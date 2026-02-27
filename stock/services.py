"""
Stock — Service Layer

Movement-based stock: get_balance, record_movement, process_b2b_transaction,
process_retail_sale. All outbound movements check balance under advisory lock.
INSERT ONLY — never update or delete StockMovement.

@file stock/services.py
"""

import hashlib
import logging
from typing import Literal
from uuid import UUID

from django.db import connection, transaction
from django.db.models import Case, IntegerField, Sum, Value, When

from core.constants import AUDIT_ACTION_CREATE
from core.exceptions import BusinessRuleViolation, InsufficientStockError, ResourceNotFoundError
from core.services import AuditService
from medicines.models import NationalLot

from .models import StockMovement

logger = logging.getLogger('pharmatrack')

EntityType = Literal['PHARMACY', 'PUBLIC_FACILITY']
MovementType = str  # StockMovement.MovementType values

INBOUND_TYPES = {'IMPORT', 'B2B_IN', 'RETURN', 'ADJUSTMENT'}
OUTBOUND_TYPES = {'B2B_OUT', 'SALE', 'RECALL_REMOVAL'}


def _advisory_lock_key(entity_type: str, entity_id: UUID, lot_id: UUID) -> int:
    """Stable bigint key for PostgreSQL advisory lock (same entity+lot = same key)."""
    raw = f'{entity_type}:{entity_id}:{lot_id}'.encode()
    h = hashlib.sha256(raw).digest()[:8]
    return int.from_bytes(h, 'big') % (2**63)


def _get_balance_orm(entity_type: str, entity_id: UUID, lot_id: UUID) -> int:
    """Compute current stock from movements using ORM (inbound - outbound)."""
    qs = StockMovement.objects.filter(
        entity_type=entity_type,
        entity_id=entity_id,
        lot_id=lot_id,
    )
    inbound = Sum(
        Case(
            When(movement_type__in=INBOUND_TYPES, then='quantity'),
            default=Value(0),
            output_field=IntegerField(),
        ),
    )
    outbound = Sum(
        Case(
            When(movement_type__in=OUTBOUND_TYPES, then='quantity'),
            default=Value(0),
            output_field=IntegerField(),
        ),
    )
    result = qs.aggregate(
        in_sum=inbound,
        out_sum=outbound,
    )
    in_sum = result['in_sum'] or 0
    out_sum = result['out_sum'] or 0
    return in_sum - out_sum


class StockService:
    """Movement-based stock: balance computation and recorded movements."""

    @staticmethod
    def get_balance(
        entity_type: str,
        entity_id: UUID,
        lot_id: UUID,
    ) -> int:
        """Return current stock for (entity_type, entity_id, lot)."""
        return _get_balance_orm(entity_type, str(entity_id), lot_id)

    @staticmethod
    @transaction.atomic
    def record_movement(
        *,
        entity_type: str,
        entity_id: UUID,
        lot_id: UUID,
        movement_type: str,
        quantity: int,
        created_by=None,
        reference_id: UUID | None = None,
        reference_type: str = '',
    ) -> StockMovement:
        """
        Record a single movement. For outbound types, checks balance and
        uses advisory lock to prevent concurrent over-sale.
        """
        if movement_type not in dict(StockMovement.MovementType.choices):
            raise BusinessRuleViolation(detail=f'Invalid movement_type: {movement_type}')
        if quantity <= 0:
            raise BusinessRuleViolation(detail='Quantity must be positive.')

        try:
            lot = NationalLot.objects.get(pk=lot_id, is_deleted=False)
        except NationalLot.DoesNotExist:
            raise ResourceNotFoundError(detail='Lot not found.')
        if not lot.is_usable:
            raise BusinessRuleViolation(
                detail='Lot is not usable for stock (blocked, expired, or recalled).',
            )

        if movement_type in OUTBOUND_TYPES:
            if connection.vendor == 'postgresql':
                lock_key = _advisory_lock_key(entity_type, entity_id, lot_id)
                with connection.cursor() as cursor:
                    cursor.execute('SELECT pg_advisory_xact_lock(%s)', [lock_key])
            balance = _get_balance_orm(entity_type, entity_id, lot_id)
            if balance < quantity:
                raise InsufficientStockError(
                    detail=f'Insufficient stock: balance={balance}, requested={quantity}.',
                )

        movement = StockMovement(
            entity_type=entity_type,
            entity_id=entity_id,
            lot_id=lot_id,
            movement_type=movement_type,
            quantity=quantity,
            reference_id=reference_id,
            reference_type=reference_type or '',
            created_by=created_by,
        )
        movement.save()

        AuditService.log(
            actor=created_by,
            action=AUDIT_ACTION_CREATE,
            model_name='StockMovement',
            object_id=str(movement.pk),
            new_values={
                'entity_type': entity_type,
                'entity_id': str(entity_id),
                'lot_id': str(lot_id),
                'movement_type': movement_type,
                'quantity': quantity,
            },
        )
        logger.info(
            'StockMovement %s %s qty=%s entity=%s:%s lot=%s',
            movement_type, movement.pk, quantity, entity_type, entity_id, lot_id,
        )
        return movement

    @staticmethod
    @transaction.atomic
    def process_b2b_transaction(
        *,
        seller_entity_type: str,
        seller_entity_id: UUID,
        buyer_entity_type: str,
        buyer_entity_id: UUID,
        lot_id: UUID,
        quantity: int,
        created_by=None,
        reference_id: UUID | None = None,
        reference_type: str = 'B2BOrder',
    ) -> tuple[StockMovement, StockMovement]:
        """
        Atomic dual movement: B2B_OUT from seller, B2B_IN to buyer.
        Rolls back both if any step fails.
        """
        if quantity <= 0:
            raise BusinessRuleViolation(detail='Quantity must be positive.')
        if connection.vendor == 'postgresql':
            seller_key = _advisory_lock_key(seller_entity_type, seller_entity_id, lot_id)
            buyer_key = _advisory_lock_key(buyer_entity_type, buyer_entity_id, lot_id)
            with connection.cursor() as cursor:
                cursor.execute('SELECT pg_advisory_xact_lock(%s)', [seller_key])
                cursor.execute('SELECT pg_advisory_xact_lock(%s)', [buyer_key])

        balance = _get_balance_orm(seller_entity_type, seller_entity_id, lot_id)
        if balance < quantity:
            raise InsufficientStockError(
                detail=f'Insufficient seller stock: balance={balance}, requested={quantity}.',
            )

        try:
            lot = NationalLot.objects.get(pk=lot_id, is_deleted=False)
        except NationalLot.DoesNotExist:
            raise ResourceNotFoundError(detail='Lot not found.')
        if not lot.is_usable:
            raise BusinessRuleViolation(detail='Lot is not usable for stock.')

        out_movement = StockMovement(
            entity_type=seller_entity_type,
            entity_id=seller_entity_id,
            lot_id=lot_id,
            movement_type=StockMovement.MovementType.B2B_OUT,
            quantity=quantity,
            reference_id=reference_id,
            reference_type=reference_type or 'B2BOrder',
            created_by=created_by,
        )
        out_movement.save()

        in_movement = StockMovement(
            entity_type=buyer_entity_type,
            entity_id=buyer_entity_id,
            lot_id=lot_id,
            movement_type=StockMovement.MovementType.B2B_IN,
            quantity=quantity,
            reference_id=reference_id,
            reference_type=reference_type or 'B2BOrder',
            created_by=created_by,
        )
        in_movement.save()

        for mov in (out_movement, in_movement):
            AuditService.log(
                actor=created_by,
                action=AUDIT_ACTION_CREATE,
                model_name='StockMovement',
                object_id=str(mov.pk),
                new_values={
                    'entity_type': mov.entity_type,
                    'entity_id': str(mov.entity_id),
                    'lot_id': str(mov.lot_id),
                    'movement_type': mov.movement_type,
                    'quantity': mov.quantity,
                },
            )
        logger.info(
            'B2B transaction: OUT %s IN %s qty=%s lot=%s',
            out_movement.pk, in_movement.pk, quantity, lot_id,
        )
        return out_movement, in_movement

    @staticmethod
    @transaction.atomic
    def process_retail_sale(
        *,
        pharmacy_id: UUID,
        lot_id: UUID,
        quantity: int,
        created_by=None,
        reference_id: UUID | None = None,
        reference_type: str = '',
    ) -> StockMovement:
        """Atomic single SALE movement from a pharmacy (retail)."""
        return StockService.record_movement(
            entity_type=StockMovement.EntityType.PHARMACY,
            entity_id=pharmacy_id,
            lot_id=lot_id,
            movement_type=StockMovement.MovementType.SALE,
            quantity=quantity,
            created_by=created_by,
            reference_id=reference_id,
            reference_type=reference_type or 'Sale',
        )
