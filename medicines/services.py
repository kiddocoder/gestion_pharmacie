"""
Medicines — Service Layer

Business logic for the national medicine registry and lot management.
All state transitions, validations, and multi-step operations live here.

@file medicines/services.py
"""

import logging

from django.db import transaction
from django.utils import timezone

from core.constants import AUDIT_ACTION_STATUS_CHANGE
from core.exceptions import (
    BusinessRuleViolation,
    DuplicateResourceError,
    InvalidStateTransition,
    ResourceNotFoundError,
)
from core.services import AuditService

from .models import NationalLot, NationalMedicine

logger = logging.getLogger('pharmatrack')


class MedicineService:
    """Registry management for NationalMedicine."""

    @staticmethod
    @transaction.atomic
    def create_medicine(*, actor=None, **fields) -> NationalMedicine:
        medicine = NationalMedicine(**fields)
        medicine.full_clean()
        medicine.created_by = actor
        medicine.save()
        return medicine

    @staticmethod
    @transaction.atomic
    def update_medicine(*, medicine_id, actor=None, **fields) -> NationalMedicine:
        try:
            medicine = NationalMedicine.objects.select_for_update().get(
                pk=medicine_id, is_deleted=False,
            )
        except NationalMedicine.DoesNotExist:
            raise ResourceNotFoundError()

        old_snapshot = AuditService.snapshot(medicine)

        for field, value in fields.items():
            if hasattr(medicine, field) and field not in ('id', 'pk'):
                setattr(medicine, field, value)

        medicine.updated_by = actor
        medicine.full_clean()
        medicine.save()
        return medicine

    @staticmethod
    @transaction.atomic
    def block_medicine(*, medicine_id, reason: str = '', actor=None) -> NationalMedicine:
        """Block a medicine and cascade-block all its ACTIVE lots."""
        try:
            medicine = NationalMedicine.objects.select_for_update().get(
                pk=medicine_id, is_deleted=False,
            )
        except NationalMedicine.DoesNotExist:
            raise ResourceNotFoundError()

        if medicine.status == NationalMedicine.StatusChoices.BLOCKED:
            raise InvalidStateTransition(detail='Medicine is already blocked.')

        old_status = medicine.status
        medicine.status = NationalMedicine.StatusChoices.BLOCKED
        medicine.updated_by = actor
        medicine.save(update_fields=['status', 'updated_by', 'updated_at'])

        blocked_lots = medicine.lots.filter(
            status=NationalLot.StatusChoices.ACTIVE, is_deleted=False,
        ).update(status=NationalLot.StatusChoices.BLOCKED)

        AuditService.log(
            actor=actor,
            action=AUDIT_ACTION_STATUS_CHANGE,
            model_name='NationalMedicine',
            object_id=str(medicine.pk),
            old_values={'status': old_status},
            new_values={'status': 'BLOCKED', 'reason': reason, 'lots_blocked': blocked_lots},
        )
        logger.info(
            'Medicine %s blocked by %s. %d lots cascade-blocked.',
            medicine.pk, actor, blocked_lots,
        )
        return medicine

    @staticmethod
    @transaction.atomic
    def unblock_medicine(*, medicine_id, actor=None) -> NationalMedicine:
        try:
            medicine = NationalMedicine.objects.select_for_update().get(
                pk=medicine_id, is_deleted=False,
            )
        except NationalMedicine.DoesNotExist:
            raise ResourceNotFoundError()

        if medicine.status != NationalMedicine.StatusChoices.BLOCKED:
            raise InvalidStateTransition(detail='Medicine is not blocked.')

        medicine.status = NationalMedicine.StatusChoices.AUTHORIZED
        medicine.updated_by = actor
        medicine.save(update_fields=['status', 'updated_by', 'updated_at'])

        AuditService.log(
            actor=actor,
            action=AUDIT_ACTION_STATUS_CHANGE,
            model_name='NationalMedicine',
            object_id=str(medicine.pk),
            old_values={'status': 'BLOCKED'},
            new_values={'status': 'AUTHORIZED'},
        )
        return medicine


class LotService:
    """Lot lifecycle: creation, recall, auto-expiry."""

    VALID_LOT_TRANSITIONS = {
        'ACTIVE': {'BLOCKED', 'RECALLED'},
        'BLOCKED': {'ACTIVE'},
        'EXPIRED': set(),
        'RECALLED': set(),
    }

    @staticmethod
    @transaction.atomic
    def create_lot(*, actor=None, **fields) -> NationalLot:
        medicine = fields.get('medicine')
        if medicine and medicine.status == NationalMedicine.StatusChoices.BLOCKED:
            raise BusinessRuleViolation(
                detail='Cannot create a lot for a BLOCKED medicine.',
            )

        lot = NationalLot(**fields)
        lot.full_clean()
        lot.created_by = actor
        lot.save()
        return lot

    @staticmethod
    @transaction.atomic
    def update_lot(*, lot_id, actor=None, **fields) -> NationalLot:
        try:
            lot = NationalLot.objects.select_for_update().get(
                pk=lot_id, is_deleted=False,
            )
        except NationalLot.DoesNotExist:
            raise ResourceNotFoundError()

        immutable_fields = {'batch_number', 'medicine', 'manufacturing_date', 'expiry_date', 'quantity_imported'}
        for field in immutable_fields:
            if field in fields and fields[field] != getattr(lot, field):
                raise BusinessRuleViolation(
                    detail=f'Cannot modify immutable lot field: {field}.',
                )

        for field, value in fields.items():
            if field not in immutable_fields and hasattr(lot, field) and field not in ('id', 'pk'):
                setattr(lot, field, value)

        lot.updated_by = actor
        lot.save()
        return lot

    @classmethod
    @transaction.atomic
    def recall_lot(cls, *, lot_id, reason: str, actor=None) -> NationalLot:
        try:
            lot = NationalLot.objects.select_for_update().get(
                pk=lot_id, is_deleted=False,
            )
        except NationalLot.DoesNotExist:
            raise ResourceNotFoundError()

        allowed = cls.VALID_LOT_TRANSITIONS.get(lot.status, set())
        if 'RECALLED' not in allowed:
            raise InvalidStateTransition(
                detail=f'Cannot recall lot with status {lot.status}.',
            )

        old_status = lot.status
        lot.status = NationalLot.StatusChoices.RECALLED
        lot.recall_reason = reason
        lot.updated_by = actor
        lot.save(update_fields=['status', 'recall_reason', 'updated_by', 'updated_at'])

        AuditService.log(
            actor=actor,
            action=AUDIT_ACTION_STATUS_CHANGE,
            model_name='NationalLot',
            object_id=str(lot.pk),
            old_values={'status': old_status},
            new_values={'status': 'RECALLED', 'reason': reason},
        )
        return lot

    @staticmethod
    def expire_overdue_lots() -> int:
        """
        Bulk-expire lots past their expiry_date. Called daily by Celery beat.
        Returns the count of newly expired lots.
        """
        today = timezone.now().date()
        qs = NationalLot.objects.filter(
            status=NationalLot.StatusChoices.ACTIVE,
            expiry_date__lt=today,
            is_deleted=False,
        )
        count = qs.update(status=NationalLot.StatusChoices.EXPIRED)
        if count:
            logger.info('Auto-expired %d lots past expiry date.', count)
        return count

    @staticmethod
    def get_expiring_soon(days: int = 30):
        """Return lots expiring within the given number of days."""
        cutoff = timezone.now().date() + timezone.timedelta(days=days)
        return NationalLot.objects.filter(
            status=NationalLot.StatusChoices.ACTIVE,
            expiry_date__lte=cutoff,
            is_deleted=False,
        ).select_related('medicine').order_by('expiry_date')
