"""
Users — Service Layer

All user-related business logic. No HTTP context — services receive
plain Python arguments and raise typed exceptions.

@file users/services.py
"""

import logging

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from core.constants import (
    AUDIT_ACTION_CREATE,
    AUDIT_ACTION_LOGIN,
    AUDIT_ACTION_LOGIN_FAILED,
    AUDIT_ACTION_LOGOUT,
    AUDIT_ACTION_STATUS_CHANGE,
    AUDIT_ACTION_UPDATE,
)
from core.exceptions import (
    AuthenticationFailedError,
    BusinessRuleViolation,
    DuplicateResourceError,
    InvalidStateTransition,
    ResourceNotFoundError,
)
from core.services import AuditService

from .models import DeviceToken, OTPCode, Role, User, UserRole

logger = logging.getLogger('pharmatrack')


# ---------------------------------------------------------------------------
# User service
# ---------------------------------------------------------------------------

class UserService:
    """CRUD and lifecycle management for User accounts."""

    VALID_STATUS_TRANSITIONS = {
        'PENDING': {'ACTIVE', 'REJECTED'},
        'ACTIVE': {'SUSPENDED'},
        'SUSPENDED': {'ACTIVE'},
        'REJECTED': set(),
    }

    @staticmethod
    @transaction.atomic
    def create_user(
        *,
        phone: str,
        password: str | None = None,
        actor=None,
        **extra_fields,
    ) -> User:
        if User.objects.filter(phone=phone).exists():
            raise DuplicateResourceError(detail=f'Phone {phone} already registered.')

        email = extra_fields.get('email')
        if email and User.objects.filter(email=email).exists():
            raise DuplicateResourceError(detail=f'Email {email} already registered.')

        cin = extra_fields.get('cin')
        if cin and User.objects.filter(cin=cin).exists():
            raise DuplicateResourceError(detail=f'CIN {cin} already registered.')

        user = User.objects.create_user(phone=phone, password=password, **extra_fields)
        user.created_by = actor
        user.save(update_fields=['created_by'])

        return user

    @staticmethod
    @transaction.atomic
    def update_user(*, user_id, actor=None, **fields) -> User:
        try:
            user = User.objects.select_for_update().get(pk=user_id, is_deleted=False)
        except User.DoesNotExist:
            raise ResourceNotFoundError()

        old_snapshot = AuditService.snapshot(user)

        for field, value in fields.items():
            if hasattr(user, field) and field not in ('id', 'pk', 'password'):
                setattr(user, field, value)

        user.updated_by = actor
        user.save()

        AuditService.log(
            actor=actor,
            action=AUDIT_ACTION_UPDATE,
            model_name='User',
            object_id=str(user.pk),
            old_values=old_snapshot,
            new_values=AuditService.snapshot(user),
        )
        return user

    @classmethod
    @transaction.atomic
    def change_status(cls, *, user_id, new_status: str, actor=None, reason: str = '') -> User:
        try:
            user = User.objects.select_for_update().get(pk=user_id, is_deleted=False)
        except User.DoesNotExist:
            raise ResourceNotFoundError()

        allowed = cls.VALID_STATUS_TRANSITIONS.get(user.status, set())
        if new_status not in allowed:
            raise InvalidStateTransition(
                detail=f'Cannot transition from {user.status} to {new_status}.',
            )

        old_status = user.status
        user.status = new_status
        user.updated_by = actor
        user.save(update_fields=['status', 'updated_by', 'updated_at'])

        AuditService.log(
            actor=actor,
            action=AUDIT_ACTION_STATUS_CHANGE,
            model_name='User',
            object_id=str(user.pk),
            old_values={'status': old_status},
            new_values={'status': new_status, 'reason': reason},
        )
        return user


# ---------------------------------------------------------------------------
# Auth service
# ---------------------------------------------------------------------------

class AuthService:
    """Authentication flows: login, OTP, device trust."""

    @staticmethod
    def authenticate(*, phone: str, password: str) -> User | None:
        try:
            user = User.objects.get(phone=phone, is_deleted=False)
        except User.DoesNotExist:
            return None

        if not user.check_password(password):
            return None

        if user.status != User.StatusChoices.ACTIVE:
            return None

        return user

    @staticmethod
    def generate_otp(user: User, purpose: str = OTPCode.PurposeChoices.LOGIN) -> str:
        OTPCode.objects.filter(
            user=user, purpose=purpose, is_used=False,
        ).update(is_used=True)

        _, plain_code = OTPCode.generate(user, purpose)
        logger.info('OTP generated for user %s (purpose=%s)', user.pk, purpose)
        return plain_code

    @staticmethod
    def verify_otp(user: User, code: str, purpose: str = OTPCode.PurposeChoices.LOGIN) -> bool:
        otp = (
            OTPCode.objects
            .filter(user=user, purpose=purpose, is_used=False)
            .order_by('-created_at')
            .first()
        )
        if otp is None:
            return False
        return otp.verify(code)

    @staticmethod
    @transaction.atomic
    def register_device(
        user: User,
        fingerprint: str,
        device_name: str = '',
    ) -> DeviceToken:
        token, _ = DeviceToken.objects.update_or_create(
            user=user,
            device_fingerprint=fingerprint,
            defaults={
                'device_name': device_name,
                'is_trusted': True,
                'expires_at': timezone.now() + timezone.timedelta(
                    days=settings.DEVICE_TOKEN_EXPIRY_DAYS,
                ),
            },
        )
        return token

    @staticmethod
    def is_trusted_device(user: User, fingerprint: str) -> bool:
        return DeviceToken.objects.filter(
            user=user,
            device_fingerprint=fingerprint,
            is_trusted=True,
            expires_at__gt=timezone.now(),
        ).exists()

    @staticmethod
    def log_auth_event(*, action: str, user=None, ip_address=None, user_agent=''):
        AuditService.log(
            actor=user,
            action=action,
            model_name='User',
            object_id=str(user.pk) if user else '',
            ip_address=ip_address,
            user_agent=user_agent,
        )


# ---------------------------------------------------------------------------
# Role service
# ---------------------------------------------------------------------------

class RoleService:
    """RBAC management: assign, revoke, query roles."""

    @staticmethod
    @transaction.atomic
    def assign_role(
        *,
        user: User,
        role_name: str,
        entity_id=None,
        actor=None,
    ) -> UserRole:
        try:
            role = Role.objects.get(name=role_name)
        except Role.DoesNotExist:
            raise ResourceNotFoundError(detail=f'Role "{role_name}" does not exist.')

        user_role, created = UserRole.objects.get_or_create(
            user=user, role=role, entity_id=entity_id,
            defaults={'created_by': actor, 'is_active': True},
        )
        if not created and not user_role.is_active:
            user_role.is_active = True
            user_role.updated_by = actor
            user_role.save(update_fields=['is_active', 'updated_by', 'updated_at'])

        AuditService.log(
            actor=actor,
            action=AUDIT_ACTION_CREATE if created else AUDIT_ACTION_UPDATE,
            model_name='UserRole',
            object_id=str(user_role.pk),
            new_values={'user': str(user.pk), 'role': role_name, 'entity_id': str(entity_id)},
        )
        return user_role

    @staticmethod
    @transaction.atomic
    def revoke_role(*, user: User, role_name: str, entity_id=None, actor=None) -> None:
        qs = UserRole.objects.filter(user=user, role__name=role_name, is_active=True)
        if entity_id:
            qs = qs.filter(entity_id=entity_id)

        updated = qs.update(is_active=False)
        if updated == 0:
            raise ResourceNotFoundError(detail='Active role assignment not found.')

    @staticmethod
    def get_user_roles(user: User) -> list[dict]:
        return list(
            UserRole.objects
            .filter(user=user, is_active=True)
            .select_related('role')
            .values('role__name', 'role__scope', 'entity_id')
        )
