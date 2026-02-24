"""
Geography — Model Tests

Tests for AdministrativeLevel constraints and hierarchy.

@file geography/tests/test_models.py
"""

import pytest
from django.db import IntegrityError

from geography.models import AdministrativeLevel
from tests.factories import CommuneFactory, ProvinceFactory, ZoneFactory


@pytest.mark.django_db
class TestAdministrativeLevel:
    def test_create_province(self):
        province = ProvinceFactory(name='Bujumbura')
        assert province.level_type == 'PROVINCE'
        assert province.parent is None

    def test_create_commune_with_province_parent(self):
        province = ProvinceFactory()
        commune = CommuneFactory(parent=province)
        assert commune.parent == province

    def test_create_zone_with_commune_parent(self):
        commune = CommuneFactory()
        zone = ZoneFactory(parent=commune)
        assert zone.parent == commune

    def test_full_path(self):
        province = ProvinceFactory(name='Bubanza')
        commune = CommuneFactory(name='Bubanza Commune', parent=province)
        zone = ZoneFactory(name='Bubanza Zone', parent=commune)
        assert zone.full_path == 'Bubanza > Bubanza Commune > Bubanza Zone'

    def test_province_must_not_have_parent(self):
        """The DB constraint should prevent a province with a parent."""
        other_province = ProvinceFactory()
        with pytest.raises(IntegrityError):
            AdministrativeLevel.objects.create(
                name='Bad Province',
                code='BAD-PRV',
                level_type='PROVINCE',
                parent=other_province,
            )

    def test_commune_must_have_parent(self):
        """The DB constraint should prevent a commune without a parent."""
        with pytest.raises(IntegrityError):
            AdministrativeLevel.objects.create(
                name='Orphan Commune',
                code='ORPHAN-COM',
                level_type='COMMUNE',
                parent=None,
            )

    def test_unique_code(self):
        ProvinceFactory(code='UNIQUE-001')
        with pytest.raises(IntegrityError):
            ProvinceFactory(code='UNIQUE-001')

    def test_get_descendants(self):
        province = ProvinceFactory()
        c1 = CommuneFactory(parent=province)
        c2 = CommuneFactory(parent=province)
        z1 = ZoneFactory(parent=c1)
        descendants = province.get_descendants()
        assert len(descendants) == 3
        assert c1 in descendants
        assert c2 in descendants
        assert z1 in descendants
