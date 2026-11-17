from rest_framework.routers import DefaultRouter
from reports.api import ExpeditionViewSet,AssetViewSet,InventoryViewSet,AlertViewSet
router=DefaultRouter(); router.register('expeditions',ExpeditionViewSet,basename='expedition'); router.register('assets',AssetViewSet,basename='asset'); router.register('inventory',InventoryViewSet,basename='inventory'); router.register('alerts',AlertViewSet,basename='alert')
urlpatterns=router.urls
