"""
Tests — PharmacyService and PharmacyDocumentService.

@file pharmacies/tests/test_services.py
"""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from core.exceptions import BusinessRuleViolation, InvalidStateTransition, ResourceNotFoundError
from pharmacies.models import Pharmacy, PharmacyDocument
from pharmacies.services import PharmacyDocumentService, PharmacyService
from tests.factories import (
    CommuneFactory,
    PharmacyDocumentFactory,
    PharmacyFactory,
    SuperuserFactory,
)


pytestmark = pytest.mark.django_db


class TestPharmacyService:

    def test_create_pharmacy_assigns_national_code(self):
        commune = CommuneFactory(parent__code='BJM')
        pharmacy = PharmacyService.create_pharmacy(
            name='New Pharma',
            pharmacy_type=Pharmacy.TypeChoices.RETAILER,
            administrative_level=commune,
        )
        assert pharmacy.national_code
        assert pharmacy.national_code.startswith('PH-')
        assert '0001' in pharmacy.national_code or '0002' in pharmacy.national_code

    def test_approve_requires_approved_document(self):
        pharmacy = PharmacyFactory(status=Pharmacy.StatusChoices.PENDING)
        with pytest.raises(BusinessRuleViolation) as exc_info:
            PharmacyService.approve_pharmacy(pharmacy_id=pharmacy.pk, actor=SuperuserFactory())
        assert 'document' in str(exc_info.value).lower()

    def test_approve_success_with_approved_document(self):
        pharmacy = PharmacyFactory(status=Pharmacy.StatusChoices.PENDING)
        PharmacyDocumentFactory(
            pharmacy=pharmacy,
            status=PharmacyDocument.StatusChoices.APPROVED,
        )
        actor = SuperuserFactory()
        approved = PharmacyService.approve_pharmacy(pharmacy_id=pharmacy.pk, actor=actor)
        assert approved.status == Pharmacy.StatusChoices.APPROVED
        approved.refresh_from_db()
        assert approved.qr_code

    def test_suspend_from_approved(self):
        pharmacy = PharmacyFactory(status=Pharmacy.StatusChoices.APPROVED)
        suspended = PharmacyService.suspend_pharmacy(
            pharmacy_id=pharmacy.pk,
            reason='Inspection',
            actor=SuperuserFactory(),
        )
        assert suspended.status == Pharmacy.StatusChoices.SUSPENDED

    def test_suspend_from_pending_raises(self):
        pharmacy = PharmacyFactory(status=Pharmacy.StatusChoices.PENDING)
        with pytest.raises(InvalidStateTransition):
            PharmacyService.suspend_pharmacy(pharmacy_id=pharmacy.pk, actor=SuperuserFactory())

    def test_approve_from_suspended(self):
        pharmacy = PharmacyFactory(status=Pharmacy.StatusChoices.SUSPENDED)
        PharmacyDocumentFactory(pharmacy=pharmacy, status=PharmacyDocument.StatusChoices.APPROVED)
        approved = PharmacyService.approve_pharmacy(pharmacy_id=pharmacy.pk, actor=SuperuserFactory())
        assert approved.status == Pharmacy.StatusChoices.APPROVED

    def test_update_pharmacy(self):
        pharmacy = PharmacyFactory(name='Old Name')
        updated = PharmacyService.update_pharmacy(
            pharmacy_id=pharmacy.pk,
            name='New Name',
            actor=SuperuserFactory(),
        )
        assert updated.name == 'New Name'

    def test_update_nonexistent_raises(self):
        import uuid
        with pytest.raises(ResourceNotFoundError):
            PharmacyService.update_pharmacy(pharmacy_id=uuid.uuid4(), name='X', actor=SuperuserFactory())


class TestPharmacyDocumentService:

    def test_create_document(self):
        pharmacy = PharmacyFactory()
        doc = PharmacyDocumentService.create_document(
            pharmacy_id=pharmacy.pk,
            document_type=PharmacyDocument.DocumentTypeChoices.LICENSE,
            file=SimpleUploadedFile('lic.pdf', b'content', content_type='application/pdf'),
            actor=SuperuserFactory(),
        )
        assert doc.pk is not None
        assert doc.pharmacy_id == pharmacy.pk
        assert doc.status == PharmacyDocument.StatusChoices.PENDING
