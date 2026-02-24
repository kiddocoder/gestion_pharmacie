"""
Users — Signals

Audit logging for User model lifecycle events.

@file users/signals.py
"""

import logging

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from core.constants import AUDIT_ACTION_CREATE, AUDIT_ACTION_UPDATE
from core.services import AuditService
from users.models import User

logger = logging.getLogger('pharmatrack')

_pre_save_state: dict = {}


@receiver(pre_save, sender=User)
def user_pre_save(sender, instance, **kwargs):
    if instance.pk:
        try:
            old = User.objects.get(pk=instance.pk)
            _pre_save_state[str(instance.pk)] = AuditService.snapshot(old)
        except User.DoesNotExist:
            pass


@receiver(post_save, sender=User)
def user_post_save(sender, instance, created, **kwargs):
    action = AUDIT_ACTION_CREATE if created else AUDIT_ACTION_UPDATE
    old_values = _pre_save_state.pop(str(instance.pk), None)
    new_values = AuditService.snapshot(instance)

    if not created and old_values == new_values:
        return

    AuditService.log(
        actor=getattr(instance, '_current_user', None),
        action=action,
        model_name='User',
        object_id=str(instance.pk),
        old_values=old_values,
        new_values=new_values,
    )
