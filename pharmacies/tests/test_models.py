"""
Tests — Pharmacy and PharmacyDocument models.

@file pharmacies/tests/test_models.py
"""

import pytest

from pharmacies.models import Pharmacy, PharmacyDocument
from tests.factories import CommuneFactory, PharmacyDocumentFactory, PharmacyFactory


pytestmark = pytest.mark.django_db


class TestPharmacyModel:

    def test_create_pharmacy(self):
        commune = CommuneFactory()
        pharmacy = PharmacyFactory(
            name='Test Pharmacy',
            pharmacy_type=Pharmacy.TypeChoices.WHOLESALER,
            administrative_level=commune,
        )
        assert pharmacy.pk is not None
        assert pharmacy.status == Pharmacy.StatusChoices.PENDING
        assert pharmacy.pharmacy_type == Pharmacy.TypeChoices.WHOLESALER

    def test_str_includes_name_and_code(self):
        pharmacy = PharmacyFactory(name='My Pharmacy', national_code='PH-BJM-0001')
        assert 'My Pharmacy' in str(pharmacy)
        assert 'PH-BJM-0001' in str(pharmacy)

    def test_str_without_code(self):
        pharmacy = PharmacyFactory(name='No Code Yet', national_code='')
        assert 'No Code Yet' in str(pharmacy)


class TestPharmacyDocumentModel:

    def test_create_document(self):
        pharmacy = PharmacyFactory()
        doc = PharmacyDocumentFactory(
            pharmacy=pharmacy,
            document_type=PharmacyDocument.DocumentTypeChoices.LICENSE,
        )
        assert doc.pk is not None
        assert doc.status == PharmacyDocument.StatusChoices.PENDING

    def test_str_includes_type_and_pharmacy(self):
        pharmacy = PharmacyFactory(name='Pharma X')
        doc = PharmacyDocumentFactory(pharmacy=pharmacy)
        assert 'License' in str(doc) or 'LICENSE' in str(doc)
        assert 'Pharma X' in str(doc)
