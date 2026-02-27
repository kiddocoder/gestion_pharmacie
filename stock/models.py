"""
Stock — Models

Movement-based, immutable stock tracking. Stock is never stored as a balance;
it is computed as SUM(inbound) - SUM(outbound) per (entity_type, entity_id, lot).
Records are INSERT ONLY — never update or delete.

@file stock/models.py
"""

import uuid

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


# Inbound: increase stock. Outbound: decrease stock.
INBOUND_TYPES = {'IMPORT', 'B2B_IN', 'RETURN'}
OUTBOUND_TYPES = {'B2B_OUT', 'SALE', 'RECALL_REMOVAL'}
# ADJUSTMENT can be + or - depending on quantity sign; handled in service.


class StockMovement(models.Model):
    """
    A single immutable stock movement (insert only).

    entity_type + entity_id identify the holder (pharmacy or public facility);
    lot identifies the product batch. Balance is computed by aggregating
    movements. created_at is the partition key for range partitioning.
    """

    class EntityType(models.TextChoices):
        PHARMACY = 'PHARMACY', _('Pharmacy')
        PUBLIC_FACILITY = 'PUBLIC_FACILITY', _('Public facility')

    class MovementType(models.TextChoices):
        IMPORT = 'IMPORT', _('Import')
        B2B_IN = 'B2B_IN', _('B2B in')
        B2B_OUT = 'B2B_OUT', _('B2B out')
        SALE = 'SALE', _('Sale')
        RETURN = 'RETURN', _('Return')
        ADJUSTMENT = 'ADJUSTMENT', _('Adjustment')
        RECALL_REMOVAL = 'RECALL_REMOVAL', _('Recall removal')

    id = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False,
    )
    entity_type = models.CharField(
        _('entity type'), max_length=16,
        choices=EntityType.choices, db_index=True,
    )
    entity_id = models.UUIDField(
        _('entity ID'),
        help_text=_('UUID of pharmacy or public facility; FK resolved in application layer'),
        db_index=True,
    )
    lot = models.ForeignKey(
        'medicines.NationalLot',
        on_delete=models.PROTECT,
        related_name='stock_movements',
        verbose_name=_('lot'),
    )
    movement_type = models.CharField(
        _('movement type'), max_length=16,
        choices=MovementType.choices, db_index=True,
    )
    quantity = models.PositiveIntegerField(_('quantity'))
    reference_id = models.UUIDField(
        _('reference ID'), null=True, blank=True,
        help_text=_('Source record: B2BOrder, InspectionFine, etc.'),
    )
    reference_type = models.CharField(
        _('reference type'), max_length=100, blank=True,
        help_text=_('Model name of source record'),
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
        verbose_name=_('created by'),
    )
    created_at = models.DateTimeField(
        _('created at'), auto_now_add=True, db_index=True,
    )
    # No updated_at — immutable record.

    class Meta:
        verbose_name = _('stock movement')
        verbose_name_plural = _('stock movements')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['entity_type', 'entity_id', 'lot'], name='stock_entity_lot_idx'),
            models.Index(fields=['lot', 'created_at'], name='stock_lot_created_idx'),
            models.Index(fields=['created_by', 'created_at'], name='stock_created_by_idx'),
        ]
        # DBA: table is designed for PARTITION BY RANGE (created_at)

    def __str__(self):
        return f'{self.movement_type} {self.quantity} lot={self.lot_id} entity={self.entity_type}:{self.entity_id}'

    def save(self, *args, **kwargs):
        if self.pk and StockMovement.objects.filter(pk=self.pk).exists():
            raise NotImplementedError('StockMovement is insert-only; updates are not allowed.')
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise NotImplementedError('StockMovement records cannot be deleted.')
