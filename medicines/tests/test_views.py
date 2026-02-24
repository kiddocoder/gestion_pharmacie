"""
Tests — Medicines API endpoints (views).

@file medicines/tests/test_views.py
"""

import pytest
from datetime import timedelta
from decimal import Decimal

from django.urls import reverse
from django.utils import timezone

from medicines.models import NationalLot, NationalMedicine
from tests.factories import (
    NationalLotFactory,
    NationalMedicineFactory,
    SuperuserFactory,
    UserFactory,
)


pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# NationalMedicine endpoints
# ---------------------------------------------------------------------------

class TestMedicineListCreate:

    def test_list_requires_auth(self, api_client):
        url = reverse('api-v1:medicines:medicine-list')
        resp = api_client.get(url)
        assert resp.status_code == 401

    def test_list_medicines(self, authenticated_client):
        NationalMedicineFactory.create_batch(3)
        url = reverse('api-v1:medicines:medicine-list')
        resp = authenticated_client.get(url)
        assert resp.status_code == 200
        assert len(resp.data['results']) == 3

    def test_search_by_inn(self, authenticated_client):
        NationalMedicineFactory(inn='Paracetamol')
        NationalMedicineFactory(inn='Amoxicillin')
        url = reverse('api-v1:medicines:medicine-list')
        resp = authenticated_client.get(url, {'search': 'Paracetamol'})
        assert resp.status_code == 200
        assert len(resp.data['results']) == 1

    def test_filter_by_status(self, authenticated_client):
        NationalMedicineFactory(status='AUTHORIZED')
        NationalMedicineFactory(status='BLOCKED')
        url = reverse('api-v1:medicines:medicine-list')
        resp = authenticated_client.get(url, {'status': 'BLOCKED'})
        assert resp.status_code == 200
        assert len(resp.data['results']) == 1

    def test_create_requires_admin(self, authenticated_client):
        url = reverse('api-v1:medicines:medicine-list')
        data = {
            'atc_code': 'N02BE01', 'inn': 'Paracetamol',
            'dosage_form': 'TABLET', 'strength': '500mg',
            'authorized_price': '3000.00',
        }
        resp = authenticated_client.post(url, data, format='json')
        assert resp.status_code == 403

    def test_create_as_superuser(self, admin_client):
        url = reverse('api-v1:medicines:medicine-list')
        data = {
            'atc_code': 'N02BE01', 'inn': 'Paracetamol',
            'dosage_form': 'TABLET', 'strength': '500mg',
            'authorized_price': '3000.00',
        }
        resp = admin_client.post(url, data, format='json')
        assert resp.status_code == 201


class TestMedicineRetrieveUpdate:

    def test_retrieve(self, authenticated_client):
        med = NationalMedicineFactory()
        url = reverse('api-v1:medicines:medicine-detail', args=[med.pk])
        resp = authenticated_client.get(url)
        assert resp.status_code == 200
        assert resp.data['atc_code'] == med.atc_code

    def test_update_as_superuser(self, admin_client):
        med = NationalMedicineFactory()
        url = reverse('api-v1:medicines:medicine-detail', args=[med.pk])
        resp = admin_client.patch(url, {'authorized_price': '7777.00'}, format='json')
        assert resp.status_code == 200
        med.refresh_from_db()
        assert med.authorized_price == Decimal('7777.00')


class TestMedicineBlockUnblock:

    def test_block(self, admin_client):
        med = NationalMedicineFactory()
        url = reverse('api-v1:medicines:medicine-block', args=[med.pk])
        resp = admin_client.post(url, {'reason': 'Safety'}, format='json')
        assert resp.status_code == 200
        med.refresh_from_db()
        assert med.status == 'BLOCKED'

    def test_unblock(self, admin_client):
        med = NationalMedicineFactory(status='BLOCKED')
        url = reverse('api-v1:medicines:medicine-unblock', args=[med.pk])
        resp = admin_client.post(url, format='json')
        assert resp.status_code == 200
        med.refresh_from_db()
        assert med.status == 'AUTHORIZED'

    def test_regular_user_cannot_block(self, authenticated_client):
        med = NationalMedicineFactory()
        url = reverse('api-v1:medicines:medicine-block', args=[med.pk])
        resp = authenticated_client.post(url, {'reason': 'Nope'}, format='json')
        assert resp.status_code == 403


class TestMedicineNestedLots:

    def test_list_lots_for_medicine(self, authenticated_client):
        med = NationalMedicineFactory()
        NationalLotFactory.create_batch(2, medicine=med)
        NationalLotFactory()  # different medicine
        url = reverse('api-v1:medicines:medicine-lots', args=[med.pk])
        resp = authenticated_client.get(url)
        assert resp.status_code == 200
        data = resp.data.get('results', resp.data.get('data', []))
        assert len(data) == 2

    def test_create_lot_for_medicine(self, admin_client):
        med = NationalMedicineFactory()
        url = reverse('api-v1:medicines:medicine-lots', args=[med.pk])
        today = timezone.now().date()
        data = {
            'batch_number': 'NEW-001',
            'manufacturing_date': str(today - timedelta(days=60)),
            'expiry_date': str(today + timedelta(days=300)),
            'quantity_imported': 5000,
        }
        resp = admin_client.post(url, data, format='json')
        assert resp.status_code == 201


# ---------------------------------------------------------------------------
# NationalLot top-level endpoints
# ---------------------------------------------------------------------------

class TestLotListRetrieve:

    def test_list_lots(self, authenticated_client):
        NationalLotFactory.create_batch(2)
        url = reverse('api-v1:medicines:lots:lot-list')
        resp = authenticated_client.get(url)
        assert resp.status_code == 200
        assert len(resp.data['results']) == 2

    def test_retrieve_lot(self, authenticated_client):
        lot = NationalLotFactory()
        url = reverse('api-v1:medicines:lots:lot-detail', args=[lot.pk])
        resp = authenticated_client.get(url)
        assert resp.status_code == 200
        assert resp.data['batch_number'] == lot.batch_number


class TestLotRecall:

    def test_recall(self, admin_client):
        lot = NationalLotFactory(status='ACTIVE')
        url = reverse('api-v1:medicines:lots:lot-recall', args=[lot.pk])
        resp = admin_client.post(url, {'reason': 'Contamination found in batch'}, format='json')
        assert resp.status_code == 200
        lot.refresh_from_db()
        assert lot.status == 'RECALLED'

    def test_recall_by_regular_user_forbidden(self, authenticated_client):
        lot = NationalLotFactory(status='ACTIVE')
        url = reverse('api-v1:medicines:lots:lot-recall', args=[lot.pk])
        resp = authenticated_client.post(url, {'reason': 'Nope'}, format='json')
        assert resp.status_code == 403


class TestLotExpiringSoon:

    def test_expiring_soon(self, authenticated_client):
        soon = timezone.now().date() + timedelta(days=10)
        far = timezone.now().date() + timedelta(days=200)
        NationalLotFactory(expiry_date=soon, manufacturing_date=soon - timedelta(days=365))
        NationalLotFactory(expiry_date=far, manufacturing_date=far - timedelta(days=365))
        url = reverse('api-v1:medicines:lots:lot-expiring-soon')
        resp = authenticated_client.get(url, {'days': 30})
        assert resp.status_code == 200
        data = resp.data.get('results', resp.data.get('data', []))
        assert len(data) == 1
