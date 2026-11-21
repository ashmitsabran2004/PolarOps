from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views
from django.urls import include, path
from rest_framework.authtoken.views import obtain_auth_token

from accounts.admin_site import polar_admin_site
from accounts.views import (
    PermissionMatrixView, ProfileContactUpdateView, ProfileView,
    UserCreateView, UserDeleteView, UserEditView, UserListView,
)
from assets.views import AssetDetailView, AssetTagView, CheckinView, CheckoutView
from core.audit import AuditLogView
from core.crud import ResourceCreateView, ResourceDeleteView, ResourceDetailView, ResourceListView, ResourceUpdateView
from core.notifications import MarkAlertReadView, NotificationsView
from core.views import (
    AlertsView, CalculatorView, DashboardView, ExpeditionDetailView,
    ExpeditionListView, ExpeditionSelectionView,
)
from emergency.views import FieldSOSView, SOSActionView
from inventory.views import (
    RequisitionActionView, RequisitionCreateView, RequisitionDetailView,
    RequisitionListView, RequisitionPDFView, SupplyConsumptionView,
)
from reports.views import ReportView
from risk.views import RiskEntryView, WeatherFetchView
from transport.views import TransportApprovalView

urlpatterns = [
    path('admin/', polar_admin_site.urls),
    path('accounts/login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('accounts/logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('accounts/password_change/', auth_views.PasswordChangeView.as_view(template_name='registration/password_change.html', success_url='/profile/'), name='password_change'),
    path('profile/', ProfileView.as_view(), name='profile'),
    path('profile/edit/', ProfileContactUpdateView.as_view(), name='profile_edit'),
    path('operators/', UserListView.as_view(), name='user_list'),
    path('operators/new/', UserCreateView.as_view(), name='user_create'),
    path('operators/<int:pk>/edit/', UserEditView.as_view(), name='user_edit'),
    path('operators/<int:pk>/delete/', UserDeleteView.as_view(), name='user_delete'),
    path('permission-matrix/', PermissionMatrixView.as_view(), name='permission_matrix'),
    path('audit-log/', AuditLogView.as_view(), name='audit_log'),
    path('expedition-scope/', ExpeditionSelectionView.as_view(), name='expedition_select'),
    path('expeditions/<int:expedition_id>/risk/new/', RiskEntryView.as_view(), name='risk_entry'),
    path('expeditions/<int:expedition_id>/weather/', WeatherFetchView.as_view(), name='weather_fetch'),
    path('field/sos/', FieldSOSView.as_view(), name='field_sos'),
    path('sos/<int:pk>/<str:action>/', SOSActionView.as_view(), name='sos_action'),
    path('', DashboardView.as_view(), name='dashboard'),
    path('expeditions/', ExpeditionListView.as_view(), name='expeditions'),
    path('expeditions/<int:pk>/', ExpeditionDetailView.as_view(), name='expedition_detail'),
    path('calculator/', CalculatorView.as_view(), name='calculator'),
    path('requisitions/', RequisitionListView.as_view(), name='requisition_list'),
    path('requisitions/new/', RequisitionCreateView.as_view(), name='requisition_create'),
    path('requisitions/<int:pk>/', RequisitionDetailView.as_view(), name='requisition_detail'),
    path('requisitions/<int:pk>/action/<str:action>/', RequisitionActionView.as_view(), name='requisition_action'),
    path('requisitions/<int:pk>/pdf/', RequisitionPDFView.as_view(), name='requisition_pdf'),
    path('transport/<int:pk>/approval/<str:action>/', TransportApprovalView.as_view(), name='transport_approval'),
    path('inventory/consume/', SupplyConsumptionView.as_view(), name='supply_consumption'),
    path('alerts/', AlertsView.as_view(), name='alerts'),
    path('notifications/', NotificationsView.as_view(), name='notifications'),
    path('notifications/<int:pk>/read/', MarkAlertReadView.as_view(), name='notification_read'),
    path('reports/<str:kind>/', ReportView.as_view(), name='report'),
    path('assets/<str:code>/tag/', AssetTagView.as_view(), name='asset_tag'),
    path('assets/<str:code>/checkout/', CheckoutView.as_view(), name='asset_checkout'),
    path('assets/<str:code>/checkin/', CheckinView.as_view(), name='asset_checkin'),
    path('assets/<str:code>/', AssetDetailView.as_view(), name='asset_detail'),
    path('ops/<str:resource>/', ResourceListView.as_view(), name='resource_list'),
    path('ops/<str:resource>/new/', ResourceCreateView.as_view(), name='resource_create'),
    path('ops/<str:resource>/<int:pk>/', ResourceDetailView.as_view(), name='resource_detail'),
    path('ops/<str:resource>/<int:pk>/edit/', ResourceUpdateView.as_view(), name='resource_edit'),
    path('ops/<str:resource>/<int:pk>/delete/', ResourceDeleteView.as_view(), name='resource_delete'),
    path('api/token/', obtain_auth_token, name='api_token'),
    path('api/', include('reports.api_urls')),
]

handler403 = 'core.views.permission_denied'

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
