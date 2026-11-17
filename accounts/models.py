from django.conf import settings
from django.db import models
from simple_history.models import HistoricalRecords


class RoleAuditEvent(models.Model):
    """Auditable record of a privileged account and role change."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name='role_changes')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name='role_changes_made')
    user_label = models.CharField(max_length=150, blank=True)
    actor_label = models.CharField(max_length=150, blank=True)
    old_role = models.CharField(max_length=40, blank=True)
    new_role = models.CharField(max_length=40, blank=True)
    action = models.CharField(max_length=24)
    reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    history = HistoricalRecords()

    class Meta:
        ordering = ['-created_at']

