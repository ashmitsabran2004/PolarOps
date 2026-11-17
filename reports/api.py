from rest_framework import serializers,viewsets
from core.permissions import PolarRolePermission
from expeditions.models import Expedition
from assets.models import Asset
from inventory.models import StockItem
from core.models import Alert
class ExpeditionSerializer(serializers.ModelSerializer):
    class Meta: model=Expedition; fields='__all__'
    def validate(self,attrs):
        user=self.context['request'].user
        if not (user.is_superuser or user.groups.filter(name__in=['Administrator','Expedition Leader','Logistics Officer']).exists()):
            raise serializers.ValidationError('Field members cannot create or modify expeditions.')
        return attrs
class AssetSerializer(serializers.ModelSerializer):
    class Meta: model=Asset; fields='__all__'
class InventorySerializer(serializers.ModelSerializer):
    class Meta: model=StockItem; fields='__all__'
class AlertSerializer(serializers.ModelSerializer):
    class Meta: model=Alert; fields='__all__'
class BaseViewSet(viewsets.ModelViewSet):
    permission_classes=[PolarRolePermission]
    def field_expeditions(self):
        profile=getattr(self.request.user,'field_profile',None)
        return profile.expeditions.all() if profile else Expedition.objects.none()
    def is_manager(self): return self.request.user.is_superuser or self.request.user.groups.filter(name__in=['Administrator','Expedition Leader','Logistics Officer']).exists()
class ExpeditionViewSet(BaseViewSet):
    serializer_class=ExpeditionSerializer
    def get_queryset(self):
        qs=Expedition.objects.prefetch_related('team','assets')
        if not self.is_manager(): qs=qs.filter(team__user=self.request.user)
        return qs.distinct()
class AssetViewSet(BaseViewSet):
    serializer_class=AssetSerializer
    def get_permissions(self):
        if self.action in ['create','update','partial_update','destroy'] and not self.is_manager(): return [__import__('rest_framework.permissions',fromlist=['IsAdminUser']).IsAdminUser()]
        return super().get_permissions()
    def get_queryset(self):
        qs=Asset.objects.select_related('expedition')
        return qs if self.is_manager() else qs.filter(expedition__in=self.field_expeditions())
class InventoryViewSet(BaseViewSet):
    serializer_class=InventorySerializer
    def get_permissions(self):
        if self.action in ['create','update','partial_update','destroy'] and not self.is_manager(): return [__import__('rest_framework.permissions',fromlist=['IsAdminUser']).IsAdminUser()]
        return super().get_permissions()
    def get_queryset(self):
        qs=StockItem.objects.select_related('expedition')
        return qs if self.is_manager() else qs.filter(expedition__in=self.field_expeditions())
class AlertViewSet(BaseViewSet):
    serializer_class=AlertSerializer
    def get_queryset(self):
        qs=Alert.objects.all()
        return qs if self.is_manager() else qs.filter(expedition__in=self.field_expeditions(),recipient=self.request.user)
