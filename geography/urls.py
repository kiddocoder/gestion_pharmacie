"""
Geography — URL Configuration

@file geography/urls.py
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import AdministrativeLevelViewSet

app_name = 'geography'

router = DefaultRouter()
router.register('levels', AdministrativeLevelViewSet, basename='level')

urlpatterns = [
    path('', include(router.urls)),
]
