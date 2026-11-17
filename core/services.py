"""Reusable PolarOps business rules."""
from datetime import timedelta
from decimal import Decimal
from django.utils import timezone
from django.db.models import Q
from core.models import Alert
from risk.models import ConsumptionRate

def calculate_requirements(team_size, days, region, season='standard', buffer=0.20):
    """Return buffered supply requirements based on the editable consumption table."""
    if team_size < 1 or days < 1 or not 0 <= buffer <= 2: raise ValueError('Team, duration, and buffer must be positive and valid.')
    buffer_factor=Decimal('1')+Decimal(str(buffer))
    rates=ConsumptionRate.objects.filter(region=region,season__in=[season,'standard']).order_by('season')
    chosen={}
    for rate in rates: chosen[rate.item]=rate
    defaults={'food':Decimal('1.2'),'fuel':Decimal('2.5'),'water':Decimal('3.0'),'medical':Decimal('0.08')}
    result=[]
    for item,rate in chosen.items() if chosen else defaults.items():
        per_person_day=rate.per_person_day*rate.temperature_factor if hasattr(rate,'per_person_day') else rate
        qty=per_person_day*team_size*days*buffer_factor
        result.append({'item':item,'quantity':round(float(qty),2),'unit':{'food':'kg','fuel':'L','water':'L','medical':'kit'}[item] if item in ('food','fuel','water','medical') else 'unit'})
    return result

def assess_risk(temperature, wind_kph, visibility_km, daylight_hours, team_ready=1.0, equipment_ready=1.0, supply_sufficiency=1.0):
    """Score environmental and operational exposure from zero (low) to 100 (extreme)."""
    factors={
      'temperature': min(30,max(0,(abs(float(temperature))-15)*0.8)),
      'wind': min(25,max(0,(float(wind_kph)-25)*0.35)),
      'visibility': min(20,max(0,(5-float(visibility_km))*4)),
      'daylight': min(15,max(0,(8-float(daylight_hours))*1.8)),
      'team_readiness': min(10,max(0,(1-float(team_ready))*10)),
      'equipment_readiness': min(10,max(0,(1-float(equipment_ready))*10)),
      'supply_sufficiency': min(10,max(0,(1-float(supply_sufficiency))*10)),
    }
    score=min(100,round(sum(factors.values())))
    return {'score':score,'verdict':'NO-GO' if score>=70 else 'CAUTION' if score>=40 else 'GO','factors':factors}

def dashboard_risk_snapshot(expedition, *, timeout=2):
    """Fetch/cache weather for one expedition and persist its current readiness assessment."""
    from django.core.exceptions import ValidationError
    from django.utils import timezone
    from risk.models import RiskAssessment, WeatherReading
    from risk.services import fetch_open_meteo, latest_weather
    from expeditions.models import Expedition

    latest=latest_weather(expedition)
    try:
        weather=fetch_open_meteo(expedition,timeout=timeout)
        if latest and all(float(getattr(latest,key))==float(weather[key]) for key in ('temperature','wind_kph','visibility_km','daylight_hours')):
            WeatherReading.objects.filter(pk=latest.pk).update(fetched_at=timezone.now(),payload=weather.get('payload',{}))
            latest.refresh_from_db(fields=['fetched_at'])
        else:
            latest=WeatherReading.objects.create(expedition=expedition,temperature=weather['temperature'],wind_kph=weather['wind_kph'],visibility_km=weather['visibility_km'],daylight_hours=weather['daylight_hours'],source='open-meteo',payload=weather.get('payload',{}))
        source='Live'; notice='Weather updated from Open-Meteo.'
    except ValidationError:
        latest=latest_weather(expedition)
        if latest:
            weather={key:float(getattr(latest,key)) for key in ('temperature','wind_kph','visibility_km','daylight_hours')}
            source='Cached'; notice='Open-Meteo unavailable; showing the last successful reading.'
        else:
            baseline=next(iter(expedition.assessments.all()),None)
            if baseline:
                weather={'temperature':float(baseline.temperature),'wind_kph':float(baseline.wind_kph),'visibility_km':float(baseline.visibility_km),'daylight_hours':float(baseline.daylight_hours)}
            else:
                values={'antarctica':(-30,55,5,24),'arctic':(-18,40,3,0),'himalaya':(-18,70,.8,5)}
                temp,wind,visibility,daylight=values.get(expedition.region,(-15,35,5,8))
                weather={'temperature':temp,'wind_kph':wind,'visibility_km':visibility,'daylight_hours':daylight}
            source='Manual'; notice='Open-Meteo unavailable; showing the seeded regional baseline.'

    team=list(expedition.team.all())
    if team:
        today=timezone.localdate()
        ready=sum(bool(person.assignment_eligible() and any(cert.expires_on>=today for cert in person.certifications.all())) for person in team)
        team_ready=ready/len(team)
    else:
        team_ready=0.0
    assets=list(expedition.assets.all())
    equipment_ready=sum(asset.condition=='ready' for asset in assets)/len(assets) if assets else 0.0
    supplies=list(expedition.supplies.all())
    supply_sufficiency=sum(item.quantity>item.minimum for item in supplies)/len(supplies) if supplies else 0.0
    result=assess_risk(weather['temperature'],weather['wind_kph'],weather['visibility_km'],weather['daylight_hours'],team_ready,equipment_ready,supply_sufficiency)
    latest_assessment=next(iter(expedition.assessments.all()),None)
    inputs=(weather['temperature'],weather['wind_kph'],weather['visibility_km'],weather['daylight_hours'],result['score'],result['verdict'],result['factors'])
    current=(float(latest_assessment.temperature),latest_assessment.wind_kph,float(latest_assessment.visibility_km),float(latest_assessment.daylight_hours),latest_assessment.score,latest_assessment.verdict,latest_assessment.factors) if latest_assessment else None
    if inputs!=current:
        latest_assessment=RiskAssessment.objects.create(expedition=expedition,temperature=weather['temperature'],wind_kph=weather['wind_kph'],visibility_km=weather['visibility_km'],daylight_hours=weather['daylight_hours'],score=result['score'],verdict=result['verdict'],factors=result['factors'])
        Expedition.objects.filter(pk=expedition.pk).update(risk_score=result['score'])
    return {'risk':result,'assessment':latest_assessment,'weather':weather,'weather_source':source,'weather_notice':notice,'weather_at':latest.fetched_at if latest else None}

def transport_conflicts(vehicle, starts_at, ends_at, people=None, exclude_id=None):
    """Find overlapping plans sharing a vehicle or any assigned person."""
    from transport.models import TransportPlan
    qs=TransportPlan.objects.filter(starts_at__lt=ends_at,ends_at__gt=starts_at).exclude(status='cancelled')
    if exclude_id: qs=qs.exclude(pk=exclude_id)
    conflicts=list(qs.filter(vehicle__iexact=vehicle))
    if people:
        conflicts.extend(qs.filter(people__in=people).distinct())
    return list({p.pk:p for p in conflicts}.values())

def refresh_alerts():
    """Create current operational alerts without duplicating existing open alerts."""
    from inventory.models import StockItem, ColdChainBreach
    from assets.models import Asset
    from personnel.models import PersonnelProfile
    now=timezone.now(); created=[]
    candidates=[]
    for item in StockItem.objects.filter(quantity__lte=models_f('minimum')):
        candidates.append(('stock',f'Low stock: {item.name}',item.expedition_id,2))
    for breach in ColdChainBreach.objects.filter(recorded_at__gte=now-timedelta(days=1)):
        candidates.append(('cold',f'Cold-chain breach: {breach.item.name}',breach.item.expedition_id,4))
    for asset in Asset.objects.filter(Q(last_service__isnull=True) | Q(last_service__lt=timezone.localdate()-timedelta(days=365))):
        candidates.append(('maintenance',f'Maintenance overdue: {asset.code}',asset.expedition_id,3))
    from personnel.models import PersonnelProfile,Certification
    today=timezone.localdate()
    warning_days=(30,14,7)
    for profile in PersonnelProfile.objects.select_related('user').filter(medical_expiry__isnull=False):
        days=(profile.medical_expiry-today).days
        if days in warning_days:
            missions=list(profile.expeditions.values_list('pk',flat=True)) or [None]
            for expedition_id in missions:
                candidates.append(('cert',f'Medical clearance for {profile} expires in {days} days',expedition_id,3 if days<=7 else 2))
    legacy_cert_fields={
        'first_aid_expiry':'First aid',
        'glacier_rescue_expiry':'Glacier rescue',
        'polar_survival_expiry':'Polar survival',
        'vehicle_operation_expiry':'Vehicle operation',
    }
    for profile in PersonnelProfile.objects.select_related('user'):
        for field,label in legacy_cert_fields.items():
            expires=getattr(profile,field)
            if expires and (expires-today).days in warning_days:
                days=(expires-today).days
                missions=list(profile.expeditions.values_list('pk',flat=True)) or [None]
                for expedition_id in missions:
                    candidates.append(('cert',f'{label} certification for {profile} expires in {days} days',expedition_id,3 if days<=7 else 2))
    for cert in Certification.objects.select_related('profile__user'):
        days=(cert.expires_on-today).days
        if days in warning_days:
            missions=list(cert.profile.expeditions.values_list('pk',flat=True)) or [None]
            for expedition_id in missions:
                candidates.append(('cert',f'{cert.get_kind_display()} certification for {cert.profile} expires in {days} days',expedition_id,3 if days<=7 else 2))
    for kind,title,expedition_id,severity in candidates:
        alert,was_created=Alert.objects.get_or_create(kind=kind,title=title,expedition_id=expedition_id,defaults={'severity':severity})
        if was_created: created.append(alert)
    return created

from django.db.models import F as models_f
