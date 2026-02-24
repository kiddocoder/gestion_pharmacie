"""
Users — Serializers

Read and write serializers for User, Role, UserRole, and custom
JWT token claims.

@file users/serializers.py
"""

from django.contrib.auth import authenticate
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import DeviceToken, OTPCode, Role, User, UserRole


# ---------------------------------------------------------------------------
# JWT — custom claims
# ---------------------------------------------------------------------------

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Inject roles, scope, and entity into JWT payload."""

    username_field = 'phone'

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['phone'] = user.phone
        token['status'] = user.status

        roles_data = (
            UserRole.objects
            .filter(user=user, is_active=True)
            .select_related('role')
            .values_list('role__name', 'role__scope', 'entity_id')
        )
        token['roles'] = [
            {'name': name, 'scope': scope, 'entity_id': str(eid) if eid else None}
            for name, scope, eid in roles_data
        ]
        return token

    def validate(self, attrs):
        phone = attrs.get('phone')
        password = attrs.get('password')

        user = authenticate(
            request=self.context.get('request'),
            phone=phone,
            password=password,
        )

        if user is None:
            raise serializers.ValidationError(
                {'detail': 'Invalid credentials or account not active.'},
                code='authentication_failed',
            )

        if user.status != User.StatusChoices.ACTIVE:
            raise serializers.ValidationError(
                {'detail': f'Account status is {user.status}. Only ACTIVE accounts can log in.'},
                code='account_inactive',
            )

        data = super().validate(attrs)
        data['user'] = UserReadSerializer(user).data
        return data


# ---------------------------------------------------------------------------
# Auth serializers
# ---------------------------------------------------------------------------

class LoginSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=20)
    password = serializers.CharField(write_only=True)


class OTPRequestSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=20)
    purpose = serializers.ChoiceField(
        choices=OTPCode.PurposeChoices.choices,
        default=OTPCode.PurposeChoices.LOGIN,
    )


class OTPVerifySerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=20)
    code = serializers.CharField(max_length=6, min_length=6)
    purpose = serializers.ChoiceField(
        choices=OTPCode.PurposeChoices.choices,
        default=OTPCode.PurposeChoices.LOGIN,
    )
    device_fingerprint = serializers.CharField(max_length=255, required=False)
    device_name = serializers.CharField(max_length=200, required=False, default='')


# ---------------------------------------------------------------------------
# User serializers
# ---------------------------------------------------------------------------

class UserReadSerializer(serializers.ModelSerializer):
    """Read-only user representation — returned in list / detail views."""

    roles = serializers.SerializerMethodField()
    administrative_level_name = serializers.CharField(
        source='administrative_level.__str__', read_only=True, default=None,
    )

    class Meta:
        model = User
        fields = [
            'id', 'cin', 'phone', 'email', 'first_name', 'last_name',
            'status', 'administrative_level', 'administrative_level_name',
            'is_staff', 'is_active', 'date_joined', 'roles',
            'created_at', 'updated_at',
        ]
        read_only_fields = fields

    def get_roles(self, obj):
        return list(
            obj.user_roles
            .filter(is_active=True)
            .select_related('role')
            .values('role__name', 'role__scope', 'entity_id')
        )


class UserWriteSerializer(serializers.ModelSerializer):
    """Create / update users. Password is write-only."""

    password = serializers.CharField(write_only=True, required=False, min_length=10)

    class Meta:
        model = User
        fields = [
            'cin', 'phone', 'email', 'first_name', 'last_name',
            'password', 'status', 'administrative_level',
        ]

    def validate_phone(self, value):
        qs = User.objects.filter(phone=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError('Phone number already in use.')
        return value

    def validate_cin(self, value):
        if not value:
            return value
        qs = User.objects.filter(cin=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError('CIN already in use.')
        return value

    def validate_email(self, value):
        if not value:
            return value
        qs = User.objects.filter(email=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError('Email already in use.')
        return value


class ChangeStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=User.StatusChoices.choices)
    reason = serializers.CharField(required=False, default='')


# ---------------------------------------------------------------------------
# Role serializers
# ---------------------------------------------------------------------------

class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = ['id', 'name', 'description', 'scope', 'is_system', 'created_at']
        read_only_fields = ['id', 'created_at']


class UserRoleWriteSerializer(serializers.Serializer):
    role_name = serializers.CharField(max_length=60)
    entity_id = serializers.UUIDField(required=False, allow_null=True)


class UserRoleReadSerializer(serializers.ModelSerializer):
    role_name = serializers.CharField(source='role.name', read_only=True)
    role_scope = serializers.CharField(source='role.scope', read_only=True)

    class Meta:
        model = UserRole
        fields = ['id', 'role_name', 'role_scope', 'entity_id', 'is_active', 'created_at']
        read_only_fields = fields
