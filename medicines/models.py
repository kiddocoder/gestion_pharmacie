"""
Medicines — Models

Authoritative national registry of all medicines authorized to circulate
in Burundi, plus per-import lot tracking with expiry and recall lifecycle.

@file medicines/models.py
"""

import re

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from core.models import RegulatedModel

ATC_CODE_REGEX = re.compile(r'^[A-Z]\d{2}[A-Z]{2}\d{2}$')


class NationalMedicine(RegulatedModel):
    """
    A medicine authorised by Burundi's national regulatory authority.

    Each entry represents a unique product defined by its ATC code,
    INN, dosage form, strength, and packaging. The authorized_price
    is the maximum price enforceable nationwide.
    """

    class StatusChoices(models.TextChoices):
        AUTHORIZED = 'AUTHORIZED', _('Authorized')
        BLOCKED = 'BLOCKED', _('Blocked')

    class DosageFormChoices(models.TextChoices):
        TABLET = 'TABLET', _('Tablet')
        CAPSULE = 'CAPSULE', _('Capsule')
        SYRUP = 'SYRUP', _('Syrup')
        INJECTION = 'INJECTION', _('Injectable')
        CREAM = 'CREAM', _('Cream / Ointment')
        DROPS = 'DROPS', _('Drops')
        INHALER = 'INHALER', _('Inhaler')
        SUPPOSITORY = 'SUPPOSITORY', _('Suppository')
        POWDER = 'POWDER', _('Powder')
        SUSPENSION = 'SUSPENSION', _('Suspension')
        SOLUTION = 'SOLUTION', _('Solution')
        OTHER = 'OTHER', _('Other')

    atc_code = models.CharField(
        _('ATC code'), max_length=7,
        help_text=_('WHO ATC classification code (e.g. N02BE01)'),
        db_index=True,
    )
    inn = models.CharField(
        _('INN'), max_length=255,
        help_text=_('International Nonproprietary Name (e.g. Paracetamol)'),
    )
    brand_name = models.CharField(
        _('brand name'), max_length=255, blank=True,
    )
    dosage_form = models.CharField(
        _('dosage form'), max_length=20,
        choices=DosageFormChoices.choices,
    )
    strength = models.CharField(
        _('strength'), max_length=100,
        help_text=_('e.g. 500mg, 250mg/5ml'),
    )
    packaging = models.CharField(
        _('packaging'), max_length=200,
        help_text=_('e.g. Box of 20 tablets, Bottle of 100ml'),
        blank=True,
    )
    manufacturer = models.CharField(
        _('manufacturer'), max_length=255, blank=True,
    )
    country_of_origin = models.CharField(
        _('country of origin'), max_length=100, blank=True,
    )
    authorized_price = models.DecimalField(
        _('authorized price (BIF)'), max_digits=15, decimal_places=2,
        help_text=_('Maximum regulated selling price in Burundian Francs'),
    )
    is_controlled = models.BooleanField(
        _('controlled substance'), default=False,
        help_text=_('Narcotics, psychotropics, or other controlled substances'),
        db_index=True,
    )
    status = models.CharField(
        _('status'), max_length=12,
        choices=StatusChoices.choices,
        default=StatusChoices.AUTHORIZED,
        db_index=True,
    )
    description = models.TextField(_('description'), blank=True)
    metadata = models.JSONField(
        _('metadata'), default=dict, blank=True,
        help_text=_('Flexible structured data for regulatory details'),
    )

    class Meta:
        verbose_name = _('national medicine')
        verbose_name_plural = _('national medicines')
        ordering = ['inn', 'strength']
        indexes = [
            models.Index(fields=['status', 'is_deleted']),
            models.Index(fields=['atc_code']),
            models.Index(fields=['inn']),
            models.Index(fields=['is_controlled', 'status']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['atc_code', 'dosage_form', 'strength', 'packaging', 'manufacturer'],
                condition=models.Q(is_deleted=False),
                name='unique_active_medicine_variant',
            ),
        ]

    def __str__(self):
        label = self.brand_name or self.inn
        return f'{label} {self.strength} ({self.get_dosage_form_display()})'

    def clean(self):
        super().clean()
        if self.atc_code and not ATC_CODE_REGEX.match(self.atc_code):
            raise ValidationError({
                'atc_code': _('Invalid ATC code format. Expected pattern: A00AA00 (e.g. N02BE01).'),
            })


class NationalLot(RegulatedModel):
    """
    A specific import batch of a nationally registered medicine.

    Lots are immutable in their core identity (batch_number, medicine,
    dates). Status transitions are tracked via AuditLog.
    """

    class StatusChoices(models.TextChoices):
        ACTIVE = 'ACTIVE', _('Active')
        BLOCKED = 'BLOCKED', _('Blocked')
        EXPIRED = 'EXPIRED', _('Expired')
        RECALLED = 'RECALLED', _('Recalled')

    medicine = models.ForeignKey(
        NationalMedicine,
        on_delete=models.PROTECT,
        related_name='lots',
        verbose_name=_('medicine'),
    )
    batch_number = models.CharField(
        _('batch number'), max_length=100,
        help_text=_('Import batch / lot number'),
    )
    manufacturing_date = models.DateField(
        _('manufacturing date'),
    )
    expiry_date = models.DateField(
        _('expiry date'), db_index=True,
    )
    quantity_imported = models.PositiveIntegerField(
        _('quantity imported'),
    )
    import_reference = models.CharField(
        _('import reference'), max_length=100, blank=True,
        help_text=_('Customs declaration or import permit number'),
    )
    supplier = models.CharField(
        _('supplier'), max_length=255, blank=True,
    )
    status = models.CharField(
        _('status'), max_length=10,
        choices=StatusChoices.choices,
        default=StatusChoices.ACTIVE,
        db_index=True,
    )
    recall_reason = models.TextField(
        _('recall reason'), blank=True,
        help_text=_('Reason for recall, if applicable'),
    )
    metadata = models.JSONField(
        _('metadata'), default=dict, blank=True,
    )

    class Meta:
        verbose_name = _('national lot')
        verbose_name_plural = _('national lots')
        ordering = ['-expiry_date']
        indexes = [
            models.Index(fields=['medicine', 'status']),
            models.Index(fields=['status', 'expiry_date']),
            models.Index(fields=['batch_number']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['medicine', 'batch_number'],
                condition=models.Q(is_deleted=False),
                name='unique_active_lot_batch',
            ),
            models.CheckConstraint(
                condition=models.Q(expiry_date__gt=models.F('manufacturing_date')),
                name='lot_expiry_after_manufacturing',
            ),
            models.CheckConstraint(
                condition=models.Q(quantity_imported__gt=0),
                name='lot_positive_quantity',
            ),
        ]

    def __str__(self):
        return f'Lot {self.batch_number} — {self.medicine}'

    @property
    def is_expired(self) -> bool:
        if not self.expiry_date:
            return False
        return self.expiry_date < timezone.now().date()

    @property
    def days_to_expiry(self) -> int | None:
        if not self.expiry_date:
            return None
        return (self.expiry_date - timezone.now().date()).days

    @property
    def is_usable(self) -> bool:
        """A lot can only back stock movements if ACTIVE."""
        return self.status == self.StatusChoices.ACTIVE and not self.is_expired

    def clean(self):
        super().clean()
        if self.expiry_date and self.manufacturing_date:
            if self.expiry_date <= self.manufacturing_date:
                raise ValidationError({
                    'expiry_date': _('Expiry date must be after manufacturing date.'),
                })
