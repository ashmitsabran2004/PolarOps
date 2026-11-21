"""Central PolarOps role policy, object scope rules, and reusable view guards."""
from functools import wraps

from django.contrib.auth.mixins import AccessMixin
from django.core.exceptions import ImproperlyConfigured
from rest_framework.permissions import BasePermission

ADMINISTRATOR = "Administrator"
EXPEDITION_LEADER = "Expedition Leader"
LOGISTICS_OFFICER = "Logistics Officer"
FIELD_MEMBER = "Field Member"
ROLE_CHOICES = (ADMINISTRATOR, EXPEDITION_LEADER, LOGISTICS_OFFICER, FIELD_MEMBER)
ROLE_GROUPS = frozenset(ROLE_CHOICES)

# Each routable operation declares one key from this policy map.
PERMISSION_MAP = {
    "dashboard.view": ROLE_CHOICES,
    "expedition.view": ROLE_CHOICES,
    "expedition.create": (ADMINISTRATOR, EXPEDITION_LEADER),
    "expedition.edit": (ADMINISTRATOR, EXPEDITION_LEADER),
    "expedition.delete": (ADMINISTRATOR,),
    "record.delete": (ADMINISTRATOR,),
    "personnel.view": (ADMINISTRATOR, EXPEDITION_LEADER, LOGISTICS_OFFICER),
    "personnel.view.self": (FIELD_MEMBER,),
    "personnel.self": (FIELD_MEMBER,),
    "personnel.assign": (ADMINISTRATOR, EXPEDITION_LEADER),
    "personnel.manage": (ADMINISTRATOR,),
    "depot.view": ROLE_CHOICES,
    "depot.manage": (ADMINISTRATOR, LOGISTICS_OFFICER),
    "certification.view": (ADMINISTRATOR, EXPEDITION_LEADER, LOGISTICS_OFFICER),
    "certification.view.self": (FIELD_MEMBER,),
    "certification.manage": (ADMINISTRATOR,),
    "asset.view": ROLE_CHOICES,
    "asset.manage": (ADMINISTRATOR, LOGISTICS_OFFICER),
    "asset.checkout": (ADMINISTRATOR, LOGISTICS_OFFICER, FIELD_MEMBER),
    "asset.checkin": (ADMINISTRATOR, LOGISTICS_OFFICER, FIELD_MEMBER),
    "asset.force_checkin": (ADMINISTRATOR, EXPEDITION_LEADER),
    "inventory.view": ROLE_CHOICES,
    "inventory.manage": (ADMINISTRATOR, LOGISTICS_OFFICER),
    "inventory.usage": (FIELD_MEMBER,),
    "transport.view": ROLE_CHOICES,
    "transport.create": (ADMINISTRATOR, LOGISTICS_OFFICER),
    "transport.edit": (ADMINISTRATOR, LOGISTICS_OFFICER),
    "transport.approve": (ADMINISTRATOR, EXPEDITION_LEADER),
    "transport.delete": (ADMINISTRATOR,),
    "calculator.run": (ADMINISTRATOR, EXPEDITION_LEADER, LOGISTICS_OFFICER),
    "requisition.view": (ADMINISTRATOR, EXPEDITION_LEADER, LOGISTICS_OFFICER),
    "requisition.create": (ADMINISTRATOR, LOGISTICS_OFFICER),
    "requisition.submit": (ADMINISTRATOR, LOGISTICS_OFFICER),
    "requisition.approve": (ADMINISTRATOR, EXPEDITION_LEADER),
    "requisition.reject": (ADMINISTRATOR, EXPEDITION_LEADER),
    "requisition.fulfill": (ADMINISTRATOR, LOGISTICS_OFFICER),
    "requisition.delete": (ADMINISTRATOR,),
    "risk.view": ROLE_CHOICES,
    "risk.assess": (ADMINISTRATOR, EXPEDITION_LEADER),
    "risk.edit": (ADMINISTRATOR,),
    "risk.override": (ADMINISTRATOR, EXPEDITION_LEADER),
    "risk.configure": (ADMINISTRATOR,),
    "emergency.view": ROLE_CHOICES,
    "emergency.edit": (ADMINISTRATOR, EXPEDITION_LEADER),
    "sos.view": ROLE_CHOICES,
    "sos.submit": (FIELD_MEMBER,),
    "sos.update": (ADMINISTRATOR, EXPEDITION_LEADER),
    "sos.delete": (),
    "alerts.view": ROLE_CHOICES,
    "notification.read": ROLE_CHOICES,
    "report.manifest.export": (ADMINISTRATOR, EXPEDITION_LEADER),
    "report.risk.export": (ADMINISTRATOR, EXPEDITION_LEADER),
    "report.assets.export": (ADMINISTRATOR, EXPEDITION_LEADER, LOGISTICS_OFFICER),
    "report.inventory.export": (ADMINISTRATOR, EXPEDITION_LEADER, LOGISTICS_OFFICER),
    "report.transport.export": (ADMINISTRATOR, EXPEDITION_LEADER, LOGISTICS_OFFICER),
    "report.requisition.export": (ADMINISTRATOR, EXPEDITION_LEADER, LOGISTICS_OFFICER),
    "audit.view": (ADMINISTRATOR,),
    "user.manage": (ADMINISTRATOR,),
    "permission_matrix.view": (ADMINISTRATOR,),
    "profile.view": ROLE_CHOICES,
    "profile.edit.self": (FIELD_MEMBER,),
    "profile.edit": (ADMINISTRATOR,),
    "admin.site": (ADMINISTRATOR,),
    "api.expedition.read": ROLE_CHOICES,
    "api.expedition.write": (ADMINISTRATOR, EXPEDITION_LEADER),
    "api.asset.read": ROLE_CHOICES,
    "api.asset.write": (ADMINISTRATOR, LOGISTICS_OFFICER),
    "api.inventory.read": ROLE_CHOICES,
    "api.inventory.write": (ADMINISTRATOR, LOGISTICS_OFFICER),
    "api.alert.read": ROLE_CHOICES,
    "api.alert.write": (ADMINISTRATOR,),
    "api.token.issue": ROLE_CHOICES,
    "api.index.view": ROLE_CHOICES,
    "maintenance.view": ROLE_CHOICES,
    "maintenance.manage": (ADMINISTRATOR, LOGISTICS_OFFICER),
    "risk.weather": (ADMINISTRATOR, EXPEDITION_LEADER),
    "requisition.pdf": (ADMINISTRATOR, EXPEDITION_LEADER, LOGISTICS_OFFICER),
    "expedition.select": ROLE_CHOICES,
}


def user_role(user):
    """Return the user's sole PolarOps role; superusers are Administrators."""
    if not getattr(user, "is_authenticated", False):
        return None
    if getattr(user, "is_superuser", False):
        return ADMINISTRATOR
    names = set(user.groups.filter(name__in=ROLE_GROUPS).values_list("name", flat=True))
    return next(iter(names)) if len(names) == 1 else None


def has_role(user, *roles):
    """Check the single effective role, without querying group names elsewhere."""
    return user_role(user) in roles


def _expedition_for(obj):
    if obj is None:
        return None
    if obj.__class__.__name__ == "Expedition":
        return obj
    if hasattr(obj, "expedition"):
        return obj.expedition
    if hasattr(obj, "asset"):
        return getattr(obj.asset, "expedition", None)
    if hasattr(obj, "asset"):
        return getattr(obj.asset, "expedition", None)
    if hasattr(obj, "asset"):
        return getattr(obj.asset, "expedition", None)
    if hasattr(obj, "item"):
        return getattr(obj.item, "expedition", None)
    return None


def in_scope(user, obj):
    """Apply Leader and Field Member scope to an expedition or related record."""
    role = user_role(user)
    if role in (ADMINISTRATOR, LOGISTICS_OFFICER) or obj is None:
        return True
    expedition = _expedition_for(obj)
    if role == EXPEDITION_LEADER:
        if expedition is None:
            if hasattr(obj, "expeditions"):
                return obj.expeditions.filter(leader=user).exists()
            return False
        return expedition.leader_id == user.pk
    if role == FIELD_MEMBER:
        profile = getattr(user, "field_profile", None)
        if profile is None:
            return False
        if obj.__class__.__name__ == "Certification":
            return obj.profile.user_id == user.pk
        if obj is user or obj.__class__.__name__ == "PersonnelProfile":
            return getattr(obj, "user_id", None) == user.pk
        if expedition is None:
            if obj.__class__.__name__ == "Alert":
                return obj.recipient_id == user.pk
            return False
        assigned = list(profile.expeditions.values_list("pk", flat=True)[:2])
        return len(assigned) == 1 and assigned[0] == expedition.pk
    return False


def can(user, action, obj=None):
    """Answer whether ``user`` may perform a named action on an optional object."""
    allowed = PERMISSION_MAP.get(action)
    if allowed is None or not has_role(user, *allowed):
        return False
    role = user_role(user)
    if action.startswith("profile.edit") and obj is not None:
        owner_id = obj.pk if obj.__class__.__name__ == "User" else getattr(obj, 'user_id', None)
        if action == 'profile.edit.self':
            return role == FIELD_MEMBER and owner_id == user.pk
        if owner_id == user.pk:
            return False
    if action in ("requisition.approve", "requisition.reject", "transport.approve") and obj is not None:
        creator = getattr(obj, "requester_id", None) or getattr(obj, "created_by_id", None)
        if creator == user.pk:
            return False
    if obj is not None and role in (EXPEDITION_LEADER, FIELD_MEMBER):
        return in_scope(user, obj)
    return True


def scoped_queryset(user, queryset, expedition_lookup="expedition"):
    """Filter queryset to the Leader's or Field Member's assigned expeditions."""
    role = user_role(user)
    if role in (ADMINISTRATOR, LOGISTICS_OFFICER):
        return queryset
    if role == EXPEDITION_LEADER:
        if queryset.model.__name__ == "Expedition":
            return queryset.filter(leader=user)
        if queryset.model.__name__ == "User":
            return queryset.filter(field_profile__expeditions__leader=user).distinct()
        if queryset.model.__name__ == "StockMovement":
            return queryset.filter(item__expedition__leader=user)
        if queryset.model.__name__ == "MaintenanceRecord":
            return queryset.filter(asset__expedition__leader=user)
        if queryset.model.__name__ == "MaintenanceRecord":
            return queryset.filter(asset__expedition__leader=user)
        if queryset.model.__name__ == "MaintenanceRecord":
            return queryset.filter(asset__expedition__leader=user)
        if queryset.model.__name__ == "Certification":
            return queryset.filter(profile__expeditions__leader=user).distinct()
        if queryset.model.__name__ == "PersonnelProfile":
            return queryset.filter(expeditions__leader=user).distinct()
        if queryset.model.__name__ == "Alert":
            from django.db.models import Q
            return queryset.filter(Q(expedition__leader=user) | Q(recipient=user))
        return queryset.filter(**{f"{expedition_lookup}__leader": user})
    if role == FIELD_MEMBER:
        profile = getattr(user, "field_profile", None)
        # Keep the subquery model aligned with expedition foreign keys. Using
        # queryset.model.objects.none() here creates (for example) an Asset
        # queryset that Django correctly rejects for expedition__in lookups.
        from expeditions.models import Expedition
        missions = profile.expeditions.all() if profile else Expedition.objects.none()
        if profile and profile.expeditions.count() != 1:
            missions = Expedition.objects.none()
        if queryset.model.__name__ == "Expedition":
            return queryset.filter(pk__in=missions.values("pk"))
        if queryset.model.__name__ == "PersonnelProfile":
            return queryset.filter(user=user)
        if queryset.model.__name__ == "Certification":
            return queryset.filter(profile__user=user)
        if queryset.model.__name__ == "Alert":
            from django.db.models import Q
            return queryset.filter(Q(expedition__in=missions) | Q(recipient=user))
        if queryset.model.__name__ == "StockMovement":
            return queryset.filter(item__expedition__in=missions)
        if queryset.model.__name__ == "MaintenanceRecord":
            return queryset.filter(asset__expedition__in=missions)
        if queryset.model.__name__ == "MaintenanceRecord":
            return queryset.filter(asset__expedition__in=missions)
        if queryset.model.__name__ == "MaintenanceRecord":
            return queryset.filter(asset__expedition__in=missions)
        if queryset.model.__name__ == "Certification":
            return queryset.filter(profile__user=user)
        return queryset.filter(**{f"{expedition_lookup}__in": missions})
    return queryset.none()


class RoleRequiredMixin(AccessMixin):
    """Enforce the declared policy action and return a themed 403 for denials."""
    permission_action = None

    def get_permission_action(self):
        if not self.permission_action:
            raise ImproperlyConfigured(f"{self.__class__.__name__} must declare permission_action.")
        return self.permission_action

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not can(request.user, self.get_permission_action()):
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)


class ExpeditionScopedMixin:
    """Apply the centralized scope to list/detail querysets and write lookups."""
    expedition_lookup = "expedition"
    permission_action = None

    def get_queryset(self):
        from accounts.permissions import scoped_queryset
        return scoped_queryset(self.request.user, super().get_queryset(), self.expedition_lookup)

    def get_object(self, queryset=None):
        from django.core.exceptions import PermissionDenied
        action = self.get_permission_action() if hasattr(self, 'get_permission_action') else (self.permission_action or "")
        write = any(token in action for token in (
            '.create', '.edit', '.delete', '.manage', '.approve', '.reject',
            '.fulfill', '.submit', '.update', '.assess', '.override',
            '.checkout', '.checkin', '.usage', '.write',
        ))
        if write:
            base = queryset if queryset is not None else self.model._default_manager.all()
            lookup = self.get_queryset_kwargs()
            candidate = base.filter(**lookup).first()
            if candidate is not None and not in_scope(self.request.user, candidate):
                raise PermissionDenied
        return super().get_object(queryset=queryset)

    def get_queryset_kwargs(self):
        kwargs = {}
        pk = self.kwargs.get(self.pk_url_kwarg or "pk")
        slug = self.kwargs.get(self.slug_url_kwarg or "slug")
        if pk is not None:
            kwargs[self.pk_url_kwarg or "pk"] = pk
        elif slug is not None:
            kwargs[self.slug_field] = slug
        return kwargs


def role_required(action):
    """Guard a function view with the same action map used by class views."""
    def decorate(view_func):
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                from django.contrib.auth.views import redirect_to_login
                return redirect_to_login(request.get_full_path())
            if not can(request.user, action):
                from django.core.exceptions import PermissionDenied
                raise PermissionDenied
            return view_func(request, *args, **kwargs)
        wrapped.permission_action = action
        return wrapped
    return decorate


class PolarDRFPermission(BasePermission):
    """DRF-compatible permission using the central role map and object scope."""
    def has_permission(self, request, view):
        action = view.get_permission_action() if hasattr(view, "get_permission_action") else None
        return bool(action and can(request.user, action))

    def has_object_permission(self, request, view, obj):
        action = view.get_permission_action() if hasattr(view, "get_permission_action") else None
        return bool(action and can(request.user, action, obj))
