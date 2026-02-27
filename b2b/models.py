"""
B2B — Models

Wholesaler-to-retailer orders with state machine, order items (lot, quantity, unit price),
and pharmacy credit (limit, balance, reserved). Dual stock movements on delivery.

@file b2b/models.py
"""

import uuid

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from core.models import BaseModel, RegulatedModel


class PharmacyCredit(BaseModel):
    """
    Credit line for a pharmacy (typically retailer) for B2B orders.

    On order approval: reserved_balance increases atomically.
    On delivery: current_balance increases, reserved_balance decreases.
    On cancellation: reserved_balance decreases.
    Available credit = credit_limit - current_balance - reserved_balance.
    """

    pharmacy = models.OneToOneField(
        'pharmacies.Pharmacy',
        on_delete=models.CASCADE,
        related_name='credit',
        verbose_name=_('pharmacy'),
    )
    credit_limit = models.DecimalField(
        _('credit limit'), max_digits=15, decimal_places=2,
        help_text=_('Maximum credit in BIF'),
    )
    current_balance = models.DecimalField(
        _('current balance'), max_digits=15, decimal_places=2, default=0,
        help_text=_('Outstanding amount used (delivered orders not yet paid)'),
    )
    reserved_balance = models.DecimalField(
        _('reserved balance'), max_digits=15, decimal_places=2, default=0,
        help_text=_('Reserved for approved orders not yet delivered'),
    )

    class Meta:
        verbose_name = _('pharmacy credit')
        verbose_name_plural = _('pharmacy credits')
        ordering = ['pharmacy__name']

    def __str__(self):
        return f'{self.pharmacy.name} — limit {self.credit_limit}'

    @property
    def available_credit(self):
        return self.credit_limit - self.current_balance - self.reserved_balance


class B2BOrder(RegulatedModel):
    """
    Order from a retailer (buyer) to a wholesaler (seller).

    State machine: DRAFT → SUBMITTED → APPROVED → IN_TRANSIT → DELIVERED,
    or SUBMITTED → REJECTED, or DRAFT/SUBMITTED/APPROVED/IN_TRANSIT → CANCELLED.
    """

    class StatusChoices(models.TextChoices):
        DRAFT = 'DRAFT', _('Draft')
        SUBMITTED = 'SUBMITTED', _('Submitted')
        APPROVED = 'APPROVED', _('Approved')
        IN_TRANSIT = 'IN_TRANSIT', _('In transit')
        DELIVERED = 'DELIVERED', _('Delivered')
        CANCELLED = 'CANCELLED', _('Cancelled')
        REJECTED = 'REJECTED', _('Rejected')

    class PaymentStatusChoices(models.TextChoices):
        PENDING = 'PENDING', _('Pending')
        PARTIAL = 'PARTIAL', _('Partial')
        PAID = 'PAID', _('Paid')

    seller = models.ForeignKey(
        'pharmacies.Pharmacy',
        on_delete=models.PROTECT,
        related_name='b2b_orders_sold',
        verbose_name=_('seller'),
        limit_choices_to={'pharmacy_type': 'WHOLESALER'},
    )
    buyer = models.ForeignKey(
        'pharmacies.Pharmacy',
        on_delete=models.PROTECT,
        related_name='b2b_orders_bought',
        verbose_name=_('buyer'),
        limit_choices_to={'pharmacy_type': 'RETAILER'},
    )
    status = models.CharField(
        _('status'), max_length=12,
        choices=StatusChoices.choices,
        default=StatusChoices.DRAFT,
        db_index=True,
    )
    total_amount = models.DecimalField(
        _('total amount (BIF)'), max_digits=15, decimal_places=2, default=0,
    )
    credit_used = models.DecimalField(
        _('credit used (BIF)'), max_digits=15, decimal_places=2, default=0,
    )
    payment_status = models.CharField(
        _('payment status'), max_length=10,
        choices=PaymentStatusChoices.choices,
        default=PaymentStatusChoices.PENDING,
        db_index=True,
    )
    price_override_approved = models.BooleanField(
        _('price override approved'), default=False,
        help_text=_('When True, unit prices may exceed medicine authorized price'),
    )

    class Meta:
        verbose_name = _('B2B order')
        verbose_name_plural = _('B2B orders')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['seller', 'status']),
            models.Index(fields=['buyer', 'status']),
            models.Index(fields=['status', 'is_deleted']),
        ]

    def __str__(self):
        return f'Order {self.pk} — {self.seller.name} → {self.buyer.name} ({self.status})'


class B2BOrderItem(RegulatedModel):
    """
    Line item of a B2B order: lot, quantity ordered/delivered, unit price.

    unit_price must match NationalMedicine.authorized_price unless exception granted.
    """

    order = models.ForeignKey(
        B2BOrder,
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name=_('order'),
    )
    lot = models.ForeignKey(
        'medicines.NationalLot',
        on_delete=models.PROTECT,
        related_name='b2b_order_items',
        verbose_name=_('lot'),
    )
    quantity_ordered = models.PositiveIntegerField(_('quantity ordered'))
    quantity_delivered = models.PositiveIntegerField(_('quantity delivered'), default=0)
    unit_price = models.DecimalField(
        _('unit price (BIF)'), max_digits=15, decimal_places=2,
    )

    class Meta:
        verbose_name = _('B2B order item')
        verbose_name_plural = _('B2B order items')
        ordering = ['order', 'id']
        indexes = [
            models.Index(fields=['order']),
            models.Index(fields=['lot']),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity_delivered__lte=models.F('quantity_ordered')),
                name='b2b_item_delivered_lte_ordered',
            ),
        ]

    def __str__(self):
        return f'{self.order_id} — {self.lot} × {self.quantity_ordered}'

    @property
    def line_total(self):
        return self.unit_price * self.quantity_ordered
