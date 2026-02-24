"""
Users — Service Layer Tests

Tests for UserService, AuthService, and RoleService business logic.

@file users/tests/test_services.py
"""

import pytest

from core.exceptions import (
    DuplicateResourceError,
    InvalidStateTransition,
    ResourceNotFoundError,
)
from core.models import AuditLog
from tests.factories import RoleFactory, UserFactory
from users.models import User
from users.services import AuthService, RoleService, UserService


@pytest.mark.django_db
class TestUserService:
    def test_create_user(self):
        user = UserService.create_user(phone='+25764000000', password='Test2026!!')
        assert user.pk is not None
        assert user.phone == '+25764000000'

    def test_create_user_duplicate_phone(self):
        UserFactory(phone='+25764000001')
        with pytest.raises(DuplicateResourceError):
            UserService.create_user(phone='+25764000001')

    def test_update_user(self):
        user = UserFactory()
        updated = UserService.update_user(user_id=user.pk, first_name='Updated')
        assert updated.first_name == 'Updated'

    def test_update_nonexistent_user(self):
        import uuid
        with pytest.raises(ResourceNotFoundError):
            UserService.update_user(user_id=uuid.uuid4(), first_name='Nope')

    def test_change_status_pending_to_active(self):
        user = UserFactory(status=User.StatusChoices.PENDING)
        result = UserService.change_status(user_id=user.pk, new_status='ACTIVE')
        assert result.status == 'ACTIVE'

    def test_change_status_invalid_transition(self):
        user = UserFactory(status=User.StatusChoices.REJECTED)
        with pytest.raises(InvalidStateTransition):
            UserService.change_status(user_id=user.pk, new_status='ACTIVE')

    def test_change_status_creates_audit_log(self):
        user = UserFactory(status=User.StatusChoices.PENDING)
        UserService.change_status(user_id=user.pk, new_status='ACTIVE')
        audit = AuditLog.objects.filter(
            model_name='User',
            object_id=str(user.pk),
            action='STATUS_CHANGE',
        )
        assert audit.exists()


@pytest.mark.django_db
class TestAuthService:
    def test_authenticate_success(self):
        UserFactory(phone='+25765000000', password='Auth2026!!')
        user = AuthService.authenticate(phone='+25765000000', password='Auth2026!!')
        assert user is not None
        assert user.phone == '+25765000000'

    def test_authenticate_wrong_password(self):
        UserFactory(phone='+25765000001', password='Auth2026!!')
        user = AuthService.authenticate(phone='+25765000001', password='wrong')
        assert user is None

    def test_authenticate_inactive_user(self):
        UserFactory(phone='+25765000002', password='Auth2026!!', status=User.StatusChoices.PENDING)
        user = AuthService.authenticate(phone='+25765000002', password='Auth2026!!')
        assert user is None

    def test_generate_and_verify_otp(self):
        user = UserFactory()
        plain = AuthService.generate_otp(user)
        assert len(plain) == 6
        assert AuthService.verify_otp(user, plain) is True

    def test_register_device(self):
        user = UserFactory()
        token = AuthService.register_device(user, 'fp-abc-123', 'Test Phone')
        assert token.is_valid is True
        assert AuthService.is_trusted_device(user, 'fp-abc-123') is True


@pytest.mark.django_db
class TestRoleService:
    def test_assign_role(self):
        user = UserFactory()
        RoleFactory(name='TEST_ASSIGN')
        user_role = RoleService.assign_role(user=user, role_name='TEST_ASSIGN')
        assert user_role.is_active is True
        assert user.has_role('TEST_ASSIGN') is True

    def test_revoke_role(self):
        user = UserFactory()
        RoleFactory(name='TEST_REVOKE')
        RoleService.assign_role(user=user, role_name='TEST_REVOKE')
        RoleService.revoke_role(user=user, role_name='TEST_REVOKE')
        assert user.has_role('TEST_REVOKE') is False

    def test_assign_nonexistent_role(self):
        user = UserFactory()
        with pytest.raises(ResourceNotFoundError):
            RoleService.assign_role(user=user, role_name='NONEXISTENT')

    def test_revoke_nonexistent_assignment(self):
        user = UserFactory()
        RoleFactory(name='UNASSIGNED')
        with pytest.raises(ResourceNotFoundError):
            RoleService.revoke_role(user=user, role_name='UNASSIGNED')
