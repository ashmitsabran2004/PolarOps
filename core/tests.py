from datetime import timedelta
from django.test import TestCase,override_settings
from django.contrib.auth.models import User,Group
from django.utils import timezone
from core.services import calculate_requirements,assess_risk,transport_conflicts
from risk.models import ConsumptionRate
from expeditions.models import Expedition
from transport.models import TransportPlan
from core.permissions import has_role
class ServiceTests(TestCase):
 def test_supply_calculator_buffer(self):
  result=calculate_requirements(2,10,'antarctica',buffer=.2)
  food=next(x for x in result if x['item']=='food'); self.assertEqual(food['quantity'],28.8)
 def test_supply_calculator_with_database_rate_and_decimal_buffer(self):
  ConsumptionRate.objects.create(region='antarctica',season='standard',item='food',per_person_day='1.200',temperature_factor='1.10')
  result=calculate_requirements(8,30,'antarctica',buffer=.20)
  self.assertEqual(next(x for x in result if x['item']=='food')['quantity'],380.16)
 def test_assessment_verdict_bounds(self):
  good=assess_risk(-5,5,20,24); bad=assess_risk(-55,110,.1,0,0,0,0)
  self.assertEqual(good['verdict'],'GO'); self.assertLessEqual(bad['score'],100); self.assertEqual(bad['verdict'],'NO-GO')
 def test_transport_conflict_vehicle_and_person(self):
  e=Expedition.objects.create(name='Test',region='arctic',latitude=70,longitude=20,start_date=timezone.localdate(),end_date=timezone.localdate()+timedelta(days=2))
  start=timezone.now()+timedelta(days=1); end=start+timedelta(hours=3)
  TransportPlan.objects.create(expedition=e,kind='flight',vehicle='Twin Otter',starts_at=start,ends_at=end,capacity=4,route='A-B')
  self.assertEqual(len(transport_conflicts('twin otter',start+timedelta(minutes=2),end+timedelta(hours=1))),1)
  self.assertEqual(len(transport_conflicts('Other',start,end)),0)
 def test_role_gate(self):
  user=User.objects.create_user('member',password='long-pass-123'); self.assertFalse(has_role(user,'Field Member'))
  user.groups.add(Group.objects.create(name='Field Member')); self.assertTrue(has_role(user,'Field Member'))

@override_settings(MEDIA_ROOT='/tmp/polarops-tests')
class ResourcePermissionTests(TestCase):
 def setUp(self):
  self.admin=User.objects.create_user('opsmanager',password='password-12345'); self.admin.groups.add(Group.objects.create(name='Logistics Officer'))
  self.member=User.objects.create_user('fieldmember',password='password-12345'); self.member.groups.add(Group.objects.create(name='Field Member'))
 def test_manager_can_open_asset_crud_and_field_member_cannot(self):
  from django.test import Client
  client=Client(); client.force_login(self.admin)
  self.assertEqual(client.get('/ops/assets/').status_code,200)
  self.assertEqual(client.get('/ops/assets/new/').status_code,200)
  client.force_login(self.member)
  self.assertEqual(client.get('/ops/assets/').status_code,403)
  self.assertEqual(client.get('/ops/assets/new/').status_code,403)
 def test_manager_can_create_asset_and_view_detail(self):
  from django.test import Client
  client=Client(); client.force_login(self.admin)
  response=client.post('/ops/assets/new/',{'code':'PO-FORM-01','name':'Field radio','category':'communication','condition':'ready','location':'Depot','usage_hours':'0','cold_exposure_hours':'0','purchase_date':'','last_service':'','expedition':''})
  self.assertEqual(response.status_code,302)
  self.assertEqual(client.get(response.url).status_code,200)

@override_settings(MEDIA_ROOT='/tmp/polarops-tests')
class AssetCustodyTests(TestCase):
 def setUp(self):
  from datetime import date,timedelta
  from personnel.models import PersonnelProfile
  from assets.models import Asset
  self.user=User.objects.create_user('custodian',password='longpassword-123')
  self.profile=PersonnelProfile.objects.create(user=self.user,medical_cleared=True,medical_expiry=date.today()+timedelta(days=90))
  self.expedition=Expedition.objects.create(name='Custody Test',region='arctic',latitude=78,longitude=15,start_date=date.today(),end_date=date.today()+timedelta(days=10))
  self.expedition.team.add(self.profile)
  self.asset=Asset.objects.create(code='PO-CUSTODY-1',name='Radio',category='communication',condition='ready',expedition=self.expedition)
 def test_checkout_rejects_maintenance_and_duplicate_custody(self):
  from django.core.exceptions import ValidationError
  from assets.services import checkout_asset
  from django.utils import timezone
  self.asset.condition='service'; self.asset.save()
  with self.assertRaises(ValidationError): checkout_asset(asset_id=self.asset.pk,taken_by=self.profile,expedition=self.expedition,checked_out_by=self.user,checkout_date=timezone.now(),handover_condition='ready')
  self.asset.condition='ready'; self.asset.save()
  checkout_asset(asset_id=self.asset.pk,taken_by=self.profile,expedition=self.expedition,checked_out_by=self.user,checkout_date=timezone.now(),handover_condition='ready')
  with self.assertRaises(ValidationError): checkout_asset(asset_id=self.asset.pk,taken_by=self.profile,expedition=self.expedition,checked_out_by=self.user,checkout_date=timezone.now(),handover_condition='ready')
 def test_checkin_adds_exposure_and_usage(self):
  from assets.services import checkout_asset,checkin_asset
  from django.utils import timezone
  checkout_asset(asset_id=self.asset.pk,taken_by=self.profile,expedition=self.expedition,checked_out_by=self.user,checkout_date=timezone.now(),handover_condition='ready')
  checkin_asset(asset_id=self.asset.pk,checked_in_by=self.user,return_condition='ready',usage_hours_added=4,cold_exposure_hours_added=9,damage_notes='No damage')
  self.asset.refresh_from_db(); self.assertEqual(self.asset.usage_hours,4); self.assertEqual(self.asset.cold_exposure_hours,9); self.assertIsNone(self.asset.checked_out_to_id)
 def test_qr_detail_view_scopes_field_member(self):
  from django.test import Client
  from django.contrib.auth.models import Group
  from assets.services import asset_qr_data_uri
  client=Client(); self.user.groups.add(Group.objects.create(name='Field Member')); client.force_login(self.user)
  self.assertEqual(client.get('/assets/PO-CUSTODY-1/').status_code,200)
  self.assertTrue(asset_qr_data_uri(self.asset,client.get('/assets/PO-CUSTODY-1/').wsgi_request).startswith('data:image/png;base64,'));self.asset.refresh_from_db();self.assertTrue(self.asset.qr_image.name)

class SOSWorkflowTests(TestCase):
 def setUp(self):
  from datetime import date,timedelta
  from django.contrib.auth.models import Group
  from personnel.models import PersonnelProfile
  self.user=User.objects.create_user('field-sos',password='long-password-123')
  self.user.groups.add(Group.objects.create(name='Field Member'))
  self.profile=PersonnelProfile.objects.create(user=self.user,medical_cleared=True,medical_expiry=date.today()+timedelta(days=60))
  self.expedition=Expedition.objects.create(name='SOS Camp',region='arctic',latitude='78.20000',longitude='15.60000',start_date=date.today(),end_date=date.today()+timedelta(days=4))
  self.expedition.team.add(self.profile)
 def test_field_member_submits_sos_prefilled_from_assigned_camp(self):
  from django.test import Client
  from emergency.models import SOSEvent
  c=Client();c.force_login(self.user)
  r=c.get('/field/sos/'); self.assertEqual(r.status_code,200); self.assertContains(r,'78.20000')
  r=c.post('/field/sos/',{'expedition':self.expedition.pk,'latitude':'78.25000','longitude':'15.70000','details':'Radio failure at camp'})
  self.assertEqual(r.status_code,302)
  event=SOSEvent.objects.get(); self.assertEqual(event.status,'open'); self.assertEqual(event.reported_by,self.user); self.assertEqual(event.status_history.count(),1)
 def test_leader_acknowledges_and_resolves_with_status_log(self):
  from django.test import Client
  from django.contrib.auth.models import Group
  from emergency.models import SOSEvent
  event=SOSEvent.objects.create(expedition=self.expedition,reported_by=self.user,latitude=78,longitude=15,details='Emergency')
  leader=User.objects.create_user('leader-sos',password='long-password-123');leader.groups.add(Group.objects.create(name='Expedition Leader'))
  c=Client();c.force_login(leader)
  self.assertEqual(c.post(f'/sos/{event.pk}/acknowledge/').status_code,302)
  self.assertEqual(c.post(f'/sos/{event.pk}/resolve/').status_code,302)
  event.refresh_from_db(); self.assertEqual(event.status,'resolved'); self.assertEqual(event.status_history.count(),2)

class WeatherFallbackTests(TestCase):
 def setUp(self):
  from datetime import date,timedelta
  from django.contrib.auth.models import Group
  self.user=User.objects.create_user('weatherlead',password='long-password-123');self.user.groups.add(Group.objects.create(name='Expedition Leader'))
  self.expedition=Expedition.objects.create(name='Weather Camp',region='arctic',latitude=78,longitude=15,start_date=date.today(),end_date=date.today()+timedelta(days=3))
 def test_open_meteo_is_parsed_with_mocked_provider(self):
  import json
  from unittest.mock import MagicMock,patch
  from risk.services import fetch_open_meteo
  response=MagicMock();response.__enter__.return_value=response
  response.read.return_value=json.dumps({'current':{'temperature_2m':-18.2,'wind_speed_10m':26.4,'visibility':12000},'daily':{'daylight_duration':[18000]}}).encode()
  with patch('risk.services.urlopen',return_value=response) as opener:
   reading=fetch_open_meteo(self.expedition,opener=opener)
  self.assertEqual(reading['temperature'],-18.2);self.assertEqual(reading['visibility_km'],12.0);opener.assert_called_once()
 def test_weather_endpoint_uses_cached_reading_when_provider_fails(self):
  from unittest.mock import patch
  from django.core.exceptions import ValidationError
  from django.test import Client
  from risk.models import WeatherReading
  WeatherReading.objects.create(expedition=self.expedition,temperature=-15,wind_kph=20,visibility_km=8,daylight_hours=5)
  client=Client();client.force_login(self.user)
  with patch('risk.views.fetch_open_meteo',side_effect=ValidationError('offline')):
   response=client.post(f'/expeditions/{self.expedition.pk}/weather/')
  self.assertEqual(response.status_code,200);self.assertEqual(response.json()['status'],'cached');self.assertEqual(response.json()['reading']['temperature'],-15.0)
 def test_weather_endpoint_without_cache_falls_back_to_manual_entry(self):
  from unittest.mock import patch
  from django.core.exceptions import ValidationError
  from django.test import Client
  client=Client();client.force_login(self.user)
  with patch('risk.views.fetch_open_meteo',side_effect=ValidationError('offline')):
   response=client.post(f'/expeditions/{self.expedition.pk}/weather/')
  self.assertEqual(response.status_code,503);self.assertEqual(response.json()['status'],'manual')

class AlertThresholdTests(TestCase):
 def test_expiry_alerts_generated_at_30_14_and_7_days(self):
  from datetime import date,timedelta
  from django.contrib.auth.models import User
  from personnel.models import PersonnelProfile,Certification
  from core.services import refresh_alerts
  user=User.objects.create_user('expiry-person')
  profile=PersonnelProfile.objects.create(user=user,medical_cleared=True,medical_expiry=date.today()+timedelta(days=30),first_aid_expiry=date.today()+timedelta(days=30))
  Certification.objects.create(profile=profile,kind='first_aid',expires_on=date.today()+timedelta(days=14))
  Certification.objects.create(profile=profile,kind='vehicle_operation',expires_on=date.today()+timedelta(days=7))
  created=refresh_alerts()
  cert_alerts=[a for a in created if a.kind=='cert']
  self.assertEqual(len(cert_alerts),4)
  self.assertTrue(any('30 days' in a.title for a in cert_alerts));self.assertTrue(any('First aid certification' in a.title for a in cert_alerts))
  self.assertTrue(any('14 days' in a.title for a in cert_alerts))
  self.assertTrue(any('7 days' in a.title for a in cert_alerts))
 def test_mark_read_creates_per_user_receipt(self):
  from django.test import Client
  from django.contrib.auth.models import Group
  from core.models import Alert,AlertReceipt
  user=User.objects.create_user('notification-manager');user.groups.add(Group.objects.create(name='Administrator'))
  alert=Alert.objects.create(kind='stock',title='Shared inventory warning')
  client=Client();client.force_login(user)
  self.assertContains(client.get('/notifications/'),'Shared inventory warning')
  self.assertEqual(client.post(f'/notifications/{alert.pk}/read/').status_code,302)
  self.assertTrue(AlertReceipt.objects.filter(alert=alert,user=user).exists())
  self.assertNotContains(client.get('/notifications/?status=unread'),'Shared inventory warning')
  self.assertContains(client.get('/notifications/?status=read'),'Shared inventory warning')
 def test_mark_read_is_role_scoped(self):
  from django.test import Client
  from django.contrib.auth.models import Group
  from core.models import Alert
  user=User.objects.create_user('notification-field');user.groups.add(Group.objects.create(name='Field Member'))
  alert=Alert.objects.create(kind='stock',title='Global stock notice')
  c=Client();c.force_login(user)
  self.assertEqual(c.get('/notifications/').status_code,200)
  self.assertEqual(c.post(f'/notifications/{alert.pk}/read/').status_code,404)

class RequisitionWorkflowTests(TestCase):
 def setUp(self):
  from datetime import date,timedelta
  from django.contrib.auth.models import Group
  from inventory.models import Requisition,RequisitionLine
  self.logistics=User.objects.create_user('rq-logistics');self.logistics.groups.add(Group.objects.create(name='Logistics Officer'))
  self.leader=User.objects.create_user('rq-leader');self.leader.groups.add(Group.objects.create(name='Expedition Leader'))
  self.expedition=Expedition.objects.create(name='Provision Camp',region='antarctica',latitude=-78,longitude=123,start_date=date.today(),end_date=date.today()+timedelta(days=20))
  self.requisition=Requisition.objects.create(expedition=self.expedition,requester=self.logistics,team_size=6,duration_days=12,safety_buffer='.2')
  RequisitionLine.objects.create(requisition=self.requisition,item_name='Field food',category='food',quantity='12.50',unit='kg')
 def test_submit_approve_fulfill_creates_stock_movement(self):
  from inventory.services import submit_requisition,approve_requisition,fulfill_requisition
  from inventory.models import StockItem,StockMovement
  submit_requisition(self.requisition.pk,self.logistics)
  approve_requisition(self.requisition.pk,self.leader)
  fulfilled=fulfill_requisition(self.requisition.pk,self.logistics)
  self.assertEqual(fulfilled.status,'fulfilled')
  stock=StockItem.objects.get(name='Field food',expedition=self.expedition)
  self.assertEqual(stock.quantity,12.5)
  self.assertEqual(StockMovement.objects.get(item=stock).delta,12.5)
 def test_roles_cannot_skip_requisition_transitions(self):
  from django.core.exceptions import PermissionDenied,ValidationError
  from inventory.services import approve_requisition,fulfill_requisition,submit_requisition
  with self.assertRaises(PermissionDenied): submit_requisition(self.requisition.pk,self.leader)
  with self.assertRaises(ValidationError): approve_requisition(self.requisition.pk,self.leader)
  with self.assertRaises(ValidationError): fulfill_requisition(self.requisition.pk,self.logistics)
 def test_calculator_conversion_creates_draft_and_field_member_is_blocked(self):
  from django.test import Client
  from django.contrib.auth.models import Group
  from inventory.models import Requisition
  client=Client();client.force_login(self.logistics)
  response=client.post('/requisitions/new/',{'team_size':'4','days':'8','region':'antarctica','season':'standard','buffer':'0.2'})
  self.assertEqual(response.status_code,302);req=Requisition.objects.filter(requester=self.logistics,team_size=4,duration_days=8).latest('pk');self.assertEqual(req.status,'draft');self.assertGreater(req.lines.count(),0)
  field=User.objects.create_user('rq-field');field.groups.add(Group.objects.create(name='Field Member'))
  client.force_login(field);self.assertEqual(client.get('/requisitions/').status_code,403);self.assertEqual(client.post('/requisitions/new/',{}).status_code,403)

@override_settings(MEDIA_ROOT='/tmp/polarops-tests')
class AuditLogTests(TestCase):
 def test_audit_log_is_admin_only_and_can_filter_model_user(self):
  from django.test import Client
  from django.contrib.auth.models import Group
  from assets.models import Asset
  admin=User.objects.create_user('audit-admin');admin.groups.add(Group.objects.create(name='Administrator'))
  member=User.objects.create_user('audit-field');member.groups.add(Group.objects.create(name='Field Member'))
  asset=Asset(code='PO-AUDIT-1',name='Beacon',category='communication',condition='ready')
  asset._history_user=admin;asset.save()
  c=Client();c.force_login(member);self.assertEqual(c.get('/audit-log/').status_code,403)
  c.force_login(admin);response=c.get('/audit-log/?model=assets.asset&user='+str(admin.pk))
  self.assertEqual(response.status_code,200);self.assertContains(response,'PO-AUDIT-1')

class ThemeContrastTests(TestCase):
 def test_all_region_palettes_meet_aa_for_text_status_and_hero_text(self):
  import re
  from pathlib import Path
  from django.conf import settings
  css=(Path(settings.BASE_DIR)/'static/css/polarops.css').read_text()
  themes=re.findall(r'html\[data-theme=([^]]+)\]\{([^}]+)',css)
  self.assertEqual({name for name,_ in themes},{'antarctica','arctic','himalaya','subantarctic','greenland'})
  def luminance(color):
   color=color.strip()
   if len(color)==4: color='#'+''.join(c*2 for c in color[1:])
   channels=[int(color[i:i+2],16)/255 for i in (1,3,5)]
   channels=[v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4 for v in channels]
   return .2126*channels[0]+.7152*channels[1]+.0722*channels[2]
  def contrast(a,b):
   x,y=sorted((luminance(a),luminance(b)),reverse=True);return (x+.05)/(y+.05)
  for name,block in themes:
   palette=dict(re.findall(r'--([\w-]+):([^;]+)',block))
   for token in ('text','accent','success','warning','danger'):
    self.assertGreaterEqual(contrast(palette[token],palette['surface']),4.5,f'{name} {token}')
   self.assertGreaterEqual(contrast('#ffffff',palette['primary']),4.5,f'{name} primary button')
   for stop in re.findall(r'#[0-9a-fA-F]{6}',palette['hero']):
    self.assertGreaterEqual(contrast('#ffffff',stop),4.5,f'{name} hero stop {stop}')

class InteractiveMapTests(TestCase):
 def setUp(self):
  from expeditions.models import Depot
  self.admin=User.objects.create_user('map-admin');self.admin.groups.add(Group.objects.create(name='Administrator'))
  self.antarctica=Expedition.objects.create(name='Map Antarctica',region='antarctica',latitude=-78.1586,longitude=123.4,start_date=timezone.localdate(),end_date=timezone.localdate()+timedelta(days=5),status='active')
  self.arctic=Expedition.objects.create(name='Map Arctic',region='arctic',latitude=78.2232,longitude=15.6469,start_date=timezone.localdate(),end_date=timezone.localdate()+timedelta(days=5),status='active')
  self.himalaya=Expedition.objects.create(name='Map Himalaya',region='himalaya',latitude=27.9881,longitude=86.925,start_date=timezone.localdate(),end_date=timezone.localdate()+timedelta(days=5),status='planned')
  Depot.objects.create(name='Map Antarctica Depot',expedition=self.antarctica,latitude=-78.15,longitude=123.75)
  Depot.objects.create(name='Map Arctic Depot',expedition=self.arctic,latitude=78.923,longitude=11.923)
  Depot.objects.create(name='Map Himalaya Depot',expedition=self.himalaya,latitude=28.0025,longitude=86.8528)
 def test_dashboard_has_leaflet_layers_correct_coordinates_and_offline_svg(self):
  from django.test import Client
  from django.conf import settings
  from unittest.mock import patch
  from django.core.exceptions import ValidationError
  c=Client();c.force_login(self.admin)
  with patch('risk.services.fetch_open_meteo',side_effect=ValidationError('offline')):
   response=c.get('/')
   preview=c.get('/?theme=himalaya')
  self.assertEqual(response.status_code,200)
  self.assertEqual(response.context['map_default_layer'],'satellite')
  body=response.content
  for value in (b'-78.1586',b'123.4',b'78.2232',b'15.6469',b'27.9881',b'86.925',b'78.923',b'11.923',b'28.0025',b'86.8528'):
   self.assertIn(value,body)
  self.assertIn(b'leafletMap',body);self.assertIn(b'opentopomap.org',body);self.assertIn(b'server.arcgisonline.com',body)
  self.assertIn(b'id="fieldMap"',body);self.assertIn(b'map-depot-data',body);self.assertIn(b'Map tiles unavailable, showing offline view',body)
  self.assertNotIn(b'tile.openstreetmap.org',body)
  self.assertEqual(preview.context['map_default_layer'],'terrain')
  self.assertEqual(settings.SECURE_REFERRER_POLICY,'strict-origin-when-cross-origin')

class DashboardExpeditionScopeTests(TestCase):
 def setUp(self):
  from datetime import date,timedelta
  from django.contrib.auth.models import Group
  from inventory.models import StockItem
  from risk.models import RiskAssessment
  self.admin=User.objects.create_user('scope-admin',password='long-password-123')
  self.admin.groups.add(Group.objects.create(name='Administrator'))
  today=date.today()
  self.antarctica=Expedition.objects.create(name='Scope Antarctica',region='antarctica',latitude=-77.8,longitude=166.7,start_date=today,end_date=today+timedelta(days=10),status='active')
  self.himalaya=Expedition.objects.create(name='Scope Himalaya',region='himalaya',latitude=28.0,longitude=86.8,start_date=today,end_date=today+timedelta(days=10),status='planned')
  self.ant_food=StockItem.objects.create(code='TEST-ANT-FOOD',name='Antarctic rations',category='food',quantity=120,minimum=20,unit='kg',expedition=self.antarctica)
  self.him_food=StockItem.objects.create(code='TEST-HIM-FOOD',name='Khumbu porter food',category='food',quantity=35,minimum=40,unit='kg',expedition=self.himalaya)
  RiskAssessment.objects.create(expedition=self.antarctica,temperature=-10,wind_kph=10,visibility_km=10,daylight_hours=24,score=18,verdict='GO',factors={'wind':2})
  RiskAssessment.objects.create(expedition=self.himalaya,temperature=-20,wind_kph=55,visibility_km=2,daylight_hours=4,score=72,verdict='NO-GO',factors={'wind':11})

 def test_expedition_scope_changes_dashboard_context_and_supply_levels(self):
  from django.test import Client
  from core.scope import SESSION_KEY
  from unittest.mock import patch
  from risk.models import RiskAssessment
  def snapshot(expedition):
   assessment=expedition.assessments.first()
   return {'risk':{'score':assessment.score,'verdict':assessment.verdict,'factors':assessment.factors},'assessment':assessment,'weather':{'temperature':float(assessment.temperature),'wind_kph':assessment.wind_kph,'visibility_km':float(assessment.visibility_km),'daylight_hours':float(assessment.daylight_hours)},'weather_source':'Manual','weather_notice':'Seeded baseline','weather_at':None}
  client=Client();client.force_login(self.admin)
  with patch('core.services.dashboard_risk_snapshot',side_effect=snapshot):
   all_response=client.get('/')
  self.assertEqual(all_response.status_code,200)
  self.assertEqual(all_response.context['scope_label'],'All expeditions')
  self.assertEqual(len(all_response.context['expeditions']),2)
  self.assertEqual({item.pk for item in all_response.context['supply_items']},{self.ant_food.pk,self.him_food.pk})
  self.assertEqual(all_response.context['risk_badge'],{'score':72,'verdict':'NO-GO'})
  changed=client.post('/expedition-scope/',{'expedition_id':self.antarctica.pk})
  self.assertEqual(changed.status_code,302)
  self.assertEqual(client.session[SESSION_KEY],str(self.antarctica.pk))
  with patch('core.services.dashboard_risk_snapshot',side_effect=snapshot):
   antarctica=client.get('/')
  self.assertEqual(antarctica.context['scope_label'],self.antarctica.name)
  self.assertEqual([item.pk for item in antarctica.context['supply_items']],[self.ant_food.pk])
  self.assertEqual(antarctica.context['risk']['score'],18)
  self.assertEqual(antarctica.context['risk_badge'],{'score':18,'verdict':'GO'})
  self.assertEqual(antarctica.context['weather_source'],'Manual')
  changed=client.post('/expedition-scope/',{'expedition_id':self.himalaya.pk})
  self.assertEqual(changed.status_code,302)
  with patch('core.services.dashboard_risk_snapshot',side_effect=snapshot):
   himalaya=client.get('/')
  self.assertEqual([item.pk for item in himalaya.context['supply_items']],[self.him_food.pk])
  self.assertNotEqual(antarctica.context['stock_rows'][0]['item'].quantity,himalaya.context['stock_rows'][0]['item'].quantity)
  self.assertEqual(himalaya.context['risk']['score'],72)
  self.assertEqual(himalaya.context['risk_badge'],{'score':72,'verdict':'NO-GO'})

 def test_latest_risk_drives_both_top_bar_and_go_no_go_panel(self):
  from django.test import Client
  from django.utils import timezone
  from django.core.exceptions import ValidationError
  from unittest.mock import patch
  from risk.models import RiskAssessment
  RiskAssessment.objects.create(expedition=self.antarctica,temperature=-31,wind_kph=70,visibility_km=3,daylight_hours=24,score=54,verdict='CAUTION',factors={'wind':16},assessed_at=timezone.now()+timedelta(seconds=1))
  client=Client();client.force_login(self.admin);client.post('/expedition-scope/',{'expedition_id':self.antarctica.pk})
  with patch('risk.services.fetch_open_meteo',side_effect=ValidationError('offline')):
   response=client.get('/')
  self.assertEqual(response.context['risk']['score'],response.context['risk_badge']['score'])
  self.assertEqual(response.context['risk']['verdict'],response.context['risk_badge']['verdict'])

@override_settings(MEDIA_ROOT='/tmp/polarops-tests')
class ManagementSurfaceTests(TestCase):
 def setUp(self):
  self.manager=User.objects.create_user('surface-manager');self.manager.groups.add(Group.objects.create(name='Expedition Leader'))
  self.field=User.objects.create_user('surface-field');self.field.groups.add(Group.objects.create(name='Field Member'))
 def test_all_manager_resource_lists_and_forms_render_and_fields_are_blocked(self):
  from django.test import Client
  resources=['expeditions','depots','personnel','certifications','assets','inventory','movements','transport','emergency-plans','risk-assessments']
  c=Client();c.force_login(self.manager)
  for resource in resources:
   with self.subTest(resource=resource):
    self.assertEqual(c.get(f'/ops/{resource}/').status_code,200)
    self.assertEqual(c.get(f'/ops/{resource}/new/').status_code,200)
  c.force_login(self.field)
  for resource in resources:
   with self.subTest(blocked_resource=resource):
    self.assertEqual(c.get(f'/ops/{resource}/').status_code,403)
    self.assertEqual(c.get(f'/ops/{resource}/new/').status_code,403)
 def test_transport_form_rejects_vehicle_overlap(self):
  from datetime import date,timedelta
  from django.utils import timezone
  from transport.models import TransportPlan
  from core.crud import TransportForm
  expedition=Expedition.objects.create(name='Transport Form Test',region='arctic',latitude=78,longitude=15,start_date=date.today(),end_date=date.today()+timedelta(days=2))
  start=timezone.now()+timedelta(days=1);end=start+timedelta(hours=3)
  TransportPlan.objects.create(expedition=expedition,kind='flight',vehicle='Twin Otter',starts_at=start,ends_at=end,capacity=6,route='A-B')
  form=TransportForm(data={'expedition':expedition.pk,'kind':'flight','vehicle':'twin otter','starts_at':(start+timedelta(minutes=30)).strftime('%Y-%m-%d %H:%M'),'ends_at':(end+timedelta(minutes=30)).strftime('%Y-%m-%d %H:%M'),'capacity':'4','route':'B-C','status':'scheduled','people':[]})
  self.assertFalse(form.is_valid());self.assertTrue(form.non_field_errors())
 def test_editing_stock_movement_adjusts_only_delta_difference(self):
  from decimal import Decimal
  from inventory.models import StockItem,StockMovement
  from core.crud import StockMovementForm
  item=StockItem.objects.create(name='Fuel drums',category='fuel',quantity=100,unit='L',minimum=10)
  form=StockMovementForm(data={'item':item.pk,'delta':'20','reason':'Receipt'});form.current_user=self.manager;self.assertTrue(form.is_valid(),form.errors);movement=form.save()
  item.refresh_from_db();self.assertEqual(item.quantity,120)
  edit=StockMovementForm(data={'item':item.pk,'delta':'30','reason':'Corrected receipt'},instance=movement);edit.current_user=self.manager;self.assertTrue(edit.is_valid(),edit.errors);edit.save()
  item.refresh_from_db();self.assertEqual(item.quantity,130)

class RequisitionRejectionTests(TestCase):
 def test_leader_can_reject_submitted_requisition_with_reason(self):
  from datetime import date,timedelta
  from django.contrib.auth.models import Group
  from expeditions.models import Expedition
  from inventory.models import Requisition
  from inventory.services import submit_requisition,reject_requisition
  logistics=User.objects.create_user('reject-logistics');logistics.groups.add(Group.objects.create(name='Logistics Officer'))
  leader=User.objects.create_user('reject-leader');leader.groups.add(Group.objects.create(name='Expedition Leader'))
  expedition=Expedition.objects.create(name='Rejection Mission',region='arctic',latitude=78,longitude=15,start_date=date.today(),end_date=date.today()+timedelta(days=3))
  requisition=Requisition.objects.create(expedition=expedition,requester=logistics,team_size=2,duration_days=3,safety_buffer=0.2)
  submit_requisition(requisition.pk,logistics)
  rejected=reject_requisition(requisition.pk,leader,'Insufficient transport capacity')
  self.assertEqual(rejected.status,'rejected')
  self.assertEqual(rejected.approver,leader)
  self.assertEqual(rejected.rejection_reason,'Insufficient transport capacity')
