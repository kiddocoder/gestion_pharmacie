"""
Medicines — Django Admin Configuration

Full admin for NationalMedicine and NationalLot with expiry color
coding, batch recall action, and comprehensive filters.

@file medicines/admin.py
"""

from django.contrib import admin
from django.utils import timezone
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from .models import NationalLot, NationalMedicine


# ---------------------------------------------------------------------------
# NationalLot Inline
# ---------------------------------------------------------------------------

class NationalLotInline(admin.TabularInline):
    model = NationalLot
    fk_name = 'medicine'
    extra = 0
    readonly_fields = ('id', 'expiry_badge', 'status', 'created_at')
    fields = (
        'batch_number', 'manufacturing_date', 'expiry_date',
        'expiry_badge', 'quantity_imported', 'status', 'created_at',
    )
    show_change_link = True

    @admin.display(description=_('Expiry'))
    def expiry_badge(self, obj):
        if not obj.pk:
            return '—'
        return _render_expiry_badge(obj)


# ---------------------------------------------------------------------------
# NationalMedicine Admin
# ---------------------------------------------------------------------------

@admin.register(NationalMedicine)
class NationalMedicineAdmin(admin.ModelAdmin):
    list_display = (
        'inn', 'brand_name', 'atc_code', 'dosage_form', 'strength',
        'formatted_price', 'controlled_badge', 'status_badge',
        'lots_count', 'created_at',
    )
    list_filter = ('status', 'dosage_form', 'is_controlled', 'is_deleted')
    search_fields = ('inn', 'brand_name', 'atc_code', 'manufacturer')
    readonly_fields = (
        'id', 'created_at', 'updated_at', 'created_by', 'updated_by',
    )
    date_hierarchy = 'created_at'
    list_select_related = True
    show_full_result_count = False
    list_per_page = 30
    ordering = ('inn',)
    inlines = [NationalLotInline]

    fieldsets = (
        (_('Identification'), {
            'fields': ('id', 'atc_code', 'inn', 'brand_name'),
        }),
        (_('Product Details'), {
            'fields': ('dosage_form', 'strength', 'packaging', 'manufacturer', 'country_of_origin'),
        }),
        (_('Regulation'), {
            'fields': ('authorized_price', 'is_controlled', 'status', 'description'),
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
        return qs.prefetch_related('lots')

    @admin.display(description=_('Price (BIF)'), ordering='authorized_price')
    def formatted_price(self, obj):
        return f'{obj.authorized_price:,.0f}'

    @admin.display(description=_('Controlled'))
    def controlled_badge(self, obj):
        if obj.is_controlled:
            return format_html(
                '<span style="background:#dc2626;color:#fff;padding:2px 8px;'
                'border-radius:4px;font-size:11px;font-weight:600;">CTRL</span>',
            )
        return '—'

    @admin.display(description=_('Status'))
    def status_badge(self, obj):
        colors = {'AUTHORIZED': '#22c55e', 'BLOCKED': '#ef4444'}
        color = colors.get(obj.status, '#6b7280')
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;'
            'border-radius:4px;font-size:11px;font-weight:600;">{}</span>',
            color, obj.get_status_display(),
        )

    @admin.display(description=_('Active lots'))
    def lots_count(self, obj):
        return obj.lots.filter(status='ACTIVE', is_deleted=False).count()


# ---------------------------------------------------------------------------
# NationalLot Admin
# ---------------------------------------------------------------------------

def _render_expiry_badge(obj):
    """Shared helper for expiry color coding."""
    days = obj.days_to_expiry
    if days is None:
        return '—'
    if days < 0:
        color, label = '#dc2626', f'EXPIRED ({abs(days)}d ago)'
    elif days <= 30:
        color, label = '#ef4444', f'{days}d left'
    elif days <= 90:
        color, label = '#f97316', f'{days}d left'
    elif days <= 180:
        color, label = '#eab308', f'{days}d left'
    else:
        color, label = '#22c55e', f'{days}d left'
    return format_html(
        '<span style="background:{};color:#fff;padding:2px 8px;'
        'border-radius:4px;font-size:11px;font-weight:600;">{}</span>',
        color, label,
    )


@admin.action(description=_('Mark selected lots as RECALLED'))
def mark_recalled(modeladmin, request, queryset):
    updated = queryset.filter(
        status__in=['ACTIVE', 'BLOCKED'],
    ).update(status=NationalLot.StatusChoices.RECALLED)
    modeladmin.message_user(request, f'{updated} lot(s) marked as recalled.')


@admin.register(NationalLot)
class NationalLotAdmin(admin.ModelAdmin):
    list_display = (
        'batch_number', 'medicine', 'manufacturing_date',
        'expiry_date', 'expiry_badge', 'quantity_imported',
        'status_badge', 'created_at',
    )
    list_filter = (
        'status', 'medicine__is_controlled',
        'medicine__dosage_form', 'is_deleted',
    )
    search_fields = (
        'batch_number', 'import_reference',
        'medicine__inn', 'medicine__brand_name', 'medicine__atc_code',
    )
    readonly_fields = (
        'id', 'expiry_badge', 'days_to_expiry',
        'created_at', 'updated_at', 'created_by', 'updated_by',
    )
    raw_id_fields = ('medicine',)
    date_hierarchy = 'expiry_date'
    list_select_related = ('medicine',)
    show_full_result_count = False
    list_per_page = 30
    ordering = ('expiry_date',)
    actions = [mark_recalled]

    fieldsets = (
        (_('Lot Identification'), {
            'fields': ('id', 'medicine', 'batch_number'),
        }),
        (_('Dates & Quantity'), {
            'fields': ('manufacturing_date', 'expiry_date', 'expiry_badge', 'days_to_expiry', 'quantity_imported'),
        }),
        (_('Import Details'), {
            'fields': ('import_reference', 'supplier'),
        }),
        (_('Status'), {
            'fields': ('status', 'recall_reason'),
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
        return qs

    @admin.display(description=_('Expiry'))
    def expiry_badge(self, obj):
        return _render_expiry_badge(obj)

    @admin.display(description=_('Days'))
    def days_to_expiry(self, obj):
        return obj.days_to_expiry

    @admin.display(description=_('Status'))
    def status_badge(self, obj):
        colors = {
            'ACTIVE': '#22c55e', 'BLOCKED': '#f97316',
            'EXPIRED': '#dc2626', 'RECALLED': '#7c3aed',
        }
        color = colors.get(obj.status, '#6b7280')
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;'
            'border-radius:4px;font-size:11px;font-weight:600;">{}</span>',
            color, obj.get_status_display(),
        )
