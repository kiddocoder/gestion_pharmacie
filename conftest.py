"""
PharmaTrack-BI — Root conftest for pytest

Shared fixtures available to all test modules.

@file conftest.py
"""

import pytest
from rest_framework.test import APIClient

from tests.factories import SuperuserFactory, UserFactory


@pytest.fixture
def api_client():
    """Unauthenticated DRF test client."""
    return APIClient()


@pytest.fixture
def user(db):
    """Active user with default password TestPass2026!"""
    return UserFactory()


@pytest.fixture
def admin_user(db):
    """Superuser with default password TestPass2026!"""
    return SuperuserFactory()


@pytest.fixture
def authenticated_client(api_client, user):
    """API client authenticated as a regular user."""
    api_client.force_authenticate(user=user)
    return api_client


@pytest.fixture
def admin_client(api_client, admin_user):
    """API client authenticated as a superuser."""
    api_client.force_authenticate(user=admin_user)
    return api_client
