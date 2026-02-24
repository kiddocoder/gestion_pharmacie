"""
Users — Models

Custom User model with UUID PK, CIN, phone-based auth, status
lifecycle, and full RBAC (Role + UserRole). Also includes OTPCode
and DeviceToken for defense-in-depth authentication.

@file users/models.py
"""

import hashlib
import secrets
import uuid

from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from core.models import BaseModel, RegulatedModel, TimestampMixin
from users.managers import UserManager


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------

class User(AbstractBaseUser, PermissionsMixin, RegulatedModel):
    """
    Custom user for PharmaTrack-BI.

    Authentication is phone-based. CIN (Carte d'Identité Nationale)
    is the official government ID. Every user is scoped to an
    administrative level (province, commune, etc.) for geographic RBAC.
    """

    class StatusChoices(models.TextChoices):
        PENDING = 'PENDING', _('Pending')
        ACTIVE = 'ACTIVE', _('Active')
        SUSPENDED = 'SUSPENDED', _('Suspended')
        REJECTED = 'REJECTED', _('Rejected')

    cin = models.CharField(
        _('CIN'), max_length=30, unique=True, null=True, blank=True,
        help_text=_('Carte d\'Identité Nationale'),
    )
    phone = models.CharField(_('phone'), max_length=20, unique=True)
    email = models.EmailField(_('email'), unique=True, null=True, blank=True)
    first_name = models.CharField(_('first name'), max_length=100, blank=True)
    last_name = models.CharField(_('last name'), max_length=100, blank=True)

    status = models.CharField(
        _('status'), max_length=12,
        choices=StatusChoices.choices, default=StatusChoices.PENDING,
        db_index=True,
    )

    administrative_level = models.ForeignKey(
        'geography.AdministrativeLevel',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='users',
        verbose_name=_('administrative level'),
    )

    is_staff = models.BooleanField(_('staff status'), default=False)
    is_active = models.BooleanField(_('active'), default=True)
    date_joined = models.DateTimeField(_('date joined'), default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = 'phone'
    REQUIRED_FIELDS = []

    class Meta:
        verbose_name = _('user')
        verbose_name_plural = _('users')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'is_deleted']),
            models.Index(fields=['cin']),
            models.Index(fields=['email']),
            models.Index(fields=['phone']),
            models.Index(fields=['administrative_level']),
        ]

    def __str__(self):
        return self.get_full_name() or self.phone

    def get_full_name(self):
        full = f'{self.first_name} {self.last_name}'.strip()
        return full or self.phone

    def get_short_name(self):
        return self.first_name or self.phone

    @property
    def role_names(self) -> list[str]:
        return list(
            self.user_roles.select_related('role')
            .values_list('role__name', flat=True)
        )

    def has_role(self, role_name: str) -> bool:
        return self.user_roles.filter(role__name=role_name, is_active=True).exists()

    def has_scoped_role(self, role_name: str, scope: str, entity_id: str | None = None) -> bool:
        qs = self.user_roles.filter(
            role__name=role_name,
            role__scope=scope,
            is_active=True,
        )
        if entity_id:
            qs = qs.filter(entity_id=entity_id)
        return qs.exists()


# ---------------------------------------------------------------------------
# Role & UserRole (RBAC)
# ---------------------------------------------------------------------------

class Role(BaseModel):
    """
    Named role with a scope. Roles are assigned to users through UserRole.

    Scopes:
      PRIVATE  — pharmacy-level operations
      PUBLIC   — public health facility operations
      NATIONAL — ministry / national-level operations
    """

    class ScopeChoices(models.TextChoices):
        PRIVATE = 'PRIVATE', _('Private Sector')
        PUBLIC = 'PUBLIC', _('Public Sector')
        NATIONAL = 'NATIONAL', _('National')

    name = models.CharField(_('name'), max_length=60, unique=True)
    description = models.TextField(_('description'), blank=True)
    scope = models.CharField(
        _('scope'), max_length=10,
        choices=ScopeChoices.choices, db_index=True,
    )
    is_system = models.BooleanField(
        _('system role'), default=False,
        help_text=_('System roles cannot be deleted.'),
    )

    class Meta:
        verbose_name = _('role')
        verbose_name_plural = _('roles')
        ordering = ['scope', 'name']

    def __str__(self):
        return f'{self.name} ({self.get_scope_display()})'


class UserRole(BaseModel):
    """
    Associates a user with a role, optionally scoped to a specific entity
    (pharmacy ID, facility ID, province ID, etc.).
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='user_roles',
        verbose_name=_('user'),
    )
    role = models.ForeignKey(
        Role,
        on_delete=models.CASCADE,
        related_name='user_roles',
        verbose_name=_('role'),
    )
    entity_id = models.UUIDField(
        _('entity ID'), null=True, blank=True, db_index=True,
        help_text=_('Optional: pharmacy, facility, or admin-level PK this role is scoped to.'),
    )
    is_active = models.BooleanField(_('active'), default=True)

    class Meta:
        verbose_name = _('user role')
        verbose_name_plural = _('user roles')
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'role', 'entity_id'],
                name='unique_user_role_entity',
            ),
        ]
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['role', 'is_active']),
        ]

    def __str__(self):
        scope = f' → {self.entity_id}' if self.entity_id else ''
        return f'{self.user} ← {self.role.name}{scope}'


# ---------------------------------------------------------------------------
# OTP & Device Tokens
# ---------------------------------------------------------------------------

class OTPCode(models.Model):
    """
    One-time password for login verification, password reset, or
    phone/email verification. Codes are hashed before storage.
    """

    class PurposeChoices(models.TextChoices):
        LOGIN = 'LOGIN', _('Login')
        RESET = 'RESET', _('Password Reset')
        VERIFY = 'VERIFY', _('Verification')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='otp_codes',
    )
    code_hash = models.CharField(_('code hash'), max_length=128)
    purpose = models.CharField(
        _('purpose'), max_length=10,
        choices=PurposeChoices.choices, db_index=True,
    )
    expires_at = models.DateTimeField(_('expires at'))
    is_used = models.BooleanField(_('used'), default=False)
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)

    class Meta:
        verbose_name = _('OTP code')
        verbose_name_plural = _('OTP codes')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'purpose', 'is_used']),
        ]

    def __str__(self):
        return f'OTP:{self.purpose} for {self.user_id}'

    @staticmethod
    def hash_code(code: str) -> str:
        return hashlib.sha256(code.encode()).hexdigest()

    @classmethod
    def generate(cls, user, purpose: str) -> tuple['OTPCode', str]:
        """Create OTP, return (instance, plain_code). Caller sends the plain code."""
        plain = f'{secrets.randbelow(10**6):06d}'
        otp = cls.objects.create(
            user=user,
            code_hash=cls.hash_code(plain),
            purpose=purpose,
            expires_at=timezone.now() + timezone.timedelta(
                minutes=settings.OTP_EXPIRY_MINUTES,
            ),
        )
        return otp, plain

    @property
    def is_expired(self) -> bool:
        return timezone.now() > self.expires_at

    def verify(self, plain_code: str) -> bool:
        if self.is_used or self.is_expired:
            return False
        if self.hash_code(plain_code) == self.code_hash:
            self.is_used = True
            self.save(update_fields=['is_used'])
            return True
        return False


class DeviceToken(models.Model):
    """
    Trusted device token. Allows skipping OTP on recognised devices
    within the configured expiry window.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='device_tokens',
    )
    device_fingerprint = models.CharField(_('device fingerprint'), max_length=255, db_index=True)
    device_name = models.CharField(_('device name'), max_length=200, blank=True)
    last_seen = models.DateTimeField(_('last seen'), auto_now=True)
    is_trusted = models.BooleanField(_('trusted'), default=True)
    expires_at = models.DateTimeField(_('expires at'))
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)

    class Meta:
        verbose_name = _('device token')
        verbose_name_plural = _('device tokens')
        ordering = ['-last_seen']
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'device_fingerprint'],
                name='unique_user_device',
            ),
        ]

    def __str__(self):
        return f'{self.device_name or self.device_fingerprint[:20]} ({self.user})'

    @property
    def is_expired(self) -> bool:
        return timezone.now() > self.expires_at

    @property
    def is_valid(self) -> bool:
        return self.is_trusted and not self.is_expired
