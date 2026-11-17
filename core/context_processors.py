from django.db.models import OuterRef, Q, Subquery

from accounts.permissions import ADMINISTRATOR, ROLE_CHOICES, can, scoped_queryset, user_role
from core.models import Alert
from core.scope import available_expeditions, selected_expedition

THEMES = {
    'antarctica': 'Antarctica', 'arctic': 'Arctic', 'himalaya': 'Himalaya / High altitude',
    'subantarctic': 'Subantarctic / Sea voyage', 'greenland': 'Greenland / Tundra',
}


def polar_theme(request):
    user = request.user
    authenticated = user.is_authenticated
    expeditions = available_expeditions(user) if authenticated else []
    selected = selected_expedition(request) if authenticated else None
    theme = selected.region if selected else 'antarctica'
    preview = request.GET.get('theme')
    if preview in THEMES and can(user, 'permission_matrix.view'):
        theme = preview
    role = user_role(user) if authenticated else None
    notifications = Alert.objects.none()
    badge = {'score': 0, 'verdict': 'NO DATA'}
    if authenticated and role:
        notifications = scoped_queryset(
            user,
            Alert.objects.filter(Q(recipient=user) | Q(recipient__isnull=True)).exclude(receipts__user=user),
        ).select_related('expedition')
        if selected:
            notifications = notifications.filter(Q(expedition=selected) | Q(expedition__isnull=True) | Q(recipient=user))
        from risk.models import RiskAssessment
        latest_ids = RiskAssessment.objects.filter(expedition_id=OuterRef('expedition_id')).order_by('-assessed_at').values('pk')[:1]
        qs = RiskAssessment.objects.filter(expedition__in=expeditions, pk__in=Subquery(latest_ids))
        assessments = list(qs.filter(expedition=selected)) if selected else list(qs)
        if assessments:
            assessment = max(assessments, key=lambda item: item.score)
            badge = {'score': assessment.score, 'verdict': assessment.verdict}
    return {
        'active_expedition': selected, 'selected_expedition': selected,
        'expedition_scope_all': selected is None,
        'expedition_scope_label': selected.name if selected else 'All expeditions',
        'available_expeditions': expeditions,
        'theme': theme, 'theme_label': THEMES.get(theme, 'Antarctica'),
        'available_themes': THEMES, 'role_name': role,
        'is_administrator': role == ADMINISTRATOR,
        'is_field_member': role == 'Field Member',
        'is_ops_manager': role in ('Administrator', 'Expedition Leader', 'Logistics Officer'),
        'unread_alert_count': notifications.count(),
        'recent_notifications': notifications[:6], 'risk_badge': badge,
    }
