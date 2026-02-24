"""
Users — Django Admin Configuration

Full admin panel for User, Role, UserRole, OTPCode, and DeviceToken.
Soft-deleted users excluded by default with a separate view.

@file users/admin.py
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from .models import DeviceToken, OTPCode, Role, User, UserRole


# ---------------------------------------------------------------------------
# Inline for UserRole within User admin
# ---------------------------------------------------------------------------

class UserRoleInline(admin.TabularInline):
    model = UserRole
    fk_name = 'user'
    extra = 0
    readonly_fields = ('created_at',)
    raw_id_fields = ('role',)
    fields = ('role', 'entity_id', 'is_active', 'created_at')


# ---------------------------------------------------------------------------
# User Admin
# ---------------------------------------------------------------------------

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """
    Full-featured admin for User model with status badges, geographic
    filtering, and inline role management.
    """

    list_display = (
        'phone', 'get_full_name', 'cin', 'email',
        'status_badge', 'administrative_level', 'is_staff',
        'date_joined',
    )
    list_filter = (
        'status', 'is_staff', 'is_superuser', 'is_deleted',
        'administrative_level__level_type',
    )
    search_fields = ('phone', 'email', 'cin', 'first_name', 'last_name')
    readonly_fields = (
        'id', 'created_at', 'updated_at', 'created_by', 'updated_by',
        'date_joined', 'last_login',
    )
    date_hierarchy = 'created_at'
    list_select_related = ('administrative_level',)
    show_full_result_count = False
    list_per_page = 30
    ordering = ('-created_at',)
    inlines = [UserRoleInline]

    fieldsets = (
        (None, {
            'fields': ('id', 'phone', 'password'),
        }),
        (_('Personal Info'), {
            'fields': ('first_name', 'last_name', 'cin', 'email'),
        }),
        (_('Status & Location'), {
            'fields': ('status', 'administrative_level'),
        }),
        (_('Permissions'), {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
        }),
        (_('Audit'), {
            'fields': ('date_joined', 'last_login', 'created_at', 'updated_at', 'created_by', 'updated_by'),
            'classes': ('collapse',),
        }),
        (_('Soft Delete'), {
            'fields': ('is_deleted', 'deleted_at', 'deleted_by'),
            'classes': ('collapse',),
        }),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('phone', 'password1', 'password2', 'first_name', 'last_name'),
        }),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if not request.GET.get('is_deleted__exact'):
            qs = qs.filter(is_deleted=False)
        return qs

    @admin.display(description=_('Status'))
    def status_badge(self, obj):
        colors = {
            'PENDING': '#eab308',
            'ACTIVE': '#22c55e',
            'SUSPENDED': '#f97316',
            'REJECTED': '#ef4444',
        }
        color = colors.get(obj.status, '#6b7280')
        return format_html(
            '<span style="background:{}; color:#fff; padding:2px 8px; '
            'border-radius:4px; font-size:11px; font-weight:600;">{}</span>',
            color, obj.get_status_display(),
        )

    def get_full_name(self, obj):
        return obj.get_full_name()
    get_full_name.short_description = _('Full Name')


# ---------------------------------------------------------------------------
# Role Admin
# ---------------------------------------------------------------------------

@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ('name', 'scope', 'is_system', 'description', 'created_at')
    list_filter = ('scope', 'is_system')
    search_fields = ('name', 'description')
    readonly_fields = ('id', 'created_at', 'updated_at', 'created_by', 'updated_by')
    list_per_page = 50

    fieldsets = (
        (None, {
            'fields': ('id', 'name', 'description', 'scope', 'is_system'),
        }),
        (_('Audit'), {
            'fields': ('created_at', 'updated_at', 'created_by', 'updated_by'),
            'classes': ('collapse',),
        }),
    )


# ---------------------------------------------------------------------------
# UserRole Admin
# ---------------------------------------------------------------------------

@admin.register(UserRole)
class UserRoleAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'entity_id', 'is_active', 'created_at')
    list_filter = ('role__scope', 'is_active', 'role')
    search_fields = ('user__phone', 'user__email', 'role__name')
    readonly_fields = ('id', 'created_at', 'updated_at', 'created_by', 'updated_by')
    raw_id_fields = ('user', 'role')
    list_select_related = ('user', 'role')
    list_per_page = 50

    fieldsets = (
        (None, {
            'fields': ('id', 'user', 'role', 'entity_id', 'is_active'),
        }),
        (_('Audit'), {
            'fields': ('created_at', 'updated_at', 'created_by', 'updated_by'),
            'classes': ('collapse',),
        }),
    )


# ---------------------------------------------------------------------------
# OTP Admin (read-only for security)
# ---------------------------------------------------------------------------

@admin.register(OTPCode)
class OTPCodeAdmin(admin.ModelAdmin):
    list_display = ('user', 'purpose', 'is_used', 'expires_at', 'created_at')
    list_filter = ('purpose', 'is_used')
    search_fields = ('user__phone',)
    readonly_fields = ('id', 'user', 'code_hash', 'purpose', 'expires_at', 'is_used', 'created_at')
    list_select_related = ('user',)
    list_per_page = 50

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


# ---------------------------------------------------------------------------
# DeviceToken Admin
# ---------------------------------------------------------------------------

@admin.register(DeviceToken)
class DeviceTokenAdmin(admin.ModelAdmin):
    list_display = ('user', 'device_name', 'device_fingerprint_short', 'is_trusted', 'last_seen', 'expires_at')
    list_filter = ('is_trusted',)
    search_fields = ('user__phone', 'device_name', 'device_fingerprint')
    readonly_fields = ('id', 'created_at', 'last_seen')
    raw_id_fields = ('user',)
    list_select_related = ('user',)
    list_per_page = 50

    @admin.display(description=_('Fingerprint'))
    def device_fingerprint_short(self, obj):
        return f'{obj.device_fingerprint[:24]}…' if len(obj.device_fingerprint) > 24 else obj.device_fingerprint
