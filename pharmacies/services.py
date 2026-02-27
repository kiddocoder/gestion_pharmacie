"""
Pharmacies — Service Layer

Business logic for pharmacy lifecycle: creation with national_code generation,
approval/suspend workflow, and QR code generation on approval.
All status transitions are audited.

@file pharmacies/services.py
"""

import io
import json
import logging

import qrcode
from django.db import transaction
from django.utils import timezone

from core.constants import AUDIT_ACTION_STATUS_CHANGE
from core.exceptions import (
    BusinessRuleViolation,
    InvalidStateTransition,
    ResourceNotFoundError,
)
from core.services import AuditService
from geography.models import AdministrativeLevel

from .models import Pharmacy, PharmacyDocument

logger = logging.getLogger('pharmatrack')


# Valid status transitions (from -> set of allowed to)
PHARMACY_STATUS_TRANSITIONS = {
    Pharmacy.StatusChoices.PENDING: {Pharmacy.StatusChoices.APPROVED, Pharmacy.StatusChoices.ILLEGAL},
    Pharmacy.StatusChoices.APPROVED: {Pharmacy.StatusChoices.SUSPENDED},
    Pharmacy.StatusChoices.SUSPENDED: {Pharmacy.StatusChoices.APPROVED, Pharmacy.StatusChoices.ILLEGAL},
    Pharmacy.StatusChoices.ILLEGAL: set(),
}


class PharmacyService:
    """Pharmacy lifecycle: create, approve, suspend, national_code, QR."""

    @staticmethod
    def _get_province_code_for_commune(commune: AdministrativeLevel) -> str:
        """Return the province code for a commune-level administrative level."""
        if commune.level_type != AdministrativeLevel.LevelType.COMMUNE:
            raise BusinessRuleViolation(
                detail='Pharmacy administrative_level must be a commune.',
            )
        parent = commune.parent
        if not parent or parent.level_type != AdministrativeLevel.LevelType.PROVINCE:
            raise BusinessRuleViolation(
                detail='Commune must have a province parent.',
            )
        return parent.code or parent.name[:3].upper()

    @staticmethod
    @transaction.atomic
    def _generate_national_code(pharmacy: Pharmacy) -> str:
        """
        Generate unique national_code PH-{PROV}-XXXX for the pharmacy.
        Uses commune's province code and next sequence in that province.
        """
        if pharmacy.national_code:
            return pharmacy.national_code
        commune = pharmacy.administrative_level
        province_code = PharmacyService._get_province_code_for_commune(commune)
        # Normalize for prefix: take first 3 chars of code or name
        prefix = (province_code or commune.name[:3])[:3].upper().replace(' ', '_')

        # Next sequence: max(XXXX) among pharmacies in same province with PH-{prefix}-XXXX
        province_id = commune.parent_id
        same_province = Pharmacy.objects.filter(
            is_deleted=False,
            administrative_level__parent_id=province_id,
        ).exclude(national_code='')
        max_seq = 0
        for nc in same_province.values_list('national_code', flat=True):
            if nc and nc.startswith(f'PH-{prefix}-'):
                try:
                    max_seq = max(max_seq, int(nc.split('-')[-1]))
                except (ValueError, IndexError):
                    pass
        seq = max_seq + 1
        code = f'PH-{prefix}-{seq:04d}'
        pharmacy.national_code = code
        pharmacy.save(update_fields=['national_code'])
        return code

    @staticmethod
    @transaction.atomic
    def create_pharmacy(*, actor=None, **fields) -> Pharmacy:
        """Create a pharmacy; national_code is set on first save (before approval)."""
        pharmacy = Pharmacy(**fields)
        pharmacy.full_clean()
        pharmacy.created_by = actor
        pharmacy.save()
        PharmacyService._generate_national_code(pharmacy)
        return pharmacy

    @staticmethod
    @transaction.atomic
    def update_pharmacy(*, pharmacy_id, actor=None, **fields) -> Pharmacy:
        """Update pharmacy; status and national_code are not writable directly."""
        try:
            pharmacy = Pharmacy.objects.select_for_update().get(
                pk=pharmacy_id, is_deleted=False,
            )
        except Pharmacy.DoesNotExist:
            raise ResourceNotFoundError()

        read_only = {'status', 'national_code', 'id'}
        for key in read_only:
            fields.pop(key, None)

        old_snapshot = AuditService.snapshot(pharmacy)
        for field, value in fields.items():
            if hasattr(pharmacy, field):
                setattr(pharmacy, field, value)
        pharmacy.updated_by = actor
        pharmacy.full_clean()
        pharmacy.save()
        return pharmacy

    @staticmethod
    def _require_documents_approved(pharmacy: Pharmacy) -> None:
        """Raise if pharmacy does not have at least one approved document (e.g. license)."""
        approved = pharmacy.documents.filter(
            is_deleted=False,
            status=PharmacyDocument.StatusChoices.APPROVED,
        ).exists()
        if not approved:
            raise BusinessRuleViolation(
                detail='At least one document must be approved before approving the pharmacy.',
            )

    @staticmethod
    def _generate_qr_code(pharmacy: Pharmacy) -> None:
        """Generate QR image encoding pharmacy_id, national_code, name, type; save to storage."""
        payload = {
            'pharmacy_id': str(pharmacy.pk),
            'national_code': pharmacy.national_code,
            'name': pharmacy.name,
            'type': pharmacy.pharmacy_type,
        }
        data = json.dumps(payload, sort_keys=True)
        img = qrcode.make(data)
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)
        filename = f'pharmacy_{pharmacy.pk}_qr.png'
        pharmacy.qr_code.save(filename, buf, save=True)

    @staticmethod
    @transaction.atomic
    def approve_pharmacy(*, pharmacy_id, reason: str = '', actor=None) -> Pharmacy:
        """Transition pharmacy to APPROVED; require approved documents; generate QR."""
        try:
            pharmacy = Pharmacy.objects.select_for_update().get(
                pk=pharmacy_id, is_deleted=False,
            )
        except Pharmacy.DoesNotExist:
            raise ResourceNotFoundError()

        old_status = pharmacy.status
        allowed = PHARMACY_STATUS_TRANSITIONS.get(old_status, set())
        if Pharmacy.StatusChoices.APPROVED not in allowed:
            raise InvalidStateTransition(
                detail=f'Cannot approve from status {old_status}.',
            )

        PharmacyService._require_documents_approved(pharmacy)
        pharmacy.status = Pharmacy.StatusChoices.APPROVED
        pharmacy.updated_by = actor
        pharmacy.save(update_fields=['status', 'updated_by', 'updated_at'])
        PharmacyService._generate_qr_code(pharmacy)

        AuditService.log(
            actor=actor,
            action=AUDIT_ACTION_STATUS_CHANGE,
            model_name='Pharmacy',
            object_id=str(pharmacy.pk),
            old_values={'status': old_status},
            new_values={'status': 'APPROVED', 'reason': reason or ''},
        )
        logger.info('Pharmacy %s approved by %s.', pharmacy_id, actor)
        return pharmacy

    @staticmethod
    @transaction.atomic
    def suspend_pharmacy(*, pharmacy_id, reason: str = '', actor=None) -> Pharmacy:
        """Transition pharmacy from APPROVED to SUSPENDED."""
        try:
            pharmacy = Pharmacy.objects.select_for_update().get(
                pk=pharmacy_id, is_deleted=False,
            )
        except Pharmacy.DoesNotExist:
            raise ResourceNotFoundError()

        old_status = pharmacy.status
        allowed = PHARMACY_STATUS_TRANSITIONS.get(old_status, set())
        if Pharmacy.StatusChoices.SUSPENDED not in allowed:
            raise InvalidStateTransition(
                detail=f'Cannot suspend from status {old_status}.',
            )

        pharmacy.status = Pharmacy.StatusChoices.SUSPENDED
        pharmacy.updated_by = actor
        pharmacy.save(update_fields=['status', 'updated_by', 'updated_at'])

        AuditService.log(
            actor=actor,
            action=AUDIT_ACTION_STATUS_CHANGE,
            model_name='Pharmacy',
            object_id=str(pharmacy.pk),
            old_values={'status': old_status},
            new_values={'status': 'SUSPENDED', 'reason': reason or ''},
        )
        logger.info('Pharmacy %s suspended by %s.', pharmacy_id, actor)
        return pharmacy

    @staticmethod
    @transaction.atomic
    def set_pharmacy_illegal(*, pharmacy_id, reason: str = '', actor=None) -> Pharmacy:
        """Transition pharmacy to ILLEGAL (from PENDING or SUSPENDED)."""
        try:
            pharmacy = Pharmacy.objects.select_for_update().get(
                pk=pharmacy_id, is_deleted=False,
            )
        except Pharmacy.DoesNotExist:
            raise ResourceNotFoundError()

        old_status = pharmacy.status
        allowed = PHARMACY_STATUS_TRANSITIONS.get(old_status, set())
        if Pharmacy.StatusChoices.ILLEGAL not in allowed:
            raise InvalidStateTransition(
                detail=f'Cannot set ILLEGAL from status {old_status}.',
            )

        pharmacy.status = Pharmacy.StatusChoices.ILLEGAL
        pharmacy.updated_by = actor
        pharmacy.save(update_fields=['status', 'updated_by', 'updated_at'])

        AuditService.log(
            actor=actor,
            action=AUDIT_ACTION_STATUS_CHANGE,
            model_name='Pharmacy',
            object_id=str(pharmacy.pk),
            old_values={'status': old_status},
            new_values={'status': 'ILLEGAL', 'reason': reason or ''},
        )
        return pharmacy


class PharmacyDocumentService:
    """Pharmacy document upload and status."""

    @staticmethod
    @transaction.atomic
    def create_document(*, pharmacy_id, actor=None, **fields) -> PharmacyDocument:
        doc = PharmacyDocument(pharmacy_id=pharmacy_id, **fields)
        doc.full_clean()
        doc.created_by = actor
        doc.save()
        return doc

    @staticmethod
    @transaction.atomic
    def update_document(*, document_id, actor=None, **fields) -> PharmacyDocument:
        try:
            doc = PharmacyDocument.objects.select_for_update().get(
                pk=document_id, is_deleted=False,
            )
        except PharmacyDocument.DoesNotExist:
            raise ResourceNotFoundError()

        for key in ('pharmacy', 'id'):
            fields.pop(key, None)
        for field, value in fields.items():
            if hasattr(doc, field):
                setattr(doc, field, value)
        doc.updated_by = actor
        doc.save()
        return doc
