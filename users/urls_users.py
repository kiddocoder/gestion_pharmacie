"""
Users — User Management URL Configuration

CRUD ViewSet routed under /v1/users/.

@file users/urls_users.py
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import UserViewSet

app_name = 'users'

router = DefaultRouter()
router.register('', UserViewSet, basename='user')

urlpatterns = [
    path('', include(router.urls)),
]
