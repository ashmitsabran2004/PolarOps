from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from rest_framework import serializers, status, viewsets
from rest_framework.authtoken.models import Token
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import (
    ADMINISTRATOR, EXPEDITION_LEADER, PolarDRFPermission, can,
    in_scope, user_role,
)
from assets.models import Asset
from core.models import Alert
from expeditions.models import Expedition
from inventory.models import StockItem
from personnel.models import PersonnelProfile
from core.scope import scope_model_queryset


class ExpeditionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Expedition
        fields = ['id', 'name', 'region', 'latitude', 'longitude', 'start_date', 'end_date', 'objectives', 'status', 'risk_score', 'leader', 'team']

    def get_fields(self):
        fields = super().get_fields()
        user = self.context['request'].user
        if user_role(user) != ADMINISTRATOR:
            fields['leader'].read_only = True
        return fields

    def validate_leader(self, leader):
        if leader and user_role(leader) != EXPEDITION_LEADER:
            raise serializers.ValidationError('Assign an account with the Expedition Leader role.')
        return leader

    def validate_team(self, team):
        for profile in team:
            if not profile.assignment_eligible():
                raise serializers.ValidationError(f'{profile} has expired or missing medical clearance.')
            other_missions = profile.expeditions.exclude(pk=getattr(self.instance, 'pk', None))
            if other_missions.exists():
                raise serializers.ValidationError(f'{profile} is already assigned to another expedition.')
        return team

    def validate(self, attrs):
        role = user_role(self.context['request'].user)
        if role == EXPEDITION_LEADER and self.instance and self.instance.leader_id != self.context['request'].user.pk:
            raise serializers.ValidationError('You can only edit expeditions you lead.')
        if role == EXPEDITION_LEADER and 'leader' in attrs:
            raise serializers.ValidationError({'leader': 'Leaders cannot reassign expedition leadership.'})
        return attrs


class AssetSerializer(serializers.ModelSerializer):
    class Meta:
        model = Asset
        fields = ['id', 'code', 'name', 'category', 'condition', 'location', 'expedition', 'purchase_date', 'usage_hours', 'cold_exposure_hours', 'last_service', 'qr_payload']


class InventorySerializer(serializers.ModelSerializer):
    class Meta:
        model = StockItem
        fields = '__all__'
        read_only_fields = ['quantity']


class AlertSerializer(serializers.ModelSerializer):
    class Meta:
        model = Alert
        fields = ['id', 'kind', 'severity', 'title', 'detail', 'created_at', 'acknowledged', 'expedition']
        read_only_fields = ['created_at']


class BaseViewSet(viewsets.ModelViewSet):
    permission_classes = [PolarDRFPermission]
    resource_name = None

    def get_permission_action(self):
        if self.action in ('list', 'retrieve'):
            return f'api.{self.resource_name}.read'
        if self.action == 'destroy':
            return 'record.delete'
        return f'api.{self.resource_name}.write'

    def unrestricted_queryset(self):
        raise NotImplementedError

    def get_object(self):
        if self.action in ('update', 'partial_update', 'destroy'):
            lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
            obj = get_object_or_404(self.unrestricted_queryset(), **{self.lookup_field: self.kwargs[lookup_url_kwarg]})
            if not in_scope(self.request.user, obj):
                raise PermissionDenied('This record is outside your expedition scope.')
            self.check_object_permissions(self.request, obj)
            selected = scope_model_queryset(self.request, obj.__class__, self.unrestricted_queryset())
            if not selected.filter(pk=obj.pk).exists():
                raise PermissionDenied('This record is outside the selected expedition scope.')
            return obj
        return super().get_object()


class ExpeditionViewSet(BaseViewSet):
    resource_name = 'expedition'
    serializer_class = ExpeditionSerializer
    permission_classes = [PolarDRFPermission]

    def unrestricted_queryset(self):
        return Expedition.objects.select_related('leader').prefetch_related('team', 'assets')

    def get_queryset(self):
        return scope_model_queryset(self.request, Expedition, self.unrestricted_queryset()).distinct()

    def perform_create(self, serializer):
        if user_role(self.request.user) == EXPEDITION_LEADER:
            serializer.save(leader=self.request.user)
        else:
            serializer.save()


class AssetViewSet(BaseViewSet):
    resource_name = 'asset'
    serializer_class = AssetSerializer
    permission_classes = [PolarDRFPermission]

    def unrestricted_queryset(self):
        return Asset.objects.select_related('expedition')

    def get_queryset(self):
        return scope_model_queryset(self.request, Asset, self.unrestricted_queryset())


class InventoryViewSet(BaseViewSet):
    resource_name = 'inventory'
    serializer_class = InventorySerializer
    permission_classes = [PolarDRFPermission]

    def unrestricted_queryset(self):
        return StockItem.objects.select_related('expedition')

    def get_queryset(self):
        return scope_model_queryset(self.request, StockItem, self.unrestricted_queryset())


class AlertViewSet(BaseViewSet):
    resource_name = 'alert'
    serializer_class = AlertSerializer
    permission_classes = [PolarDRFPermission]

    def unrestricted_queryset(self):
        return Alert.objects.select_related('expedition').filter(acknowledged=False)

    def get_queryset(self):
        return scope_model_queryset(self.request, Alert, self.unrestricted_queryset())


class APIIndexView(APIView):
    permission_classes = [PolarDRFPermission]
    permission_action = 'api.index.view'

    def get(self, request):
        endpoints = (
            ('expeditions', 'expedition', '/api/expeditions/'),
            ('assets', 'asset', '/api/assets/'),
            ('inventory', 'inventory', '/api/inventory/'),
            ('alerts', 'alert', '/api/alerts/'),
        )
        visible = {name: request.build_absolute_uri(path) for name, action, path in endpoints
                   if can(request.user, f'api.{action}.read')}
        return Response(visible)

    def get_permission_action(self):
        return self.permission_action


class PolarObtainAuthToken(ObtainAuthToken):
    """Allow credential submission while issuing tokens only to valid PolarOps roles."""
    permission_classes = [AllowAny]
    permission_action = 'api.token.issue'

    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        if not can(user, self.permission_action):
            raise PermissionDenied('This account does not have exactly one PolarOps role.')
        token, _ = Token.objects.get_or_create(user=user)
        return Response({'token': token.key}, status=status.HTTP_200_OK)
