"""
Pharmacies — Django Admin Configuration

Full admin for Pharmacy and PharmacyDocument with status badges,
moderation queue for PENDING pharmacies and document status.

@file pharmacies/admin.py
"""

from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _

from .models import Pharmacy, PharmacyDocument


# ---------------------------------------------------------------------------
# PharmacyDocument Inline
# ---------------------------------------------------------------------------

class PharmacyDocumentInline(admin.TabularInline):
    model = PharmacyDocument
    extra = 0
    readonly_fields = ('id', 'document_type', 'status_badge', 'expiry_date', 'created_at')
    fields = ('document_type', 'file', 'status', 'status_badge', 'expiry_date', 'rejection_reason', 'created_at')
    show_change_link = True

    @admin.display(description=_('Status'))
    def status_badge(self, obj):
        if not obj.pk:
            return '—'
        colors = {'PENDING': '#f59e0b', 'APPROVED': '#22c55e', 'REJECTED': '#dc2626'}
        color = colors.get(obj.status, '#6b7280')
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;'
            'border-radius:4px;font-size:11px;font-weight:600;">{}</span>',
            color, obj.get_status_display(),
        )


# ---------------------------------------------------------------------------
# Pharmacy Admin
# ---------------------------------------------------------------------------

@admin.register(Pharmacy)
class PharmacyAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'national_code', 'pharmacy_type_badge', 'status_badge',
        'administrative_level', 'documents_summary', 'created_at',
    )
    list_filter = ('status', 'pharmacy_type', 'is_deleted')
    search_fields = ('name', 'national_code', 'address', 'phone')
    readonly_fields = (
        'id', 'national_code', 'qr_code', 'created_at', 'updated_at',
        'created_by', 'updated_by',
    )
    list_select_related = ('administrative_level',)
    show_full_result_count = False
    list_per_page = 30
    date_hierarchy = 'created_at'
    ordering = ('name',)
    inlines = [PharmacyDocumentInline]

    fieldsets = (
        (_('Identification'), {
            'fields': ('id', 'name', 'pharmacy_type', 'national_code'),
        }),
        (_('Location'), {
            'fields': ('administrative_level', 'latitude', 'longitude', 'address', 'phone'),
        }),
        (_('Status'), {
            'fields': ('status',),
        }),
        (_('QR Code'), {
            'fields': ('qr_code',),
            'classes': ('collapse',),
        }),
        (_('Metadata'), {
            'fields': ('metadata',),
            'classes': ('collapse',),
        }),
        (_('Audit'), {
            'fields': ('created_at', 'updated_at', 'created_by', 'updated_by'),
            'classes': ('collapse',),
        }),
        (_('Soft Delete'), {
            'fields': ('is_deleted', 'deleted_at', 'deleted_by'),
            'classes': ('collapse',),
        }),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if not request.GET.get('is_deleted__exact'):
            qs = qs.filter(is_deleted=False)
        return qs.prefetch_related('documents')

    @admin.display(description=_('Type'))
    def pharmacy_type_badge(self, obj):
        colors = {'WHOLESALER': '#3b82f6', 'RETAILER': '#8b5cf6'}
        color = colors.get(obj.pharmacy_type, '#6b7280')
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;'
            'border-radius:4px;font-size:11px;font-weight:600;">{}</span>',
            color, obj.get_pharmacy_type_display(),
        )

    @admin.display(description=_('Status'))
    def status_badge(self, obj):
        colors = {
            'PENDING': '#f59e0b',
            'APPROVED': '#22c55e',
            'SUSPENDED': '#f97316',
            'ILLEGAL': '#dc2626',
        }
        color = colors.get(obj.status, '#6b7280')
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;'
            'border-radius:4px;font-size:11px;font-weight:600;">{}</span>',
            color, obj.get_status_display(),
        )

    @admin.display(description=_('Documents'))
    def documents_summary(self, obj):
        """Moderation queue: show document status for PENDING pharmacies."""
        docs = list(obj.documents.filter(is_deleted=False))
        if not docs:
            return mark_safe('<span style="color:#dc2626;">No documents</span>')
        approved = sum(1 for d in docs if d.status == PharmacyDocument.StatusChoices.APPROVED)
        pending = sum(1 for d in docs if d.status == PharmacyDocument.StatusChoices.PENDING)
        parts = []
        if approved:
            parts.append(format_html('<span style="color:#22c55e;">{} approved</span>', approved))
        if pending:
            parts.append(format_html('<span style="color:#f59e0b;">{} pending</span>', pending))
        return mark_safe(' · '.join(parts) if parts else '—')


# ---------------------------------------------------------------------------
# PharmacyDocument Admin (standalone)
# ---------------------------------------------------------------------------

@admin.register(PharmacyDocument)
class PharmacyDocumentAdmin(admin.ModelAdmin):
    list_display = (
        'pharmacy', 'document_type', 'status_badge',
        'expiry_date', 'created_at',
    )
    list_filter = ('status', 'document_type')
    search_fields = ('pharmacy__name', 'pharmacy__national_code')
    readonly_fields = (
        'id', 'created_at', 'updated_at', 'created_by', 'updated_by',
    )
    list_select_related = ('pharmacy',)
    show_full_result_count = False
    list_per_page = 30
    date_hierarchy = 'created_at'
    raw_id_fields = ('pharmacy',)

    fieldsets = (
        (_('Document'), {
            'fields': ('id', 'pharmacy', 'document_type', 'file', 'expiry_date'),
        }),
        (_('Review'), {
            'fields': ('status', 'rejection_reason'),
        }),
        (_('Audit'), {
            'fields': ('created_at', 'updated_at', 'created_by', 'updated_by'),
            'classes': ('collapse',),
        }),
        (_('Soft Delete'), {
            'fields': ('is_deleted', 'deleted_at', 'deleted_by'),
            'classes': ('collapse',),
        }),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if not request.GET.get('is_deleted__exact'):
            qs = qs.filter(is_deleted=False)
        return qs

    @admin.display(description=_('Status'))
    def status_badge(self, obj):
        colors = {'PENDING': '#f59e0b', 'APPROVED': '#22c55e', 'REJECTED': '#dc2626'}
        color = colors.get(obj.status, '#6b7280')
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;'
            'border-radius:4px;font-size:11px;font-weight:600;">{}</span>',
            color, obj.get_status_display(),
        )
