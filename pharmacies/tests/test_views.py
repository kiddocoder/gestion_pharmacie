"""
Tests — Pharmacies API endpoints.

@file pharmacies/tests/test_views.py
"""

import pytest
from django.urls import reverse

from pharmacies.models import Pharmacy, PharmacyDocument
from tests.factories import (
    CommuneFactory,
    PharmacyDocumentFactory,
    PharmacyFactory,
    SuperuserFactory,
)


pytestmark = pytest.mark.django_db


class TestPharmacyListCreate:

    def test_list_requires_auth(self, api_client):
        url = reverse('api-v1:pharmacies:pharmacy-list')
        resp = api_client.get(url)
        assert resp.status_code == 401

    def test_list_pharmacies(self, authenticated_client):
        PharmacyFactory.create_batch(2)
        url = reverse('api-v1:pharmacies:pharmacy-list')
        resp = authenticated_client.get(url)
        assert resp.status_code == 200
        assert len(resp.data['results']) == 2

    def test_create_pharmacy(self, admin_client):
        commune = CommuneFactory()
        url = reverse('api-v1:pharmacies:pharmacy-list')
        data = {
            'name': 'New Pharma',
            'pharmacy_type': 'RETAILER',
            'administrative_level': str(commune.pk),
            'address': '123 Street',
            'phone': '+25771234567',
        }
        resp = admin_client.post(url, data, format='json')
        assert resp.status_code == 201
        assert resp.data['name'] == 'New Pharma'
        assert resp.data['status'] == 'PENDING'
        assert resp.data['national_code']
        assert resp.data['national_code'].startswith('PH-')

    def test_approve_pharmacy(self, admin_client):
        pharmacy = PharmacyFactory(status=Pharmacy.StatusChoices.PENDING)
        PharmacyDocumentFactory(pharmacy=pharmacy, status=PharmacyDocument.StatusChoices.APPROVED)
        url = reverse(
            'api-v1:pharmacies:pharmacy-approve',
            kwargs={'pk': pharmacy.pk},
        )
        resp = admin_client.post(url, {'reason': 'OK'}, format='json')
        assert resp.status_code == 200
        assert resp.data['status'] == 'APPROVED'
        assert resp.data.get('qr_code_url') or resp.data.get('qr_code')

    def test_suspend_pharmacy(self, admin_client):
        pharmacy = PharmacyFactory(status=Pharmacy.StatusChoices.APPROVED)
        url = reverse(
            'api-v1:pharmacies:pharmacy-suspend',
            kwargs={'pk': pharmacy.pk},
        )
        resp = admin_client.post(url, {'reason': 'Inspection'}, format='json')
        assert resp.status_code == 200
        assert resp.data['status'] == 'SUSPENDED'

    def test_qr_endpoint_returns_url_when_approved(self, admin_client, admin_user):
        pharmacy = PharmacyFactory(status=Pharmacy.StatusChoices.PENDING)
        PharmacyDocumentFactory(pharmacy=pharmacy, status=PharmacyDocument.StatusChoices.APPROVED)
        from pharmacies.services import PharmacyService
        PharmacyService.approve_pharmacy(pharmacy_id=pharmacy.pk, actor=admin_user)
        url = reverse('api-v1:pharmacies:pharmacy-qr', kwargs={'pk': pharmacy.pk})
        resp = admin_client.get(url)
        assert resp.status_code == 200
        assert 'qr_code_url' in resp.data

    def test_documents_list_and_create(self, admin_client):
        pharmacy = PharmacyFactory()
        list_url = reverse(
            'api-v1:pharmacies:pharmacy-documents',
            kwargs={'pk': pharmacy.pk},
        )
        resp = admin_client.get(list_url)
        assert resp.status_code == 200
        assert isinstance(resp.data, list)
