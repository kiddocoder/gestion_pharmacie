"""
Medicines — Signals

Audit logging for NationalMedicine and NationalLot lifecycle events.

@file medicines/signals.py
"""

import logging

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from core.constants import AUDIT_ACTION_CREATE, AUDIT_ACTION_UPDATE
from core.services import AuditService

from .models import NationalLot, NationalMedicine

logger = logging.getLogger('pharmatrack')

_medicine_pre: dict = {}
_lot_pre: dict = {}


@receiver(pre_save, sender=NationalMedicine)
def medicine_pre_save(sender, instance, **kwargs):
    if instance.pk:
        try:
            old = NationalMedicine.objects.get(pk=instance.pk)
            _medicine_pre[str(instance.pk)] = AuditService.snapshot(old)
        except NationalMedicine.DoesNotExist:
            pass


@receiver(post_save, sender=NationalMedicine)
def medicine_post_save(sender, instance, created, **kwargs):
    action = AUDIT_ACTION_CREATE if created else AUDIT_ACTION_UPDATE
    old = _medicine_pre.pop(str(instance.pk), None)
    new = AuditService.snapshot(instance)
    if not created and old == new:
        return
    AuditService.log(
        actor=getattr(instance, '_current_user', None),
        action=action,
        model_name='NationalMedicine',
        object_id=str(instance.pk),
        old_values=old,
        new_values=new,
    )


@receiver(pre_save, sender=NationalLot)
def lot_pre_save(sender, instance, **kwargs):
    if instance.pk:
        try:
            old = NationalLot.objects.get(pk=instance.pk)
            _lot_pre[str(instance.pk)] = AuditService.snapshot(old)
        except NationalLot.DoesNotExist:
            pass


@receiver(post_save, sender=NationalLot)
def lot_post_save(sender, instance, created, **kwargs):
    action = AUDIT_ACTION_CREATE if created else AUDIT_ACTION_UPDATE
    old = _lot_pre.pop(str(instance.pk), None)
    new = AuditService.snapshot(instance)
    if not created and old == new:
        return
    AuditService.log(
        actor=getattr(instance, '_current_user', None),
        action=action,
        model_name='NationalLot',
        object_id=str(instance.pk),
        old_values=old,
        new_values=new,
    )
