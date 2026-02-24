"""
Users — Auth URL Configuration

Endpoints: login, refresh, logout, OTP, me.

@file users/urls.py
"""

from django.urls import path

from .views import (
    LoginView,
    LogoutView,
    MeView,
    OTPRequestView,
    OTPVerifyView,
    TokenRefreshAPIView,
)

app_name = 'auth'

urlpatterns = [
    path('login/', LoginView.as_view(), name='login'),
    path('refresh/', TokenRefreshAPIView.as_view(), name='token-refresh'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('otp/request/', OTPRequestView.as_view(), name='otp-request'),
    path('otp/verify/', OTPVerifyView.as_view(), name='otp-verify'),
    path('me/', MeView.as_view(), name='me'),
]
