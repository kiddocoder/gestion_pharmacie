"""
Tests — B2BOrderService: lifecycle, credit reserve/release, dual stock on deliver.

@file b2b/tests/test_services.py
"""

import pytest
from decimal import Decimal

from b2b.models import B2BOrder, PharmacyCredit
from b2b.services import B2BOrderService
from core.exceptions import BusinessRuleViolation, InvalidStateTransition
from stock.models import StockMovement
from stock.services import StockService
from tests.factories import (
    B2BOrderItemFactory,
    B2BOrderFactory,
    NationalLotFactory,
    PharmacyCreditFactory,
    PharmacyFactory,
    SuperuserFactory,
)


pytestmark = pytest.mark.django_db


def _wholesaler():
    return PharmacyFactory(pharmacy_type='WHOLESALER', status='APPROVED')


def _retailer():
    return PharmacyFactory(pharmacy_type='RETAILER', status='APPROVED')


class TestOrderLifecycle:
    def test_create_order(self):
        seller = _wholesaler()
        buyer = _retailer()
        lot = NationalLotFactory()
        order = B2BOrderService.create_order(
            seller_id=seller.pk,
            buyer_id=buyer.pk,
            items=[{'lot_id': lot.pk, 'quantity_ordered': 5, 'unit_price': lot.medicine.authorized_price}],
            actor=SuperuserFactory(),
        )
        assert order.status == B2BOrder.StatusChoices.DRAFT
        assert order.items.filter(is_deleted=False).count() == 1
        assert order.total_amount == lot.medicine.authorized_price * 5

    def test_submit_approve_ship_deliver(self):
        seller = _wholesaler()
        buyer = _retailer()
        PharmacyCreditFactory(pharmacy=buyer, credit_limit=Decimal('1000000'))
        lot = NationalLotFactory()
        StockService.record_movement(
            entity_type=StockMovement.EntityType.PHARMACY,
            entity_id=seller.pk,
            lot_id=lot.pk,
            movement_type=StockMovement.MovementType.IMPORT,
            quantity=100,
            created_by=SuperuserFactory(),
        )
        order = B2BOrderService.create_order(
            seller_id=seller.pk,
            buyer_id=buyer.pk,
            items=[{'lot_id': lot.pk, 'quantity_ordered': 10}],
            actor=SuperuserFactory(),
        )
        order = B2BOrderService.submit_order(order_id=order.pk, actor=SuperuserFactory())
        assert order.status == B2BOrder.StatusChoices.SUBMITTED
        order = B2BOrderService.approve_order(order_id=order.pk, actor=SuperuserFactory())
        assert order.status == B2BOrder.StatusChoices.APPROVED
        credit = PharmacyCredit.objects.get(pharmacy=buyer)
        assert credit.reserved_balance == order.total_amount
        order = B2BOrderService.ship_order(order_id=order.pk, actor=SuperuserFactory())
        assert order.status == B2BOrder.StatusChoices.IN_TRANSIT
        order = B2BOrderService.deliver_order(order_id=order.pk, actor=SuperuserFactory())
        assert order.status == B2BOrder.StatusChoices.DELIVERED
        assert StockService.get_balance(StockMovement.EntityType.PHARMACY, seller.pk, lot.pk) == 90
        assert StockService.get_balance(StockMovement.EntityType.PHARMACY, buyer.pk, lot.pk) == 10
        credit.refresh_from_db()
        assert credit.reserved_balance == 0
        assert credit.current_balance == order.total_amount

    def test_approve_without_credit_raises(self):
        seller = _wholesaler()
        buyer = _retailer()
        # No PharmacyCredit for buyer
        lot = NationalLotFactory()
        order = B2BOrderService.create_order(
            seller_id=seller.pk,
            buyer_id=buyer.pk,
            items=[{'lot_id': lot.pk, 'quantity_ordered': 1}],
            actor=SuperuserFactory(),
        )
        B2BOrderService.submit_order(order_id=order.pk, actor=SuperuserFactory())
        with pytest.raises(BusinessRuleViolation, match='credit'):
            B2BOrderService.approve_order(order_id=order.pk, actor=SuperuserFactory())

    def test_cancel_after_approve_releases_reserved(self):
        seller = _wholesaler()
        buyer = _retailer()
        PharmacyCreditFactory(pharmacy=buyer, credit_limit=Decimal('1000000'))
        order = B2BOrderFactory(seller=seller, buyer=buyer, status=B2BOrder.StatusChoices.DRAFT)
        B2BOrderItemFactory(order=order, quantity_ordered=1, unit_price=Decimal('1000'))
        order.total_amount = Decimal('1000')
        order.save()
        B2BOrderService.submit_order(order_id=order.pk, actor=SuperuserFactory())
        B2BOrderService.approve_order(order_id=order.pk, actor=SuperuserFactory())
        credit = PharmacyCredit.objects.get(pharmacy=buyer)
        assert credit.reserved_balance == Decimal('1000')
        B2BOrderService.cancel_order(order_id=order.pk, actor=SuperuserFactory())
        credit.refresh_from_db()
        assert credit.reserved_balance == 0

    def test_reject_from_submitted(self):
        order = B2BOrderFactory(seller=_wholesaler(), buyer=_retailer(), status=B2BOrder.StatusChoices.SUBMITTED)
        order = B2BOrderService.reject_order(order_id=order.pk, actor=SuperuserFactory())
        assert order.status == B2BOrder.StatusChoices.REJECTED

    def test_invalid_transition_raises(self):
        order = B2BOrderFactory(seller=_wholesaler(), buyer=_retailer(), status=B2BOrder.StatusChoices.DRAFT)
        with pytest.raises(InvalidStateTransition):
            B2BOrderService.deliver_order(order_id=order.pk, actor=SuperuserFactory())
