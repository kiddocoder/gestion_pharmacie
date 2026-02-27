"""
Stock — Django Admin Configuration

Read-only list of StockMovement. No edit, no delete (insert-only).
INSERT ONLY — model save() blocks updates; delete() raises.

@file stock/admin.py
"""

from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import StockMovement


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'entity_type', 'entity_id', 'lot', 'movement_type',
        'quantity', 'reference_type', 'reference_id', 'created_by', 'created_at',
    )
    list_filter = ('entity_type', 'movement_type', 'created_at')
    search_fields = ('reference_type',)
    readonly_fields = (
        'id', 'entity_type', 'entity_id', 'lot', 'movement_type',
        'quantity', 'reference_id', 'reference_type',
        'created_by', 'created_at',
    )
    list_select_related = ('lot', 'lot__medicine', 'created_by')
    show_full_result_count = False
    list_per_page = 50
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)

    fieldsets = (
        (_('Movement'), {
            'fields': ('id', 'entity_type', 'entity_id', 'lot', 'movement_type', 'quantity'),
        }),
        (_('Reference'), {
            'fields': ('reference_id', 'reference_type'),
        }),
        (_('Audit'), {
            'fields': ('created_by', 'created_at'),
        }),
    )

    def has_change_permission(self, request, obj=None):
        return False  # INSERT ONLY — no updates

    def has_delete_permission(self, request, obj=None):
        return False  # INSERT ONLY — no deletes
