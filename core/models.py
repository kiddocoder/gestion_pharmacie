"""
Core — Base Models & Audit Infrastructure

Provides reusable abstract models for timestamps, soft-delete, and
audit trail fields. Also defines the AuditLog model for tracking every
write operation across the platform.

@file core/models.py
"""

import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


# ---------------------------------------------------------------------------
# Abstract base models (mixins)
# ---------------------------------------------------------------------------

class TimestampMixin(models.Model):
    """Adds created_at / updated_at to any model."""

    created_at = models.DateTimeField(
        _('created at'), auto_now_add=True, db_index=True,
    )
    updated_at = models.DateTimeField(
        _('updated at'), auto_now=True,
    )

    class Meta:
        abstract = True


class AuditFieldsMixin(models.Model):
    """Adds created_by / updated_by foreign keys for actor tracking."""

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
        verbose_name=_('created by'),
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
        verbose_name=_('updated by'),
    )

    class Meta:
        abstract = True


class SoftDeleteMixin(models.Model):
    """
    Regulatory soft-delete. Records are never physically removed;
    instead is_deleted, deleted_at, deleted_by are set.
    """

    is_deleted = models.BooleanField(_('deleted'), default=False, db_index=True)
    deleted_at = models.DateTimeField(_('deleted at'), null=True, blank=True)
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
        verbose_name=_('deleted by'),
    )

    class Meta:
        abstract = True

    def soft_delete(self, user=None):
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.deleted_by = user
        self.save(update_fields=['is_deleted', 'deleted_at', 'deleted_by', 'updated_at'])

    def restore(self, user=None):
        self.is_deleted = False
        self.deleted_at = None
        self.deleted_by = None
        self.save(update_fields=['is_deleted', 'deleted_at', 'deleted_by', 'updated_at'])


class BaseModel(TimestampMixin, AuditFieldsMixin):
    """
    Standard base for all PharmaTrack models.
    UUID PK + timestamps + actor audit fields.
    """

    id = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False,
    )

    class Meta:
        abstract = True


class RegulatedModel(BaseModel, SoftDeleteMixin):
    """
    Extended base for regulatory/financial models that must never be
    hard-deleted.
    """

    class Meta:
        abstract = True


# ---------------------------------------------------------------------------
# Audit Log — immutable record of every write operation
# ---------------------------------------------------------------------------

class AuditLog(models.Model):
    """
    Immutable audit trail. One row per create / update / soft-delete
    across the entire platform.

    Stores old and new values as JSONB for full diff capability.
    """

    class ActionChoices(models.TextChoices):
        CREATE = 'CREATE', _('Create')
        UPDATE = 'UPDATE', _('Update')
        DELETE = 'DELETE', _('Delete')
        SOFT_DELETE = 'SOFT_DELETE', _('Soft Delete')
        RESTORE = 'RESTORE', _('Restore')
        STATUS_CHANGE = 'STATUS_CHANGE', _('Status Change')
        LOGIN = 'LOGIN', _('Login')
        LOGOUT = 'LOGOUT', _('Logout')
        LOGIN_FAILED = 'LOGIN_FAILED', _('Login Failed')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='audit_logs',
        verbose_name=_('actor'),
    )
    action = models.CharField(
        _('action'), max_length=20,
        choices=ActionChoices.choices, db_index=True,
    )
    model_name = models.CharField(_('model'), max_length=100, db_index=True)
    object_id = models.CharField(_('object ID'), max_length=40, db_index=True)

    old_values = models.JSONField(_('old values'), null=True, blank=True)
    new_values = models.JSONField(_('new values'), null=True, blank=True)

    ip_address = models.GenericIPAddressField(_('IP address'), null=True, blank=True)
    user_agent = models.TextField(_('user agent'), blank=True, default='')

    timestamp = models.DateTimeField(_('timestamp'), auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = _('audit log')
        verbose_name_plural = _('audit logs')
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['model_name', 'object_id']),
            models.Index(fields=['actor', 'timestamp']),
            models.Index(fields=['action', 'timestamp']),
        ]

    def __str__(self):
        return f'{self.action} {self.model_name}:{self.object_id} by {self.actor_id}'
