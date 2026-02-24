"""
Users — Model Tests

Tests for User, Role, UserRole, OTPCode, DeviceToken model logic.

@file users/tests/test_models.py
"""

import pytest
from django.utils import timezone

from tests.factories import (
    ProvinceFactory,
    RoleFactory,
    UserFactory,
    UserRoleFactory,
)
from users.models import OTPCode, User


@pytest.mark.django_db
class TestUserModel:
    def test_create_user(self):
        user = UserFactory(phone='+25761111111')
        assert user.pk is not None
        assert user.phone == '+25761111111'
        assert user.status == User.StatusChoices.ACTIVE

    def test_create_user_default_status(self):
        user = User.objects.create_user(phone='+25762222222', password='Test2026!!')
        assert user.status == User.StatusChoices.PENDING

    def test_superuser_creation(self):
        user = User.objects.create_superuser(phone='+25763333333', password='Super2026!!')
        assert user.is_staff is True
        assert user.is_superuser is True
        assert user.status == User.StatusChoices.ACTIVE

    def test_full_name(self):
        user = UserFactory(first_name='Jean', last_name='Ndayisaba')
        assert user.get_full_name() == 'Jean Ndayisaba'

    def test_full_name_fallback_to_phone(self):
        user = UserFactory(first_name='', last_name='')
        assert user.get_full_name() == user.phone

    def test_uuid_pk(self):
        user = UserFactory()
        assert len(str(user.pk)) == 36

    def test_soft_delete(self):
        user = UserFactory()
        user.soft_delete()
        assert user.is_deleted is True
        assert user.deleted_at is not None

    def test_restore(self):
        user = UserFactory()
        user.soft_delete()
        user.restore()
        assert user.is_deleted is False
        assert user.deleted_at is None

    def test_administrative_level_fk(self):
        province = ProvinceFactory()
        user = UserFactory(administrative_level=province)
        assert user.administrative_level == province


@pytest.mark.django_db
class TestRoleAndRBAC:
    def test_has_role(self):
        role = RoleFactory(name='TEST_ROLE')
        user = UserFactory()
        UserRoleFactory(user=user, role=role)
        assert user.has_role('TEST_ROLE') is True

    def test_has_role_inactive(self):
        role = RoleFactory(name='INACTIVE_ROLE')
        user = UserFactory()
        UserRoleFactory(user=user, role=role, is_active=False)
        assert user.has_role('INACTIVE_ROLE') is False

    def test_role_names_property(self):
        user = UserFactory()
        role1 = RoleFactory(name='ROLE_A')
        role2 = RoleFactory(name='ROLE_B')
        UserRoleFactory(user=user, role=role1)
        UserRoleFactory(user=user, role=role2)
        assert set(user.role_names) == {'ROLE_A', 'ROLE_B'}


@pytest.mark.django_db
class TestOTPCode:
    def test_generate_otp(self):
        user = UserFactory()
        otp, plain = OTPCode.generate(user, OTPCode.PurposeChoices.LOGIN)
        assert len(plain) == 6
        assert otp.is_used is False

    def test_verify_otp_success(self):
        user = UserFactory()
        otp, plain = OTPCode.generate(user, OTPCode.PurposeChoices.LOGIN)
        assert otp.verify(plain) is True
        otp.refresh_from_db()
        assert otp.is_used is True

    def test_verify_otp_wrong_code(self):
        user = UserFactory()
        otp, _ = OTPCode.generate(user, OTPCode.PurposeChoices.LOGIN)
        assert otp.verify('000000') is False

    def test_verify_otp_expired(self):
        user = UserFactory()
        otp, plain = OTPCode.generate(user, OTPCode.PurposeChoices.LOGIN)
        otp.expires_at = timezone.now() - timezone.timedelta(minutes=1)
        otp.save()
        assert otp.verify(plain) is False

    def test_verify_otp_already_used(self):
        user = UserFactory()
        otp, plain = OTPCode.generate(user, OTPCode.PurposeChoices.LOGIN)
        otp.verify(plain)
        assert otp.verify(plain) is False
