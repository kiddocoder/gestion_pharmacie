"""
Tests — B2BOrder, B2BOrderItem, PharmacyCredit models.

@file b2b/tests/test_models.py
"""

import pytest
from decimal import Decimal

from b2b.models import B2BOrder, B2BOrderItem, PharmacyCredit
from tests.factories import (
    B2BOrderFactory,
    B2BOrderItemFactory,
    NationalLotFactory,
    PharmacyCreditFactory,
    PharmacyFactory,
)


pytestmark = pytest.mark.django_db


class TestPharmacyCredit:
    def test_available_credit(self):
        credit = PharmacyCreditFactory(
            credit_limit=Decimal('100000'),
            current_balance=Decimal('20000'),
            reserved_balance=Decimal('10000'),
        )
        assert credit.available_credit == Decimal('70000')


class TestB2BOrder:
    def test_create_order(self):
        seller = PharmacyFactory(pharmacy_type='WHOLESALER')
        buyer = PharmacyFactory(pharmacy_type='RETAILER')
        order = B2BOrderFactory(seller=seller, buyer=buyer, status=B2BOrder.StatusChoices.DRAFT)
        assert order.pk is not None
        assert order.status == B2BOrder.StatusChoices.DRAFT

    def test_str(self):
        order = B2BOrderFactory()
        assert str(order.seller.name) in str(order) or str(order.pk) in str(order)


class TestB2BOrderItem:
    def test_line_total(self):
        item = B2BOrderItemFactory(quantity_ordered=5, unit_price=Decimal('1000'))
        assert item.unit_price * item.quantity_ordered == Decimal('5000')
