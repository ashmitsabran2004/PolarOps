"""Database-level safeguards for the single-role and final Administrator rules."""
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.db.models.signals import m2m_changed, pre_save
from django.dispatch import receiver

from accounts.permissions import ADMINISTRATOR, ROLE_GROUPS

User = get_user_model()
ROLE_GROUP_IDS = lambda: set(Group.objects.filter(name__in=ROLE_GROUPS).values_list('pk', flat=True))


def active_admin_count(exclude_pk=None):
    qs = User.objects.filter(is_active=True)
    if exclude_pk:
        # A superuser cannot be demoted by a role group change, so count it as admin separately.
        role_admins = qs.filter(groups__name=ADMINISTRATOR).exclude(pk=exclude_pk).distinct().count()
        superusers = qs.filter(is_superuser=True).exclude(pk=exclude_pk).count()
        return role_admins + superusers
    role_admins = qs.filter(groups__name=ADMINISTRATOR).distinct().count()
    superusers = qs.filter(is_superuser=True).count()
    return role_admins + superusers


@receiver(pre_save, sender=User)
def protect_last_admin_deactivation(sender, instance, **kwargs):
    if not instance.pk:
        return
    previous = sender.objects.filter(pk=instance.pk).first()
    if previous and previous.is_active and not instance.is_active:
        is_admin = previous.is_superuser or previous.groups.filter(name=ADMINISTRATOR).exists()
        if is_admin and active_admin_count(exclude_pk=instance.pk) == 0:
            raise ValidationError('The last active Administrator cannot be deactivated.')


@receiver(m2m_changed, sender=User.groups.through)
def enforce_one_role_and_protect_last_admin(sender, instance, action, reverse, model, pk_set, **kwargs):
    if reverse or not isinstance(instance, User):
        return
    role_ids = ROLE_GROUP_IDS()
    if action == 'pre_add':
        current = set(instance.groups.filter(pk__in=role_ids).values_list('pk', flat=True))
        pending = set(pk_set or ()) & role_ids
        if len(current | pending) > 1:
            raise ValidationError('A user must have exactly one PolarOps role group.')
    if action in ('pre_remove', 'pre_clear'):
        current_roles = set(instance.groups.filter(pk__in=role_ids).values_list('pk', flat=True))
        removing_admin = any(group.name == ADMINISTRATOR for group in model.objects.filter(pk__in=current_roles & set(pk_set or current_roles)))
        if removing_admin and instance.is_active and not instance.is_superuser and active_admin_count(exclude_pk=instance.pk) == 0:
            raise ValidationError('The last active Administrator cannot be demoted.')
