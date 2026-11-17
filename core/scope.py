"""Session selection and queryset helpers backed by centralized RBAC scope."""
from django.core.exceptions import PermissionDenied

from accounts.permissions import scoped_queryset, user_role

SESSION_KEY = 'polarops_expedition_id'


def available_expeditions(user):
    from expeditions.models import Expedition
    return scoped_queryset(
        user,
        Expedition.objects.select_related('leader', 'contingency').prefetch_related('team', 'assets'),
    )


def selected_expedition(request, *, strict=False):
    selected_id = request.session.get(SESSION_KEY)
    if not selected_id:
        return None
    expedition = available_expeditions(request.user).filter(pk=selected_id).first()
    if expedition is None:
        request.session.pop(SESSION_KEY, None)
        if strict:
            raise PermissionDenied('The selected expedition is unavailable to this account.')
    return expedition


def scope_model_queryset(request, model, queryset):
    """Respect the active expedition selector and role's immutable access scope."""
    selected = selected_expedition(request)
    base = scoped_queryset(request.user, queryset)
    if selected is None:
        return base
    name = model.__name__
    if name == 'Expedition':
        return base.filter(pk=selected.pk)
    if name == 'PersonnelProfile':
        return base.filter(expeditions=selected).distinct()
    if name == 'Certification':
        return base.filter(profile__expeditions=selected).distinct()
    if name == 'StockMovement':
        return base.filter(item__expedition=selected)
    try:
        model._meta.get_field('expedition')
    except Exception:
        return base
    return base.filter(expedition=selected)
