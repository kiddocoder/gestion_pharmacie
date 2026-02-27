"""
Pharmacies — Models

Private pharmacy lifecycle: Pharmacy (wholesaler/retailer) with commune-level
location, status workflow, and PharmacyDocument for licenses and compliance.
QR code generated on approval; all status transitions audited.

@file pharmacies/models.py
"""

import uuid

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from core.models import RegulatedModel


class Pharmacy(RegulatedModel):
    """
    A private pharmacy (wholesaler or retailer) registered in the system.

    national_code is unique and auto-generated on creation (format PH-PROV-XXXX).
    QR code is generated when status moves to APPROVED and stored via default
    storage (S3 in production).
    """

    class TypeChoices(models.TextChoices):
        WHOLESALER = 'WHOLESALER', _('Wholesaler')
        RETAILER = 'RETAILER', _('Retailer')

    class StatusChoices(models.TextChoices):
        PENDING = 'PENDING', _('Pending')
        APPROVED = 'APPROVED', _('Approved')
        SUSPENDED = 'SUSPENDED', _('Suspended')
        ILLEGAL = 'ILLEGAL', _('Illegal')

    name = models.CharField(
        _('name'), max_length=255,
        help_text=_('Official or trading name of the pharmacy'),
    )
    pharmacy_type = models.CharField(
        _('type'), max_length=12,
        choices=TypeChoices.choices,
        db_index=True,
    )
    national_code = models.CharField(
        _('national code'), max_length=20, unique=True, blank=True,
        help_text=_('Auto-generated format: PH-PROV-XXXX'),
        db_index=True,
    )
    latitude = models.DecimalField(
        _('latitude'), max_digits=9, decimal_places=6,
        null=True, blank=True,
    )
    longitude = models.DecimalField(
        _('longitude'), max_digits=9, decimal_places=6,
        null=True, blank=True,
    )
    administrative_level = models.ForeignKey(
        'geography.AdministrativeLevel',
        on_delete=models.PROTECT,
        related_name='pharmacies',
        verbose_name=_('commune'),
        help_text=_('Commune-level administrative level'),
        limit_choices_to={'level_type': 'COMMUNE'},
    )
    status = models.CharField(
        _('status'), max_length=12,
        choices=StatusChoices.choices,
        default=StatusChoices.PENDING,
        db_index=True,
    )
    qr_code = models.ImageField(
        _('QR code'), upload_to='pharmacy_qr/%Y/%m/',
        null=True, blank=True,
        help_text=_('Generated on approval; stored in default storage (S3 in production)'),
    )
    address = models.CharField(
        _('address'), max_length=500, blank=True,
    )
    phone = models.CharField(_('phone'), max_length=20, blank=True)
    metadata = models.JSONField(
        _('metadata'), default=dict, blank=True,
    )

    class Meta:
        verbose_name = _('pharmacy')
        verbose_name_plural = _('pharmacies')
        ordering = ['name']
        indexes = [
            models.Index(fields=['status', 'is_deleted']),
            models.Index(fields=['pharmacy_type', 'status']),
            models.Index(fields=['administrative_level']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['national_code'],
                condition=models.Q(is_deleted=False) & ~models.Q(national_code=''),
                name='unique_active_pharmacy_national_code',
            ),
        ]

    def __str__(self):
        code = f' ({self.national_code})' if self.national_code else ''
        return f'{self.name}{code}'


class PharmacyDocument(RegulatedModel):
    """
    A document attached to a pharmacy (license, tax clearance, diploma, etc.).

    Status is PENDING until reviewed; APPROVED or REJECTED by authorized users.
    """

    class DocumentTypeChoices(models.TextChoices):
        LICENSE = 'LICENSE', _('License')
        TAX_CLEARANCE = 'TAX_CLEARANCE', _('Tax clearance')
        PHARMACIST_DIPLOMA = 'PHARMACIST_DIPLOMA', _('Pharmacist diploma')
        OTHER = 'OTHER', _('Other')

    class StatusChoices(models.TextChoices):
        PENDING = 'PENDING', _('Pending')
        APPROVED = 'APPROVED', _('Approved')
        REJECTED = 'REJECTED', _('Rejected')

    pharmacy = models.ForeignKey(
        Pharmacy,
        on_delete=models.CASCADE,
        related_name='documents',
        verbose_name=_('pharmacy'),
    )
    document_type = models.CharField(
        _('document type'), max_length=24,
        choices=DocumentTypeChoices.choices,
        db_index=True,
    )
    file = models.FileField(
        _('file'), upload_to='pharmacy_documents/%Y/%m/',
        help_text=_('Uploaded file; stored in default storage (S3 in production)'),
    )
    status = models.CharField(
        _('status'), max_length=10,
        choices=StatusChoices.choices,
        default=StatusChoices.PENDING,
        db_index=True,
    )
    expiry_date = models.DateField(
        _('expiry date'), null=True, blank=True,
    )
    rejection_reason = models.CharField(
        _('rejection reason'), max_length=500, blank=True,
    )

    class Meta:
        verbose_name = _('pharmacy document')
        verbose_name_plural = _('pharmacy documents')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['pharmacy', 'document_type']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f'{self.get_document_type_display()} — {self.pharmacy.name}'
