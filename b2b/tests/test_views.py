"""
Tests — B2B API endpoints.

@file b2b/tests/test_views.py
"""

import pytest
from decimal import Decimal

from django.urls import reverse

from b2b.models import B2BOrder
from tests.factories import (
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


class TestB2BOrderAPI:
    def test_list_requires_auth(self, api_client):
        url = reverse('api-v1:b2b:order-list')
        resp = api_client.get(url)
        assert resp.status_code == 401

    def test_list_orders(self, admin_client):
        B2BOrderFactory.create_batch(2)
        url = reverse('api-v1:b2b:order-list')
        resp = admin_client.get(url)
        assert resp.status_code == 200
        assert len(resp.data['results']) == 2

    def test_create_order(self, admin_client):
        seller = _wholesaler()
        buyer = _retailer()
        lot = NationalLotFactory()
        url = reverse('api-v1:b2b:order-list')
        data = {
            'seller_id': str(seller.pk),
            'buyer_id': str(buyer.pk),
            'items': [
                {'lot_id': str(lot.pk), 'quantity_ordered': 3},
            ],
        }
        resp = admin_client.post(url, data, format='json')
        assert resp.status_code == 201
        assert resp.data['status'] == 'DRAFT'
        assert len(resp.data['items']) == 1
        assert resp.data['items'][0]['quantity_ordered'] == 3

    def test_submit_order(self, admin_client):
        order = B2BOrderFactory(seller=_wholesaler(), buyer=_retailer(), status=B2BOrder.StatusChoices.DRAFT)
        from tests.factories import B2BOrderItemFactory
        B2BOrderItemFactory(order=order, quantity_ordered=1, unit_price=Decimal('1000'))
        order.total_amount = Decimal('1000')
        order.save()
        url = reverse('api-v1:b2b:order-submit', kwargs={'pk': order.pk})
        resp = admin_client.post(url, {}, format='json')
        assert resp.status_code == 200
        assert resp.data['status'] == 'SUBMITTED'
