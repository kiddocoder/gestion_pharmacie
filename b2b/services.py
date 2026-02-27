"""
B2B — Service Layer

Order lifecycle: create (DRAFT), submit, approve (reserve credit), ship,
deliver (dual stock + finalize credit), cancel (release/reserve reversal), reject.
State machine and price validation enforced here.

@file b2b/services.py
"""

import logging
from decimal import Decimal

from django.db import transaction

from core.constants import AUDIT_ACTION_STATUS_CHANGE
from core.exceptions import (
    BusinessRuleViolation,
    InsufficientStockError,
    InvalidStateTransition,
    ResourceNotFoundError,
)
from core.services import AuditService
from medicines.models import NationalLot
from stock.models import StockMovement
from stock.services import StockService

from .models import B2BOrder, B2BOrderItem, PharmacyCredit

logger = logging.getLogger('pharmatrack')

# Valid status transitions: from_status -> set of allowed to_status
ORDER_TRANSITIONS = {
    B2BOrder.StatusChoices.DRAFT: {B2BOrder.StatusChoices.SUBMITTED, B2BOrder.StatusChoices.CANCELLED},
    B2BOrder.StatusChoices.SUBMITTED: {
        B2BOrder.StatusChoices.APPROVED,
        B2BOrder.StatusChoices.REJECTED,
        B2BOrder.StatusChoices.CANCELLED,
    },
    B2BOrder.StatusChoices.APPROVED: {
        B2BOrder.StatusChoices.IN_TRANSIT,
        B2BOrder.StatusChoices.CANCELLED,
    },
    B2BOrder.StatusChoices.IN_TRANSIT: {
        B2BOrder.StatusChoices.DELIVERED,
        B2BOrder.StatusChoices.CANCELLED,
    },
    B2BOrder.StatusChoices.DELIVERED: set(),
    B2BOrder.StatusChoices.CANCELLED: set(),
    B2BOrder.StatusChoices.REJECTED: set(),
}


def _assert_transition(order: B2BOrder, new_status: str) -> None:
    allowed = ORDER_TRANSITIONS.get(order.status, set())
    if new_status not in allowed:
        raise InvalidStateTransition(
            detail=f'Cannot transition order from {order.status} to {new_status}.',
        )


def _recompute_order_total(order: B2BOrder) -> Decimal:
    total = sum(
        (item.unit_price * item.quantity_ordered for item in order.items.filter(is_deleted=False)),
        Decimal('0'),
    )
    order.total_amount = total
    order.save(update_fields=['total_amount'])
    return total


def _validate_item_prices(order: B2BOrder, price_override_approved: bool = False) -> None:
    """Raise if any item unit_price exceeds medicine authorized_price and override not granted."""
    for item in order.items.filter(is_deleted=False).select_related('lot', 'lot__medicine'):
        authorized = item.lot.medicine.authorized_price
        if item.unit_price > authorized and not price_override_approved:
            raise BusinessRuleViolation(
                detail=(
                    f'Unit price {item.unit_price} exceeds authorized price {authorized} '
                    'for lot. Price override must be granted.'
                ),
            )


class B2BOrderService:
    """B2B order lifecycle and credit/stock operations."""

    @staticmethod
    @transaction.atomic
    def create_order(
        *,
        seller_id,
        buyer_id,
        items: list[dict],
        actor=None,
        price_override_approved: bool = False,
    ) -> B2BOrder:
        """Create order in DRAFT with items. Validates seller=WHOLESALER, buyer=RETAILER."""
        from pharmacies.models import Pharmacy

        seller = Pharmacy.objects.filter(
            pk=seller_id, pharmacy_type=Pharmacy.TypeChoices.WHOLESALER, is_deleted=False,
        ).first()
        if not seller:
            raise ResourceNotFoundError(detail='Seller pharmacy (WHOLESALER) not found.')
        buyer = Pharmacy.objects.filter(
            pk=buyer_id, pharmacy_type=Pharmacy.TypeChoices.RETAILER, is_deleted=False,
        ).first()
        if not buyer:
            raise ResourceNotFoundError(detail='Buyer pharmacy (RETAILER) not found.')

        order = B2BOrder(
            seller=seller,
            buyer=buyer,
            status=B2BOrder.StatusChoices.DRAFT,
            price_override_approved=price_override_approved,
            created_by=actor,
        )
        order.save()
        total = Decimal('0')
        for row in items:
            lot = NationalLot.objects.get(pk=row['lot_id'], is_deleted=False)
            if not lot.is_usable:
                raise BusinessRuleViolation(detail=f'Lot {lot.pk} is not usable for stock.')
            authorized = lot.medicine.authorized_price
            unit_price = row.get('unit_price', authorized)
            if unit_price > authorized and not price_override_approved:
                raise BusinessRuleViolation(
                    detail=f'Unit price exceeds authorized price for lot {lot.pk}.',
                )
            qty = row['quantity_ordered']
            if qty <= 0:
                raise BusinessRuleViolation(detail='Quantity must be positive.')
            B2BOrderItem.objects.create(
                order=order,
                lot=lot,
                quantity_ordered=qty,
                unit_price=unit_price,
                created_by=actor,
            )
            total += unit_price * qty
        order.total_amount = total
        order.save(update_fields=['total_amount'])
        return order

    @staticmethod
    @transaction.atomic
    def update_draft_order(
        *,
        order_id,
        items: list[dict] | None = None,
        price_override_approved: bool | None = None,
        actor=None,
    ) -> B2BOrder:
        """Update a DRAFT order (replace items, optionally set price_override_approved)."""
        order = B2BOrder.objects.select_for_update().get(pk=order_id, is_deleted=False)
        if order.status != B2BOrder.StatusChoices.DRAFT:
            raise InvalidStateTransition(detail='Only DRAFT orders can be updated.')
        if price_override_approved is not None:
            order.price_override_approved = price_override_approved
            order.updated_by = actor
            order.save(update_fields=['price_override_approved', 'updated_by', 'updated_at'])
        if items is not None:
            for item in order.items.filter(is_deleted=False):
                item.soft_delete(user=actor)
            total = Decimal('0')
            for row in items:
                lot = NationalLot.objects.get(pk=row['lot_id'], is_deleted=False)
                if not lot.is_usable:
                    raise BusinessRuleViolation(detail=f'Lot {lot.pk} is not usable.')
                unit_price = row.get('unit_price', lot.medicine.authorized_price)
                qty = row['quantity_ordered']
                if qty <= 0:
                    raise BusinessRuleViolation(detail='Quantity must be positive.')
                B2BOrderItem.objects.create(
                    order=order,
                    lot=lot,
                    quantity_ordered=qty,
                    unit_price=unit_price,
                    created_by=actor,
                )
                total += unit_price * qty
            order.total_amount = total
            order.save(update_fields=['total_amount', 'updated_by', 'updated_at'])
        order.updated_by = actor
        order.save(update_fields=['updated_by', 'updated_at'])
        return order

    @staticmethod
    @transaction.atomic
    def submit_order(*, order_id, actor=None) -> B2BOrder:
        order = B2BOrder.objects.select_for_update().select_related('seller', 'buyer').get(
            pk=order_id, is_deleted=False,
        )
        _assert_transition(order, B2BOrder.StatusChoices.SUBMITTED)
        if not order.items.filter(is_deleted=False).exists():
            raise BusinessRuleViolation(detail='Order must have at least one item.')
        old_status = order.status
        order.status = B2BOrder.StatusChoices.SUBMITTED
        order.updated_by = actor
        order.save(update_fields=['status', 'updated_by', 'updated_at'])
        AuditService.log(
            actor=actor,
            action=AUDIT_ACTION_STATUS_CHANGE,
            model_name='B2BOrder',
            object_id=str(order.pk),
            old_values={'status': old_status},
            new_values={'status': order.status},
        )
        return order

    @staticmethod
    @transaction.atomic
    def approve_order(*, order_id, credit_used: Decimal | None = None, actor=None) -> B2BOrder:
        order = B2BOrder.objects.select_for_update().select_related('seller', 'buyer').prefetch_related(
            'items__lot', 'items__lot__medicine',
        ).get(pk=order_id, is_deleted=False)
        _assert_transition(order, B2BOrder.StatusChoices.APPROVED)
        _validate_item_prices(order, price_override_approved=order.price_override_approved)

        credit_used = credit_used or order.total_amount
        if credit_used > 0:
            try:
                credit = PharmacyCredit.objects.select_for_update().get(pharmacy=order.buyer)
            except PharmacyCredit.DoesNotExist:
                raise BusinessRuleViolation(detail='Buyer has no credit line configured.')
            available = credit.credit_limit - credit.current_balance - credit.reserved_balance
            if available < credit_used:
                raise BusinessRuleViolation(
                    detail=f'Insufficient credit: available={available}, order total={credit_used}.',
                )
            credit.reserved_balance += credit_used
            credit.save(update_fields=['reserved_balance', 'updated_at'])
        order.credit_used = credit_used
        order.save(update_fields=['credit_used', 'updated_at'])

        old_status = order.status
        order.status = B2BOrder.StatusChoices.APPROVED
        order.updated_by = actor
        order.save(update_fields=['status', 'updated_by', 'updated_at'])
        AuditService.log(
            actor=actor,
            action=AUDIT_ACTION_STATUS_CHANGE,
            model_name='B2BOrder',
            object_id=str(order.pk),
            old_values={'status': old_status},
            new_values={'status': 'APPROVED', 'credit_used': str(credit_used)},
        )
        return order

    @staticmethod
    @transaction.atomic
    def ship_order(*, order_id, actor=None) -> B2BOrder:
        order = B2BOrder.objects.select_for_update().get(pk=order_id, is_deleted=False)
        _assert_transition(order, B2BOrder.StatusChoices.IN_TRANSIT)
        old_status = order.status
        order.status = B2BOrder.StatusChoices.IN_TRANSIT
        order.updated_by = actor
        order.save(update_fields=['status', 'updated_by', 'updated_at'])
        AuditService.log(
            actor=actor,
            action=AUDIT_ACTION_STATUS_CHANGE,
            model_name='B2BOrder',
            object_id=str(order.pk),
            old_values={'status': old_status},
            new_values={'status': 'IN_TRANSIT'},
        )
        return order

    @staticmethod
    @transaction.atomic
    def deliver_order(*, order_id, actor=None) -> B2BOrder:
        order = B2BOrder.objects.select_for_update().select_related('seller', 'buyer').prefetch_related(
            'items__lot',
        ).get(pk=order_id, is_deleted=False)
        _assert_transition(order, B2BOrder.StatusChoices.DELIVERED)

        for item in order.items.filter(is_deleted=False):
            if item.quantity_ordered <= 0:
                continue
            try:
                StockService.process_b2b_transaction(
                    seller_entity_type=StockMovement.EntityType.PHARMACY,
                    seller_entity_id=order.seller_id,
                    buyer_entity_type=StockMovement.EntityType.PHARMACY,
                    buyer_entity_id=order.buyer_id,
                    lot_id=item.lot_id,
                    quantity=item.quantity_ordered,
                    created_by=actor,
                    reference_id=order.pk,
                    reference_type='B2BOrder',
                )
            except InsufficientStockError as e:
                raise BusinessRuleViolation(
                    detail=f'Seller insufficient stock for lot {item.lot_id}: {e.detail}.',
                )
            item.quantity_delivered = item.quantity_ordered
            item.save(update_fields=['quantity_delivered', 'updated_at'])

        if order.credit_used > 0:
            credit = PharmacyCredit.objects.select_for_update().get(pharmacy=order.buyer)
            credit.reserved_balance -= order.credit_used
            credit.current_balance += order.credit_used
            credit.save(update_fields=['reserved_balance', 'current_balance', 'updated_at'])

        # JournalEntry creation deferred to Phase 8 (finance)
        old_status = order.status
        order.status = B2BOrder.StatusChoices.DELIVERED
        order.updated_by = actor
        order.save(update_fields=['status', 'updated_by', 'updated_at'])
        AuditService.log(
            actor=actor,
            action=AUDIT_ACTION_STATUS_CHANGE,
            model_name='B2BOrder',
            object_id=str(order.pk),
            old_values={'status': old_status},
            new_values={'status': 'DELIVERED'},
        )
        logger.info('B2B order %s delivered.', order_id)
        return order

    @staticmethod
    @transaction.atomic
    def cancel_order(*, order_id, actor=None) -> B2BOrder:
        order = B2BOrder.objects.select_for_update().select_related('seller', 'buyer').prefetch_related(
            'items__lot',
        ).get(pk=order_id, is_deleted=False)
        _assert_transition(order, B2BOrder.StatusChoices.CANCELLED)

        if order.status == B2BOrder.StatusChoices.DELIVERED:
            raise InvalidStateTransition(detail='Cannot cancel an already delivered order; use reversal flow.')

        if order.status in (B2BOrder.StatusChoices.APPROVED, B2BOrder.StatusChoices.IN_TRANSIT) and order.credit_used > 0:
            credit = PharmacyCredit.objects.select_for_update().get(pharmacy=order.buyer)
            credit.reserved_balance -= order.credit_used
            credit.save(update_fields=['reserved_balance', 'updated_at'])

        if order.status == B2BOrder.StatusChoices.IN_TRANSIT:
            # Already shipped but not delivered: release reserved only (no stock moved yet)
            pass

        old_status = order.status
        order.status = B2BOrder.StatusChoices.CANCELLED
        order.updated_by = actor
        order.save(update_fields=['status', 'updated_by', 'updated_at'])
        AuditService.log(
            actor=actor,
            action=AUDIT_ACTION_STATUS_CHANGE,
            model_name='B2BOrder',
            object_id=str(order.pk),
            old_values={'status': old_status},
            new_values={'status': 'CANCELLED'},
        )
        return order

    @staticmethod
    @transaction.atomic
    def reject_order(*, order_id, actor=None) -> B2BOrder:
        order = B2BOrder.objects.select_for_update().get(pk=order_id, is_deleted=False)
        _assert_transition(order, B2BOrder.StatusChoices.REJECTED)
        old_status = order.status
        order.status = B2BOrder.StatusChoices.REJECTED
        order.updated_by = actor
        order.save(update_fields=['status', 'updated_by', 'updated_at'])
        AuditService.log(
            actor=actor,
            action=AUDIT_ACTION_STATUS_CHANGE,
            model_name='B2BOrder',
            object_id=str(order.pk),
            old_values={'status': old_status},
            new_values={'status': 'REJECTED'},
        )
        return order
