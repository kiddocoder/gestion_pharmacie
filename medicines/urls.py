"""
Medicines — URL Configuration

@file medicines/urls.py
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import NationalLotViewSet, NationalMedicineViewSet

app_name = 'medicines'

router = DefaultRouter()
router.register('', NationalMedicineViewSet, basename='medicine')

lot_router = DefaultRouter()
lot_router.register('', NationalLotViewSet, basename='lot')

urlpatterns = [
    path('lots/', include((lot_router.urls, 'lots'))),
    path('', include(router.urls)),
]
