"""
Users — API Integration Tests

End-to-end tests for auth endpoints and user CRUD.

@file users/tests/test_views.py
"""

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from tests.factories import RoleFactory, SuperuserFactory, UserFactory, UserRoleFactory
from users.models import User


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def admin_user():
    user = SuperuserFactory(phone='+25769000000')
    role = RoleFactory(name='NATIONAL_ADMIN', scope='NATIONAL')
    UserRoleFactory(user=user, role=role)
    return user


@pytest.fixture
def authenticated_admin(api_client, admin_user):
    api_client.force_authenticate(user=admin_user)
    return api_client


@pytest.mark.django_db
class TestLoginEndpoint:
    def test_login_success(self, api_client):
        UserFactory(phone='+25768000000', password='Login2026!!')
        response = api_client.post(
            reverse('api-v1:auth:login'),
            {'phone': '+25768000000', 'password': 'Login2026!!'},
            format='json',
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data['success'] is True
        assert 'access' in data['data']
        assert 'refresh' in data['data']

    def test_login_wrong_password(self, api_client):
        UserFactory(phone='+25768000001', password='Login2026!!')
        response = api_client.post(
            reverse('api-v1:auth:login'),
            {'phone': '+25768000001', 'password': 'wrong'},
            format='json',
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_login_inactive_user(self, api_client):
        UserFactory(phone='+25768000002', password='Login2026!!', status=User.StatusChoices.PENDING)
        response = api_client.post(
            reverse('api-v1:auth:login'),
            {'phone': '+25768000002', 'password': 'Login2026!!'},
            format='json',
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestMeEndpoint:
    def test_me_authenticated(self, api_client):
        user = UserFactory()
        api_client.force_authenticate(user=user)
        response = api_client.get(reverse('api-v1:auth:me'))
        assert response.status_code == status.HTTP_200_OK
        assert response.json()['data']['phone'] == user.phone

    def test_me_unauthenticated(self, api_client):
        response = api_client.get(reverse('api-v1:auth:me'))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestUserCRUD:
    def test_list_users(self, authenticated_admin):
        UserFactory.create_batch(5)
        response = authenticated_admin.get(reverse('api-v1:users:user-list'))
        assert response.status_code == status.HTTP_200_OK

    def test_create_user(self, authenticated_admin):
        response = authenticated_admin.post(
            reverse('api-v1:users:user-list'),
            {
                'phone': '+25768100000',
                'first_name': 'Test',
                'last_name': 'User',
                'password': 'NewUser2026!!',
            },
            format='json',
        )
        assert response.status_code == status.HTTP_201_CREATED

    def test_retrieve_user(self, authenticated_admin):
        user = UserFactory()
        response = authenticated_admin.get(
            reverse('api-v1:users:user-detail', kwargs={'pk': user.pk}),
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()['data']['phone'] == user.phone

    def test_unauthenticated_access_denied(self, api_client):
        response = api_client.get(reverse('api-v1:users:user-list'))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
