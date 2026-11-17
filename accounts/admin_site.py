"""Role-restricted Django admin site; user roles are managed in the audited UI."""
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

from accounts.permissions import can


class PolarOpsAdminSite(admin.AdminSite):
    site_header = 'PolarOps Administrator Console'
    site_title = 'PolarOps Admin'
    index_title = 'System administration'

    def has_permission(self, request):
        return bool(request.user.is_active and can(request.user, 'admin.site'))


polar_admin_site = PolarOpsAdminSite(name='admin')
polar_admin_site._registry = admin.site._registry.copy()
# Users and groups can only be changed through account views that enforce one role,
# self-role protection, last-Administrator protection, and role-change audit logs.
polar_admin_site._registry.pop(get_user_model(), None)
polar_admin_site._registry.pop(Group, None)
