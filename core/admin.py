"""
Core — Django Admin Configuration

Read-only admin for AuditLog.

@file core/admin.py
"""

from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from core.models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    """Read-only audit log viewer for administrators."""

    list_display = (
        'timestamp', 'action_badge', 'model_name', 'object_id',
        'actor', 'ip_address',
    )
    list_filter = ('action', 'model_name', 'timestamp')
    search_fields = ('object_id', 'model_name', 'actor__email', 'actor__phone')
    readonly_fields = (
        'id', 'actor', 'action', 'model_name', 'object_id',
        'old_values', 'new_values', 'ip_address', 'user_agent', 'timestamp',
    )
    date_hierarchy = 'timestamp'
    list_select_related = ('actor',)
    show_full_result_count = False
    list_per_page = 50
    ordering = ('-timestamp',)

    fieldsets = (
        (_('Event'), {
            'fields': ('id', 'action', 'timestamp', 'actor', 'ip_address', 'user_agent'),
        }),
        (_('Target'), {
            'fields': ('model_name', 'object_id'),
        }),
        (_('Data'), {
            'fields': ('old_values', 'new_values'),
            'classes': ('collapse',),
        }),
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description=_('Action'))
    def action_badge(self, obj):
        colors = {
            'CREATE': '#22c55e',
            'UPDATE': '#3b82f6',
            'DELETE': '#ef4444',
            'SOFT_DELETE': '#f97316',
            'RESTORE': '#8b5cf6',
            'STATUS_CHANGE': '#eab308',
            'LOGIN': '#06b6d4',
            'LOGOUT': '#6b7280',
            'LOGIN_FAILED': '#dc2626',
        }
        color = colors.get(obj.action, '#6b7280')
        return format_html(
            '<span style="background:{}; color:#fff; padding:2px 8px; '
            'border-radius:4px; font-size:11px; font-weight:600;">{}</span>',
            color, obj.get_action_display(),
        )
