"""
Medicines — Permissions

Access control for the medicine registry. Write operations restricted
to NATIONAL_ADMIN and NATIONAL_PHARMACIST roles.

@file medicines/permissions.py
"""

from rest_framework.permissions import BasePermission


class CanModifyMedicine(BasePermission):
    """Read is open to authenticated users; write requires national roles."""

    def has_permission(self, request, view):
        if request.method in ('GET', 'HEAD', 'OPTIONS'):
            return True
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        return user.has_role('NATIONAL_ADMIN') or user.has_role('NATIONAL_PHARMACIST')


class CanBlockMedicine(BasePermission):
    """Only NATIONAL_ADMIN can block/unblock medicines."""

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        return user.is_superuser or user.has_role('NATIONAL_ADMIN')


class CanRecallLot(BasePermission):
    """Only NATIONAL_ADMIN or NATIONAL_PHARMACIST can recall lots."""

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        return user.has_role('NATIONAL_ADMIN') or user.has_role('NATIONAL_PHARMACIST')
