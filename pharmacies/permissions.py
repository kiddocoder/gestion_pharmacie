"""
Pharmacies — Permissions

Approval and suspend restricted to NATIONAL_ADMIN or INSPECTOR with
correct scope. List/create for authenticated users with appropriate roles.

@file pharmacies/permissions.py
"""

from rest_framework.permissions import BasePermission


class CanManagePharmacy(BasePermission):
    """Read (list/retrieve) allowed for authenticated; create/update by national/pharmacy roles."""

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.method in ('GET', 'HEAD', 'OPTIONS'):
            return True
        if request.user.is_superuser:
            return True
        return request.user.has_role('NATIONAL_ADMIN') or request.user.has_role('INSPECTOR')


class CanApproveOrSuspendPharmacy(BasePermission):
    """Only NATIONAL_ADMIN or INSPECTOR (with scope) can approve or suspend."""

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return True
        return request.user.has_role('NATIONAL_ADMIN') or request.user.has_role('INSPECTOR')

    def has_object_permission(self, request, view, obj):
        if request.user.is_superuser:
            return True
        if request.user.has_role('NATIONAL_ADMIN'):
            return True
        # INSPECTOR: scope check (e.g. province) — optional entity_id on UserRole
        return request.user.has_role('INSPECTOR')
