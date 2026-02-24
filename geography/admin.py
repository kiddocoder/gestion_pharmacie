"""
Geography — Django Admin Configuration

Tree-like display of administrative levels with parent chain,
filter by level_type, and proper search.

@file geography/admin.py
"""

from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from .models import AdministrativeLevel


@admin.register(AdministrativeLevel)
class AdministrativeLevelAdmin(admin.ModelAdmin):
    """Admin for the Burundi administrative hierarchy."""

    list_display = (
        'name', 'code', 'level_type_badge', 'parent_display',
        'children_count', 'created_at',
    )
    list_filter = ('level_type',)
    search_fields = ('name', 'code')
    readonly_fields = ('id', 'created_at', 'updated_at', 'created_by', 'updated_by')
    raw_id_fields = ('parent',)
    list_select_related = ('parent',)
    show_full_result_count = False
    list_per_page = 50
    ordering = ('level_type', 'name')

    fieldsets = (
        (None, {
            'fields': ('id', 'name', 'code', 'level_type', 'parent'),
        }),
        (_('Audit'), {
            'fields': ('created_at', 'updated_at', 'created_by', 'updated_by'),
            'classes': ('collapse',),
        }),
    )

    @admin.display(description=_('Level'))
    def level_type_badge(self, obj):
        colors = {
            'PROVINCE': '#1d4ed8',
            'COMMUNE': '#7c3aed',
            'ZONE': '#0891b2',
            'COLLINE': '#65a30d',
        }
        color = colors.get(obj.level_type, '#6b7280')
        return format_html(
            '<span style="background:{}; color:#fff; padding:2px 8px; '
            'border-radius:4px; font-size:11px; font-weight:600;">{}</span>',
            color, obj.get_level_type_display(),
        )

    @admin.display(description=_('Parent'))
    def parent_display(self, obj):
        if obj.parent:
            return f'{obj.parent.name} ({obj.parent.get_level_type_display()})'
        return '—'

    @admin.display(description=_('Children'))
    def children_count(self, obj):
        return obj.children.count()
