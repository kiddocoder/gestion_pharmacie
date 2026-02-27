"""
B2B — URL Configuration

@file b2b/urls.py
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import B2BOrderViewSet

app_name = 'b2b'

router = DefaultRouter()
router.register('orders', B2BOrderViewSet, basename='order')

urlpatterns = [
    path('', include(router.urls)),
]
