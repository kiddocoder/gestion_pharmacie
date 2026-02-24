"""
Geography — Service Layer

Query helpers for the administrative hierarchy.

@file geography/services.py
"""

from .models import AdministrativeLevel


class GeographyService:
    """Read-oriented service for administrative level queries."""

    @staticmethod
    def get_provinces():
        return AdministrativeLevel.objects.filter(level_type='PROVINCE').order_by('name')

    @staticmethod
    def get_children(parent_id):
        return AdministrativeLevel.objects.filter(parent_id=parent_id).order_by('name')

    @staticmethod
    def get_hierarchy(level_id) -> list[dict]:
        """Return the full parent chain from root to the given level."""
        try:
            level = AdministrativeLevel.objects.select_related(
                'parent__parent__parent',
            ).get(pk=level_id)
        except AdministrativeLevel.DoesNotExist:
            return []

        chain = []
        current = level
        while current:
            chain.insert(0, {
                'id': str(current.pk),
                'name': current.name,
                'code': current.code,
                'level_type': current.level_type,
            })
            current = current.parent
        return chain
