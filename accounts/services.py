"""Privileged account changes with role policy and audit records."""
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from accounts.models import RoleAuditEvent
from accounts.permissions import ADMINISTRATOR, ROLE_CHOICES, can, user_role
from accounts.signals import active_admin_count


@transaction.atomic
def set_user_role(*, actor, user, role, reason=''):
    """Assign the sole role group, refusing self-role changes and final demotion."""
    if not can(actor, 'user.manage'):
        raise PermissionDenied
    if role not in ROLE_CHOICES:
        raise ValidationError('Choose one of the four PolarOps roles.')
    previous = user_role(user) or ''
    if user.pk == actor.pk and previous != role:
        raise PermissionDenied('Administrators cannot change their own role.')
    if previous == ADMINISTRATOR and role != ADMINISTRATOR and user.is_active and active_admin_count(exclude_pk=user.pk) == 0:
        raise ValidationError('The last active Administrator cannot be demoted.')
    group, _ = Group.objects.get_or_create(name=role)
    user.groups.set([group])
    entry = RoleAuditEvent(user=user, actor=actor, user_label=user.get_username(), actor_label=actor.get_username(), old_role=previous, new_role=role, action='role_changed', reason=reason)
    entry._history_user = actor
    entry.save()
    return user


@transaction.atomic
def deactivate_user(*, actor, user, reason=''):
    """Deactivate an account while preserving at least one active Administrator."""
    if not can(actor, 'user.manage'):
        raise PermissionDenied
    if user_role(user) == ADMINISTRATOR and user.is_active and active_admin_count(exclude_pk=user.pk) == 0:
        raise ValidationError('The last active Administrator cannot be deactivated.')
    user.is_active = False
    user.save(update_fields=['is_active'])
    event = RoleAuditEvent(user=user, actor=actor, user_label=user.get_username(), actor_label=actor.get_username(), old_role=user_role(user) or '', new_role=user_role(user) or '', action='deactivated', reason=reason)
    event._history_user = actor
    event.save()
    return user


@transaction.atomic
def delete_user(*, actor, user, reason=''):
    """Delete a user only when doing so cannot remove the final Administrator."""
    if not can(actor, 'user.manage'):
        raise PermissionDenied
    if user_role(user) == ADMINISTRATOR and user.is_active and active_admin_count(exclude_pk=user.pk) == 0:
        raise ValidationError('The last active Administrator cannot be deleted.')
    old_role = user_role(user) or ''
    event = RoleAuditEvent(user=user, actor=actor, user_label=user.get_username(), actor_label=actor.get_username(), old_role=old_role, new_role='', action='deleted', reason=reason)
    event._history_user = actor
    event.save()
    user.delete()
