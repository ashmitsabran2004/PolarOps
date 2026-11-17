"""Recreate the three simulated PolarOps training expeditions and their fixtures."""
from datetime import date,datetime,timedelta
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User,Group
from django.db import transaction
from django.utils import timezone
from expeditions.models import Expedition,Depot
from personnel.models import PersonnelProfile,Certification
from assets.models import Asset,MaintenanceRecord
from inventory.models import StockItem,StockMovement,ColdChainBreach,Requisition
from transport.models import TransportPlan
from emergency.models import SOSEvent,SOSStatusEvent,ContingencyPlan
from risk.models import ConsumptionRate,RiskAssessment,WeatherReading
from core.models import Alert
from core.services import assess_risk,refresh_alerts

MISSIONS=[
 {'name':'McMurdo–South Pole Traverse 2026/27','region':'antarctica','lat':-77.8419,'lon':166.6863,'status':'active','start':date(2026,12,1),'days':68,'team_size':5,'objectives':'Simulated coastal departure from McMurdo Station across the Ross Ice Shelf and up onto the polar plateau; establish fuel caches, conduct ice-core sampling and validate traverse communications.','weather':(-28,38,8,24),'readiness':(.98,.93,.90),'depot':('South Pole Plateau Cache',-89.99,0.0),'evac':'McMurdo Station (-77.8419,166.6863) → Ross Ice Shelf cache (-82.8628,135.0000) → South Pole (-90.0000,0.0000)','stations':'McMurdo Station; Amundsen–Scott South Pole Station','checklist':'Account for traverse team; secure fuel bladders; establish HF and satellite check-in; prepare tracked-vehicle tow and medical sled.'},
 {'name':'Ny-Ålesund Polar Night Observatory','region':'arctic','lat':78.9230,'lon':11.9230,'status':'active','start':date(2026,12,10),'days':100,'team_size':4,'objectives':'Simulated Svalbard research-camp season during polar night: maintain weather masts, sample the ice edge by boat when conditions permit, and enforce polar-bear watch protocols.','weather':(-18,62,2.2,.3),'readiness':(.80,.72,.65),'depot':('Longyearbyen Ice-Edge Depot',78.2232,15.6469),'evac':'Ny-Ålesund (78.9230,11.9230) → Kongsfjorden landing (78.9750,12.0000) → Longyearbyen (78.2232,15.6469)','stations':'Ny-Ålesund Research Station; Longyearbyen Hospital; Governor of Svalbard rescue base','checklist':'Post two-person polar-bear watch; check flare and deterrent inventory; confirm vessel ice report; maintain heated sample lockers and satellite beacon.'},
 {'name':'Everest Base Camp High-Altitude Relay','region':'himalaya','lat':28.0043,'lon':86.8528,'status':'planned','start':date(2027,4,20),'days':44,'team_size':3,'objectives':'Simulated Everest Base Camp deployment near 5,300 m: relay communications, test oxygen systems, service solar power and move science payloads by helicopter, yak and porter caravan.','weather':(-19,92,.4,4.5),'readiness':(.35,.25,.35),'depot':('Pangboche Medical Staging Cache',27.8625,86.7864),'evac':'Everest Base Camp (28.0043,86.8528) → Lobuche (27.9590,86.8100) → Pheriche (27.8950,86.8190)','stations':'Everest ER clinic; Pheriche Himalayan Rescue Association clinic; Lukla airstrip','checklist':'Check oxygen pressure and masks; assess altitude symptoms; confirm weather window and helicopter landing zone; prepare portable hyperbaric chamber.'},
]

CREW=[
 ('field_member','Aroha McMurdo','New Zealand','Traverse Commander','O+'),('field01','Elias Mikkelsen','Norwegian','Snow Tractor Engineer','A-'),('field02','Priya Nair','Indian','Glaciologist / Ice-Core Lead','B+'),('field03','Mateo Rojas','Chilean','Power and Fuel Technician','O-'),('field04','Nia Sørensen','Danish','Field Medic','AB+'),
 ('field05','Freya Lund','Norwegian','Camp Scientist','A+'),('field06','Aputi Knudsen','Greenlandic','Polar-Bear Safety Officer','O+'),('field07','Erik Solberg','Swedish','Marine Engineer','B-'),('field08','Mina Johansen','Danish','Sample-Preservation Specialist','AB-'),
 ('field09','Tenzing Sherpa','Nepali','High-Altitude Sirdar','O+'),('field10','Pasang Lama','Nepali','Climbing Medic','A+'),('field11','Maya Gurung','Nepali','Oxygen and Solar Technician','B+'),
]
CERTS={
 'antarctica':[('first_aid',180),('polar_survival',220),('vehicle_operation',210),('glacier_rescue',200)],
 'arctic':[('first_aid',90),('polar_survival',14),('vehicle_operation',70),('glacier_rescue',60)],
 'himalaya':[('first_aid',7),('glacier_rescue',21),('vehicle_operation',45)],
}
ASSETS={
 'antarctica':[
  ('TRK','PistenBully 300 Polar Tractor','vehicle','ready'),('TRK','Challenger 9200 Snow Tractor','vehicle','ready'),('TRK','Sno-Cat Traverse Unit','vehicle','service'),('TRK','Twin Otter Fuel Sled','vehicle','ready'),('TRK','Polar Cargo Sled Alpha','vehicle','ready'),('TRK','Polar Cargo Sled Bravo','vehicle','ready'),('SHEL','Endurance High-Wind Tent','shelter','ready'),('PWR','30 kW Plateau Generator','power','ready'),('PWR','Arctic Grade Battery Bank','power','service'),('COM','Iridium Expedition Terminal','communication','ready'),('COM','HF Traverse Radio Set','communication','ready'),('SCI','Kovacs Ice-Coring Drill','scientific_instrument','ready'),('SCI','Ground-Penetrating Radar Array','scientific_instrument','ready'),('SAFE','Crevasse Probe and Rescue Kit','safety_gear','ready'),('SAFE','Emergency Medical Sled','safety_gear','ready')],
 'arctic':[
  ('SNOW','Lynx Expedition Snowmobile','vehicle','ready'),('SNOW','Ski-Doo Tundra Carrier','vehicle','ready'),('BOAT','Zodiac Ice-Edge RIB','vehicle','ready'),('BOAT','Kongsfjorden Workboat','vehicle','service'),('SAFE','Polar-Bear Deterrent Kit','safety_gear','ready'),('SAFE','12-Gauge Bear-Safety Kit','safety_gear','ready'),('SAFE','Signal Flare Launcher Set','safety_gear','ready'),('SCI','Ny-Ålesund Weather Mast','scientific_instrument','ready'),('SCI','Sea-Ice Sampling Kit','scientific_instrument','service'),('SCI','CTD Water Sampler','scientific_instrument','ready'),('PWR','Polar Night Battery and Heater','power','ready'),('SHEL','Insulated Observatory Module','shelter','ready'),('COM','Iridium Bear-Watch Radio','communication','ready'),('SAFE','Ice-Edge Immersion Suits','safety_gear','damaged')],
 'himalaya':[
  ('OXY','High-Altitude Oxygen Rack','safety_gear','ready'),('OXY','Portable Oxygen Concentrator','power','service'),('TENT','5,300 m Storm Tent','shelter','ready'),('TENT','High-Altitude Medical Tent','shelter','ready'),('PWR','Everest 2 kW Solar Array','power','ready'),('PWR','Cold-Soak Battery Module','power','damaged'),('SAFE','Fixed-Rope Ice-Climbing Kit','safety_gear','ready'),('SAFE','Portable Hyperbaric Chamber','safety_gear','service'),('COM','Khumbu VHF Relay Radio','communication','ready'),('COM','Summit-Line Satellite Phone','communication','ready'),('SCI','Thin-Air Weather Station','scientific_instrument','service'),('SAFE','Crampon and Ice-Axe Set','safety_gear','ready'),('OXY','Spare Regulator Manifold','safety_gear','damaged'),('TENT','Yak-Carried Payload Sled','vehicle','ready')]
}
STOCK={
 'antarctica':[
  ('ANT-FOOD-001','Plateau High-Calorie Rations','food',860,300,'kg','camp',None,None),('ANT-FUEL-001','JP-8 Aviation Fuel Bladders','fuel',1850,600,'L','depot',None,None),('ANT-FUEL-002','Arctic Diesel Traverse Reserve','fuel',4300,1200,'L','camp',None,None),('ANT-MED-001','Polar Trauma and Frostbite Kits','medical',26,18,'kit','camp',-25,8),('ANT-SPR-001','Generator Belts and Cold-Start Filters','spares',4,10,'unit','depot',None,None)],
 'arctic':[
  ('ARC-SPR-001','Bear-Safety Ammunition Case','spares',64,40,'rounds','camp',None,None),('ARC-SAFE-001','Marine Signal Flares','spares',12,24,'flare','camp',None,None),('ARC-FUEL-001','Marine Diesel Reserve','fuel',5700,1800,'L','depot',None,None),('ARC-WATER-001','Fresh-Water Desalination Cartridges','spares',9,6,'cartridge','camp',None,None),('ARC-SAMP-001','Cryogenic Sample-Preservation Vials','sample',5,12,'box','camp',-25,-10),('ARC-MED-001','Polar Night Medical Cache','medical',18,10,'kit','warehouse',-20,8)],
 'himalaya':[
  ('HIM-OXY-001','Medical Oxygen Cylinders 4.5 L','medical',42,18,'cylinder','camp',-20,25),('HIM-FUEL-001','High-Altitude Kerosene','fuel',680,250,'L','depot',None,None),('HIM-FUEL-002','Isobutane Climbing Gas Canisters','fuel',82,35,'canister','camp',None,None),('HIM-FOOD-001','Porter-Carried High-Energy Food','food',96,140,'kg','camp',None,None),('HIM-MED-001','Acetazolamide and Altitude-Sickness Pack','medical',7,12,'pack','camp',-10,25),('HIM-SPR-001','Oxygen Regulator and Mask Spares','spares',16,6,'unit','depot',None,None)]
}
RATES={
 'antarctica':{'food':(1.8,1.18),'fuel':(8.5,1.45),'water':(3.4,1.1),'medical':(.12,1.2)},
 'arctic':{'food':(1.65,1.12),'fuel':(5.8,1.3),'water':(2.8,1.05),'medical':(.15,1.15)},
 'himalaya':{'food':(1.5,1.1),'fuel':(2.2,1.05),'water':(3.2,1.1),'medical':(.2,1.35)},
}

class Command(BaseCommand):
    help='Reset and create PolarOps synthetic regional demonstration data.'
    @transaction.atomic
    def handle(self,*args,**opts):
        roles=['Administrator','Expedition Leader','Logistics Officer','Field Member']
        groups={role:Group.objects.get_or_create(name=role)[0] for role in roles}
        role_users={}
        for role in roles:
            username=role.lower().replace(' ','_');user,_=User.objects.get_or_create(username=username,defaults={'email':f'{username}@polarops.demo','first_name':role.split()[0],'last_name':'Demo'})
            user.email=f'{username}@polarops.demo';user.set_password('PolarOps-2026!');user.save();user.groups.set([groups[role]]);role_users[role]=user
        old_names=[m['name'] for m in MISSIONS]+['South Pole Traverse 26','Aurora Shelf Survey','High Altitude Relay']
        old_expeditions=Expedition.objects.filter(name__in=set(old_names))
        Requisition.objects.filter(expedition__in=old_expeditions).delete()
        Asset.objects.filter(expedition__in=old_expeditions).delete()
        StockItem.objects.filter(expedition__in=old_expeditions).delete()
        Depot.objects.filter(expedition__in=old_expeditions).delete()
        old_expeditions.delete()
        demo_usernames=['field_member']+[f'field{i:02d}' for i in range(1,13)]
        User.objects.filter(username__in=demo_usernames).delete()
        today=timezone.localdate();profiles=[]
        for index,(username,name,nationality,job,blood) in enumerate(CREW):
            user=User.objects.create_user(username=username,email=f'{username}@polarops.demo',password='PolarOps-2026!',first_name=name.split()[0],last_name=' '.join(name.split()[1:]))
            user.groups.set([groups['Field Member']]);region='antarctica' if index<5 else 'arctic' if index<9 else 'himalaya'
            clearance_days=[150,120,95,80,65,90,30,75,60,60,45,35][index]
            profile=PersonnelProfile.objects.create(user=user,role=job,nationality=nationality,blood_group=blood,emergency_contact=f'{nationality} expedition desk · +1-555-{6100+index}',medical_cleared=True,medical_expiry=today+timedelta(days=clearance_days))
            profiles.append(profile)
            for kind,days in CERTS[region]:
                if username=='field07' and kind=='polar_survival':days=14
                if username=='field10' and kind=='first_aid':days=7
                Certification.objects.create(profile=profile,kind=kind,issued_on=today-timedelta(days=300),expires_on=today+timedelta(days=days),credential_id=f'{region[:3].upper()}-{kind[:3].upper()}-{index+1:02d}')
        expeditions=[];team_slices=[profiles[0:5],profiles[5:9],profiles[9:12]]
        for idx,mission in enumerate(MISSIONS):
            start=mission['start'];end=start+timedelta(days=mission['days'])
            e=Expedition.objects.create(name=mission['name'],region=mission['region'],latitude=mission['lat'],longitude=mission['lon'],start_date=start,end_date=end,objectives=mission['objectives']+' ALL RECORDS IN THIS EXPEDITION ARE SIMULATED TRAINING DATA.',status=mission['status'],leader=role_users['Expedition Leader'])
            e.team.set(team_slices[idx]);expeditions.append(e)
            ContingencyPlan.objects.create(expedition=e,evacuation_route=mission['evac'],nearest_stations=mission['stations'],checklist=mission['checklist']+' Simulated exercise; verify routes and numbers before any real deployment.')
            Depot.objects.create(expedition=e,name=mission['depot'][0],latitude=mission['depot'][1],longitude=mission['depot'][2],status='active',notes='SIMULATED demo depot; coordinates are real regional reference points.')
        for region_index,e in enumerate(expeditions):
            mission=MISSIONS[region_index];region=e.region; assets=ASSETS[region]
            for n,(prefix,name,category,condition) in enumerate(assets,1):
                code=f'{region[:3].upper()}-{prefix}-{n:03d}'
                asset=Asset.objects.create(code=code,name=name,category=category,condition=condition,location=f'{e.name} staging area',expedition=e,purchase_date=today-timedelta(days=300+n*19),usage_hours=260+n*110,cold_exposure_hours=200+n*125,last_service=today-timedelta(days=[35,420,75][region_index] if condition=='service' else 45+n*12),qr_payload=code)
                if n%2==0 or condition=='service':
                    due=today-timedelta(days=18) if condition=='service' and n%2==0 else today+timedelta(days=35+n)
                    MaintenanceRecord.objects.create(asset=asset,service_date=today-timedelta(days=55+n*5),summary=f'SIMULATED regional inspection · {name}',next_due=due)
            for code,name,category,quantity,minimum,unit,location,cold_min,cold_max in STOCK[region]:
                item=StockItem.objects.create(code=code,name=name,category=category,quantity=Decimal(str(quantity)),unit=unit,minimum=Decimal(str(minimum)),location=location,expedition=e,cold_min=cold_min,cold_max=cold_max)
                StockMovement.objects.create(item=item,delta=Decimal(str(quantity)),reason='SIMULATED opening regional stock balance',by=role_users['Logistics Officer'])
            if region=='antarctica':
                plans=[('flight','Twin Otter 300 · McMurdo Air Wing','McMurdo (-77.8419,166.6863) → South Pole (-90,0)',start+timedelta(days=2),6,'scheduled'),('traverse','Challenger 9200 snow-tractor traverse','McMurdo (-77.8419,166.6863) → Ross Shelf (-82.8628,135) → South Pole (-90,0)',start+timedelta(days=4),12,'scheduled')]
            elif region=='arctic':
                plans=[('ship','RV Kronprins Haakon','Longyearbyen (78.2232,15.6469) → Ny-Ålesund (78.923,11.923)',start+timedelta(days=1),26,'scheduled'),('flight','AS350 B3 rescue helicopter','Longyearbyen (78.2232,15.6469) → Ny-Ålesund (78.923,11.923)',start+timedelta(days=4),5,'scheduled')]
            else:
                plans=[('flight','AS350 B3+ high-altitude helicopter','Lukla (27.687,86.731) → Everest Base Camp (28.0043,86.8528)',start+timedelta(days=3),5,'scheduled'),('traverse','Yak and porter supply caravan','Pangboche (27.8625,86.7864) → Lobuche (27.959,86.810) → Everest Base Camp (28.0043,86.8528)',start+timedelta(days=6),9,'scheduled')]
            for kind,vehicle,route,depart,capacity,status in plans:
                plan=TransportPlan.objects.create(expedition=e,kind=kind,vehicle=vehicle,starts_at=timezone.make_aware(datetime.combine(depart,datetime.min.time().replace(hour=8))),ends_at=timezone.make_aware(datetime.combine(depart,datetime.min.time().replace(hour=13))),capacity=capacity,route=route,status=status)
                plan.people.set(team_slices[region_index])
            temp,wind,visibility,daylight=mission['weather'];team_ready,equipment_ready,supply_ready=mission['readiness'];risk=assess_risk(temp,wind,visibility,daylight,team_ready,equipment_ready,supply_ready)
            RiskAssessment.objects.create(expedition=e,temperature=temp,wind_kph=wind,visibility_km=visibility,daylight_hours=daylight,score=risk['score'],verdict=risk['verdict'],factors=risk['factors'])
            e.risk_score=risk['score'];e.save(update_fields=['risk_score'])
            for item,(rate,factor) in RATES[region].items():
                ConsumptionRate.objects.update_or_create(region=region,season='standard',item=item,defaults={'per_person_day':rate,'temperature_factor':factor})
            if region=='arctic':
                sample=StockItem.objects.get(expedition=e,category='sample')
                ColdChainBreach.objects.create(item=sample,temperature=-5,notes='SIMULATED excursion during polar-night handover drill.')
        # A single live signal per mission gives the scope switch a visible emergency state.
        event=SOSEvent.objects.create(expedition=expeditions[1],reported_by=profiles[6].user,latitude=78.8800,longitude=11.7600,details='SIMULATED polar-bear watch shelter incident; team safe, awaiting acknowledgement.',status='open')
        SOSStatusEvent.objects.create(event=event,to_status='open',changed_by=profiles[6].user,note='Training signal submitted from the Ny-Ålesund camp.')
        him_event=SOSEvent.objects.create(expedition=expeditions[2],reported_by=profiles[10].user,latitude=28.0043,longitude=86.8528,details='SIMULATED altitude-sickness evacuation drill; patient stabilized.',status='acknowledged')
        SOSStatusEvent.objects.create(event=him_event,to_status='open',changed_by=profiles[10].user,note='Training signal submitted.')
        SOSStatusEvent.objects.create(event=him_event,from_status='open',to_status='acknowledged',changed_by=role_users['Expedition Leader'],note='Training signal acknowledged by expedition leadership.')
        refresh_alerts()
        self.stdout.write(self.style.SUCCESS('Seeded simulated Antarctic, Arctic and Himalayan expeditions, with region-specific personnel, assets, stock, routes, risks, SOS signals and alerts. Demo password: PolarOps-2026!'))
