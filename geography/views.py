"""
Geography — Views

Read-heavy ViewSet for administrative levels. Supports tree endpoint
for hierarchy rendering.

@file geography/views.py
"""

from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import AdministrativeLevel
from .permissions import CanModifyGeography
from .serializers import (
    AdministrativeLevelReadSerializer,
    AdministrativeLevelTreeSerializer,
    AdministrativeLevelWriteSerializer,
)
from .services import GeographyService


class AdministrativeLevelViewSet(viewsets.ModelViewSet):
    """
    CRUD for administrative levels.

    List / retrieve is open to any authenticated user.
    Create / update / delete restricted to NATIONAL_ADMIN.
    """

    permission_classes = [IsAuthenticated, CanModifyGeography]
    filterset_fields = ['level_type', 'parent']
    search_fields = ['name', 'code']
    ordering_fields = ['name', 'level_type', 'created_at']
    ordering = ['level_type', 'name']

    def get_queryset(self):
        return AdministrativeLevel.objects.select_related('parent')

    def get_serializer_class(self):
        if self.action in ('list', 'retrieve'):
            return AdministrativeLevelReadSerializer
        return AdministrativeLevelWriteSerializer

    @action(detail=False, methods=['get'], url_path='provinces')
    def provinces(self, request):
        qs = GeographyService.get_provinces()
        serializer = AdministrativeLevelReadSerializer(qs, many=True)
        return Response({'success': True, 'data': serializer.data})

    @action(detail=True, methods=['get'], url_path='children')
    def children(self, request, pk=None):
        qs = GeographyService.get_children(pk)
        serializer = AdministrativeLevelReadSerializer(qs, many=True)
        return Response({'success': True, 'data': serializer.data})

    @action(detail=True, methods=['get'], url_path='hierarchy')
    def hierarchy(self, request, pk=None):
        chain = GeographyService.get_hierarchy(pk)
        return Response({'success': True, 'data': chain})

    @action(detail=False, methods=['get'], url_path='tree')
    def tree(self, request):
        """Return the full province tree (depth limited to 2 by default)."""
        depth = int(request.query_params.get('depth', 2))
        provinces = AdministrativeLevel.objects.filter(
            level_type='PROVINCE',
        ).prefetch_related('children__children').order_by('name')
        serializer = AdministrativeLevelTreeSerializer(
            provinces, many=True, context={'depth': depth},
        )
        return Response({'success': True, 'data': serializer.data})
