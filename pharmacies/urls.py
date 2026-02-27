"""
Pharmacies — URL Configuration

@file pharmacies/urls.py
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import PharmacyViewSet

app_name = 'pharmacies'

router = DefaultRouter()
router.register('', PharmacyViewSet, basename='pharmacy')

urlpatterns = [
    path('', include(router.urls)),
]
