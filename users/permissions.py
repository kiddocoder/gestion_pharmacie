"""
Users — DRF Permission Classes

Role-based and scope-based permission checks for ViewSets.

@file users/permissions.py
"""

from rest_framework.permissions import BasePermission


class IsActiveUser(BasePermission):
    """Requires user to be authenticated and have ACTIVE status."""

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and getattr(request.user, 'status', None) == 'ACTIVE'
        )


class HasRole(BasePermission):
    """
    Checks that the user holds one of the roles listed in
    ``view.required_roles``.

    Usage::

        class MyView(APIView):
            permission_classes = [IsActiveUser, HasRole]
            required_roles = ['NATIONAL_ADMIN', 'INSPECTOR']
    """

    def has_permission(self, request, view):
        required = getattr(view, 'required_roles', [])
        if not required:
            return True
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        return any(user.has_role(r) for r in required)


class HasScopedRole(BasePermission):
    """
    Checks role **and** scope. Views must provide:
        required_role    = 'INSPECTOR'
        required_scope   = 'PRIVATE'
    Optionally resolve entity_id from the request for row-level checks.
    """

    def has_permission(self, request, view):
        role = getattr(view, 'required_role', None)
        scope = getattr(view, 'required_scope', None)
        if not role or not scope:
            return True
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        return user.has_scoped_role(role, scope)

    def has_object_permission(self, request, view, obj):
        role = getattr(view, 'required_role', None)
        scope = getattr(view, 'required_scope', None)
        if not role or not scope:
            return True
        user = request.user
        if user.is_superuser:
            return True

        entity_id = getattr(obj, 'id', None)
        return user.has_scoped_role(role, scope, entity_id=str(entity_id) if entity_id else None)


class IsNationalAdmin(BasePermission):
    """Shortcut: user must be superuser or hold NATIONAL_ADMIN role."""

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        return user.is_superuser or user.has_role('NATIONAL_ADMIN')
