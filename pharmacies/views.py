"""
Pharmacies — Views

DRF ViewSets for pharmacy and document management. Approval/suspend
actions enforce state machine and document requirements.

@file pharmacies/views.py
"""

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Pharmacy, PharmacyDocument
from .permissions import CanApproveOrSuspendPharmacy, CanManagePharmacy
from .serializers import (
    PharmacyApproveSerializer,
    PharmacyDocumentReadSerializer,
    PharmacyDocumentWriteSerializer,
    PharmacyReadSerializer,
    PharmacySuspendSerializer,
    PharmacyWriteSerializer,
)
from .services import PharmacyDocumentService, PharmacyService


class PharmacyViewSet(viewsets.ModelViewSet):
    """
    CRUD and workflow actions for pharmacies.

    List/retrieve: authenticated.
    Create/update: NATIONAL_ADMIN or INSPECTOR.
    Approve/suspend: NATIONAL_ADMIN or INSPECTOR (with scope).
    """

    permission_classes = [IsAuthenticated, CanManagePharmacy]
    filterset_fields = ['status', 'pharmacy_type', 'administrative_level']
    search_fields = ['name', 'national_code', 'address', 'phone']
    ordering_fields = ['name', 'national_code', 'created_at', 'status']
    ordering = ['name']

    def get_queryset(self):
        return Pharmacy.objects.filter(is_deleted=False).select_related('administrative_level')

    def get_serializer_class(self):
        if self.action in ('list', 'retrieve'):
            return PharmacyReadSerializer
        if self.action == 'approve':
            return PharmacyApproveSerializer
        if self.action == 'suspend':
            return PharmacySuspendSerializer
        return PharmacyWriteSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        pharmacy = PharmacyService.create_pharmacy(
            actor=request.user,
            **serializer.validated_data,
        )
        read_serializer = PharmacyReadSerializer(pharmacy, context={'request': request})
        return Response(read_serializer.data, status=status.HTTP_201_CREATED)

    def perform_update(self, serializer):
        pharmacy = PharmacyService.update_pharmacy(
            pharmacy_id=self.get_object().pk,
            actor=self.request.user,
            **serializer.validated_data,
        )
        serializer.instance = pharmacy

    def perform_destroy(self, instance):
        instance.soft_delete(user=self.request.user)

    @action(
        detail=True,
        methods=['post'],
        url_path='approve',
        permission_classes=[IsAuthenticated, CanManagePharmacy, CanApproveOrSuspendPharmacy],
    )
    def approve(self, request, pk=None):
        ser = PharmacyApproveSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        pharmacy = PharmacyService.approve_pharmacy(
            pharmacy_id=pk,
            reason=ser.validated_data.get('reason', ''),
            actor=request.user,
        )
        return Response(
            PharmacyReadSerializer(pharmacy, context={'request': request}).data,
            status=status.HTTP_200_OK,
        )

    @action(
        detail=True,
        methods=['post'],
        url_path='suspend',
        permission_classes=[IsAuthenticated, CanManagePharmacy, CanApproveOrSuspendPharmacy],
    )
    def suspend(self, request, pk=None):
        ser = PharmacySuspendSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        pharmacy = PharmacyService.suspend_pharmacy(
            pharmacy_id=pk,
            reason=ser.validated_data.get('reason', ''),
            actor=request.user,
        )
        return Response(
            PharmacyReadSerializer(pharmacy, context={'request': request}).data,
            status=status.HTTP_200_OK,
        )

    @action(
        detail=True,
        methods=['get'],
        url_path='qr',
    )
    def qr(self, request, pk=None):
        """Return QR code URL; 404 if not approved or no QR generated."""
        pharmacy = self.get_object()
        if not pharmacy.qr_code:
            return Response(
                {'detail': 'QR code not available for this pharmacy.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        url = request.build_absolute_uri(pharmacy.qr_code.url)
        return Response({'qr_code_url': url})

    @action(
        detail=True,
        methods=['get', 'post'],
        url_path='documents',
    )
    def documents(self, request, pk=None):
        """List or create documents for this pharmacy."""
        pharmacy = self.get_object()
        if request.method == 'GET':
            docs = pharmacy.documents.filter(is_deleted=False)
            ser = PharmacyDocumentReadSerializer(
                docs, many=True, context={'request': request},
            )
            return Response(ser.data)
        # POST
        ser = PharmacyDocumentWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        doc = PharmacyDocumentService.create_document(
            pharmacy_id=pharmacy.pk,
            actor=request.user,
            **ser.validated_data,
        )
        return Response(
            PharmacyDocumentReadSerializer(doc, context={'request': request}).data,
            status=status.HTTP_201_CREATED,
        )
