"""
B2B — Django Admin Configuration

Orders, order items, and pharmacy credit. Status badges and filters.

@file b2b/admin.py
"""

from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from .models import B2BOrder, B2BOrderItem, PharmacyCredit


class B2BOrderItemInline(admin.TabularInline):
    model = B2BOrderItem
    extra = 0
    readonly_fields = ('id', 'lot', 'quantity_ordered', 'quantity_delivered', 'unit_price', 'line_total_display', 'created_at')
    fields = ('lot', 'quantity_ordered', 'quantity_delivered', 'unit_price', 'line_total_display', 'created_at')
    show_change_link = True

    def line_total_display(self, obj):
        return obj.unit_price * obj.quantity_ordered if obj.pk else '—'
    line_total_display.short_description = _('Line total')


@admin.register(B2BOrder)
class B2BOrderAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'seller', 'buyer', 'status_badge', 'total_amount',
        'credit_used', 'payment_status', 'created_at',
    )
    list_filter = ('status', 'payment_status', 'is_deleted')
    search_fields = ('id', 'seller__name', 'buyer__name')
    readonly_fields = (
        'id', 'total_amount', 'credit_used', 'created_at', 'updated_at',
        'created_by', 'updated_by',
    )
    list_select_related = ('seller', 'buyer')
    show_full_result_count = False
    list_per_page = 30
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)
    inlines = [B2BOrderItemInline]
    raw_id_fields = ('seller', 'buyer')

    fieldsets = (
        (_('Parties'), {'fields': ('id', 'seller', 'buyer')}),
        (_('Status'), {'fields': ('status', 'payment_status', 'price_override_approved')}),
        (_('Amounts'), {'fields': ('total_amount', 'credit_used')}),
        (_('Audit'), {'fields': ('created_at', 'updated_at', 'created_by', 'updated_by'), 'classes': ('collapse',)}),
        (_('Soft Delete'), {'fields': ('is_deleted', 'deleted_at', 'deleted_by'), 'classes': ('collapse',)}),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if not request.GET.get('is_deleted__exact'):
            qs = qs.filter(is_deleted=False)
        return qs.prefetch_related('items')

    @admin.display(description=_('Status'))
    def status_badge(self, obj):
        colors = {
            'DRAFT': '#6b7280', 'SUBMITTED': '#f59e0b', 'APPROVED': '#22c55e',
            'IN_TRANSIT': '#3b82f6', 'DELIVERED': '#22c55e', 'CANCELLED': '#dc2626', 'REJECTED': '#dc2626',
        }
        color = colors.get(obj.status, '#6b7280')
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;'
            'border-radius:4px;font-size:11px;font-weight:600;">{}</span>',
            color, obj.get_status_display(),
        )


@admin.register(B2BOrderItem)
class B2BOrderItemAdmin(admin.ModelAdmin):
    list_display = ('id', 'order', 'lot', 'quantity_ordered', 'quantity_delivered', 'unit_price', 'created_at')
    list_filter = ('order__status',)
    search_fields = ('order__id', 'lot__batch_number')
    readonly_fields = ('id', 'created_at', 'updated_at', 'created_by', 'updated_by')
    list_select_related = ('order', 'lot', 'lot__medicine')
    show_full_result_count = False
    raw_id_fields = ('order', 'lot')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if not request.GET.get('is_deleted__exact'):
            qs = qs.filter(is_deleted=False)
        return qs


@admin.register(PharmacyCredit)
class PharmacyCreditAdmin(admin.ModelAdmin):
    list_display = ('pharmacy', 'credit_limit', 'current_balance', 'reserved_balance', 'available_display', 'created_at')
    list_filter = ()
    search_fields = ('pharmacy__name', 'pharmacy__national_code')
    readonly_fields = ('id', 'created_at', 'updated_at', 'created_by', 'updated_by')
    list_select_related = ('pharmacy',)
    raw_id_fields = ('pharmacy',)

    def available_display(self, obj):
        return obj.available_credit
    available_display.short_description = _('Available credit')
