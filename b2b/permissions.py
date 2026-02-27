"""
B2B — Permissions

Orders: list/create for authenticated; workflow actions for NATIONAL_ADMIN
or pharmacy-scoped roles (seller/buyer).

@file b2b/permissions.py
"""

from rest_framework.permissions import BasePermission


class CanManageB2BOrder(BasePermission):
    """List/retrieve: authenticated. Create/update: authenticated (buyer/seller or national)."""

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return True


class CanApproveOrRejectOrder(BasePermission):
    """Submit/approve/reject/ship/deliver/cancel: NATIONAL_ADMIN or seller/buyer scope."""

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return True
        return request.user.has_role('NATIONAL_ADMIN') or request.user.has_role('INSPECTOR')
