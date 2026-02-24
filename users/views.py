"""
Users — Views

Auth endpoints (login, refresh, OTP, logout) and user management
CRUD ViewSet.

@file users/views.py
"""

import logging

from django.contrib.auth import authenticate
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView

from core.constants import AUDIT_ACTION_LOGIN, AUDIT_ACTION_LOGIN_FAILED, AUDIT_ACTION_LOGOUT
from core.services import AuditService

from .models import User
from .permissions import HasRole, IsActiveUser, IsNationalAdmin
from .serializers import (
    ChangeStatusSerializer,
    CustomTokenObtainPairSerializer,
    OTPRequestSerializer,
    OTPVerifySerializer,
    RoleSerializer,
    UserReadSerializer,
    UserRoleReadSerializer,
    UserRoleWriteSerializer,
    UserWriteSerializer,
)
from .services import AuthService, RoleService, UserService

logger = logging.getLogger('pharmatrack')


# ---------------------------------------------------------------------------
# Auth views
# ---------------------------------------------------------------------------

class LoginView(APIView):
    """POST /v1/auth/login — Authenticate and obtain JWT pair."""
    permission_classes = [AllowAny]
    throttle_scope = 'anon'

    def post(self, request):
        serializer = CustomTokenObtainPairSerializer(
            data=request.data, context={'request': request},
        )
        serializer.is_valid(raise_exception=True)

        user_data = serializer.validated_data.get('user')
        user_obj = User.objects.get(phone=request.data.get('phone'))

        AuthService.log_auth_event(
            action=AUDIT_ACTION_LOGIN,
            user=user_obj,
            ip_address=AuditService.get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
        )

        return Response({
            'success': True,
            'data': {
                'access': serializer.validated_data['access'],
                'refresh': serializer.validated_data['refresh'],
                'user': user_data,
            },
        })


class LogoutView(APIView):
    """POST /v1/auth/logout — Blacklist the refresh token."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get('refresh')
        if refresh_token:
            try:
                token = RefreshToken(refresh_token)
                token.blacklist()
            except Exception:
                pass

        AuthService.log_auth_event(
            action=AUDIT_ACTION_LOGOUT,
            user=request.user,
            ip_address=AuditService.get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
        )

        return Response({'success': True, 'data': None}, status=status.HTTP_200_OK)


class OTPRequestView(APIView):
    """POST /v1/auth/otp/request — Generate and (in prod) send an OTP."""
    permission_classes = [AllowAny]
    throttle_scope = 'anon'

    def post(self, request):
        serializer = OTPRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            user = User.objects.get(
                phone=serializer.validated_data['phone'], is_deleted=False,
            )
        except User.DoesNotExist:
            return Response(
                {'success': True, 'data': {'message': 'If the phone exists, an OTP was sent.'}},
            )

        plain_code = AuthService.generate_otp(user, serializer.validated_data['purpose'])
        logger.info('OTP for %s: %s (dev only)', user.phone, plain_code)

        return Response({
            'success': True,
            'data': {'message': 'If the phone exists, an OTP was sent.'},
        })


class OTPVerifyView(APIView):
    """POST /v1/auth/otp/verify — Verify OTP and optionally register device."""
    permission_classes = [AllowAny]
    throttle_scope = 'anon'

    def post(self, request):
        serializer = OTPVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            user = User.objects.get(phone=data['phone'], is_deleted=False)
        except User.DoesNotExist:
            return Response(
                {'success': False, 'errors': {'detail': ['Invalid code.']}, 'code': 'INVALID_OTP'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not AuthService.verify_otp(user, data['code'], data['purpose']):
            return Response(
                {'success': False, 'errors': {'detail': ['Invalid or expired code.']}, 'code': 'INVALID_OTP'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if data.get('device_fingerprint'):
            AuthService.register_device(user, data['device_fingerprint'], data.get('device_name', ''))

        refresh = RefreshToken.for_user(user)
        return Response({
            'success': True,
            'data': {
                'access': str(refresh.access_token),
                'refresh': str(refresh),
                'user': UserReadSerializer(user).data,
            },
        })


class TokenRefreshAPIView(TokenRefreshView):
    """POST /v1/auth/refresh — Rotate refresh token."""
    pass


class MeView(APIView):
    """GET /v1/auth/me — Return the current authenticated user."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({
            'success': True,
            'data': UserReadSerializer(request.user).data,
        })


# ---------------------------------------------------------------------------
# User management ViewSet
# ---------------------------------------------------------------------------

class UserViewSet(viewsets.ModelViewSet):
    """
    CRUD for user accounts. List/retrieve available to staff;
    create/update require NATIONAL_ADMIN or appropriate role.
    """

    permission_classes = [IsActiveUser, HasRole]
    required_roles = ['NATIONAL_ADMIN', 'PROVINCIAL_ADMIN']
    filterset_fields = ['status', 'is_staff', 'administrative_level']
    search_fields = ['phone', 'email', 'cin', 'first_name', 'last_name']
    ordering_fields = ['created_at', 'first_name', 'last_name', 'status']
    ordering = ['-created_at']

    def get_queryset(self):
        return (
            User.objects
            .filter(is_deleted=False)
            .select_related('administrative_level')
            .prefetch_related('user_roles__role')
        )

    def get_serializer_class(self):
        if self.action in ('list', 'retrieve'):
            return UserReadSerializer
        return UserWriteSerializer

    def perform_create(self, serializer):
        password = serializer.validated_data.pop('password', None)
        user = UserService.create_user(
            phone=serializer.validated_data['phone'],
            password=password,
            actor=self.request.user,
            **{k: v for k, v in serializer.validated_data.items() if k != 'phone'},
        )
        serializer.instance = user

    def perform_update(self, serializer):
        password = serializer.validated_data.pop('password', None)
        user = UserService.update_user(
            user_id=self.get_object().pk,
            actor=self.request.user,
            **serializer.validated_data,
        )
        if password:
            user.set_password(password)
            user.save(update_fields=['password'])
        serializer.instance = user

    def perform_destroy(self, instance):
        instance.soft_delete(user=self.request.user)

    @action(detail=True, methods=['post'], url_path='change-status')
    def change_status(self, request, pk=None):
        serializer = ChangeStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = UserService.change_status(
            user_id=pk,
            new_status=serializer.validated_data['status'],
            actor=request.user,
            reason=serializer.validated_data.get('reason', ''),
        )
        return Response({'success': True, 'data': UserReadSerializer(user).data})

    @action(detail=True, methods=['post'], url_path='assign-role')
    def assign_role(self, request, pk=None):
        serializer = UserRoleWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = self.get_object()
        user_role = RoleService.assign_role(
            user=user,
            role_name=serializer.validated_data['role_name'],
            entity_id=serializer.validated_data.get('entity_id'),
            actor=request.user,
        )
        return Response(
            {'success': True, 'data': UserRoleReadSerializer(user_role).data},
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=['post'], url_path='revoke-role')
    def revoke_role(self, request, pk=None):
        serializer = UserRoleWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = self.get_object()
        RoleService.revoke_role(
            user=user,
            role_name=serializer.validated_data['role_name'],
            entity_id=serializer.validated_data.get('entity_id'),
            actor=request.user,
        )
        return Response({'success': True, 'data': None})

    @action(detail=True, methods=['get'], url_path='roles')
    def roles(self, request, pk=None):
        user = self.get_object()
        roles_data = RoleService.get_user_roles(user)
        return Response({'success': True, 'data': roles_data})
