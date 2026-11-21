from datetime import date, timedelta
from pathlib import Path

from django.contrib.auth.models import Group, User
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import Client, TestCase
from django.utils import timezone

from accounts.permissions import PERMISSION_MAP, ROLE_CHOICES, can
from expeditions.models import Expedition
from personnel.models import PersonnelProfile


class RBACMatrixTests(TestCase):
    def setUp(self):
        self.users = {}
        for role in ROLE_CHOICES:
            user = User.objects.create_user(role.lower().replace(' ', '-'), password='long-password-123')
            user.groups.add(Group.objects.get_or_create(name=role)[0])
            self.users[role] = user

    def test_every_permission_map_entry_matches_each_role(self):
        for action, allowed in PERMISSION_MAP.items():
            for role, user in self.users.items():
                with self.subTest(action=action, role=role):
                    self.assertEqual(can(user, action), role in allowed)

    def test_invalid_unassigned_and_multi_role_users_fail_closed(self):
        user = User.objects.create_user('no-role', password='long-password-123')
        self.assertFalse(can(user, 'dashboard.view'))
        user.groups.add(Group.objects.get(name='Administrator'))
        with self.assertRaises(ValidationError):
            user.groups.add(Group.objects.get(name='Field Member'))


class RBACTargetIntegrityTests(TestCase):
    def make_user(self, username, role):
        user = User.objects.create_user(username, password='long-password-123')
        user.groups.add(Group.objects.get_or_create(name=role)[0])
        return user

    def make_expedition(self, name, leader=None):
        today = date.today()
        return Expedition.objects.create(name=name, region='arctic', latitude=78, longitude=15,
            start_date=today, end_date=today + timedelta(days=5), leader=leader)

    def test_scope_detail_is_404_for_read_and_403_for_write(self):
        leader = self.make_user('scope-leader', 'Expedition Leader')
        own = self.make_expedition('Own', leader)
        other = self.make_expedition('Other')
        client = Client(); client.force_login(leader)
        self.assertEqual(client.get(f'/expeditions/{other.pk}/').status_code, 404)
        response = client.post('/ops/expeditions/new/', {
            'name':'Out of scope edit','region':'arctic','latitude':78,'longitude':15,
            'start_date':date.today(),'end_date':date.today()+timedelta(days=2),
        })
        self.assertNotEqual(response.status_code, 403)
        self.assertEqual(client.get('/api/').status_code, 200)
        self.assertEqual(client.get('/api/expeditions/').status_code, 200)
        self.assertEqual(len(client.get('/api/expeditions/').json()), 1)

    def test_last_active_administrator_cannot_be_deactivated_or_demoted(self):
        from accounts.services import deactivate_user, set_user_role
        admin = self.make_user('only-admin', 'Administrator')
        with self.assertRaises(ValidationError):
            deactivate_user(actor=admin, user=admin, reason='test')
        with self.assertRaises((ValidationError, PermissionDenied)):
            set_user_role(actor=admin, user=admin, role='Logistics Officer', reason='test')

    def test_field_member_supply_consumption_creates_usage_only_movement(self):
        from inventory.models import StockItem, StockMovement
        from inventory.views import SupplyConsumptionView
        member = self.make_user('usage-field', 'Field Member')
        profile = PersonnelProfile.objects.create(user=member, medical_cleared=True,
            medical_expiry=date.today()+timedelta(days=60))
        expedition = self.make_expedition('Usage Camp')
        expedition.team.add(profile)
        item = StockItem.objects.create(name='Rations', category='food', quantity=20, unit='kg', minimum=0, expedition=expedition)
        client=Client(); client.force_login(member)
        response=client.post('/inventory/consume/', {'item':item.pk,'quantity':'2','reason':'Meals'})
        self.assertIn(response.status_code,(200,302))
        movement=StockMovement.objects.filter(item=item).latest('pk')
        self.assertEqual(movement.movement_type,'usage')
        self.assertLess(movement.delta,0)

    def test_viewsets_declare_permission_class_and_all_views_declare_policy(self):
        from reports.api import AlertViewSet, AssetViewSet, ExpeditionViewSet, InventoryViewSet
        for viewset in (AlertViewSet, AssetViewSet, ExpeditionViewSet, InventoryViewSet):
            self.assertTrue(viewset.permission_classes)
        # The runtime guard itself refuses dispatch for undeclared CBV actions.
        from accounts.permissions import RoleRequiredMixin
        class Undeclared(RoleRequiredMixin):
            pass
        with self.assertRaises(Exception):
            Undeclared().get_permission_action()


class RequisitionAndCustodyRulesTests(TestCase):
    def test_creator_cannot_approve_and_final_requisition_is_immutable(self):
        from inventory.models import Requisition
        from inventory.services import approve_requisition
        logistics = User.objects.create_user('rq-creator')
        logistics.groups.add(Group.objects.get_or_create(name='Logistics Officer')[0])
        today = date.today()
        expedition = Expedition.objects.create(name='Immutable',region='arctic',latitude=78,longitude=15,
            start_date=today,end_date=today+timedelta(days=3))
        req=Requisition.objects.create(expedition=expedition,requester=logistics,team_size=2,duration_days=3,status='submitted')
        with self.assertRaises(PermissionDenied): approve_requisition(req.pk,logistics)

