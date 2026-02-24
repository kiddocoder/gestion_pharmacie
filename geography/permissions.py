"""
Geography — Permissions

Geography data is mostly read-only. Only NATIONAL_ADMIN can modify.

@file geography/permissions.py
"""

from rest_framework.permissions import BasePermission


class CanModifyGeography(BasePermission):
    """Only national admins and superusers can create/edit geography."""

    def has_permission(self, request, view):
        if request.method in ('GET', 'HEAD', 'OPTIONS'):
            return True
        user = request.user
        return user.is_superuser or user.has_role('NATIONAL_ADMIN')
