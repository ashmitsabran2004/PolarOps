"""Compatibility exports; access policy is defined only in accounts.permissions."""
from accounts.permissions import (
    ROLE_GROUPS,
    PolarDRFPermission as PolarRolePermission,
    can,
    has_role,
    user_role,
)

__all__ = ['ROLE_GROUPS', 'PolarRolePermission', 'can', 'has_role', 'user_role']
