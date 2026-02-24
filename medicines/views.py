"""
Medicines — Views

DRF ViewSets for the national medicine registry and lot management.

@file medicines/views.py
"""

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import NationalLot, NationalMedicine
from .permissions import CanBlockMedicine, CanModifyMedicine, CanRecallLot
from .serializers import (
    LotRecallSerializer,
    MedicineBlockSerializer,
    NationalLotNestedWriteSerializer,
    NationalLotReadSerializer,
    NationalLotWriteSerializer,
    NationalMedicineReadSerializer,
    NationalMedicineWriteSerializer,
)
from .services import LotService, MedicineService


class NationalMedicineViewSet(viewsets.ModelViewSet):
    """
    CRUD for the national medicine registry.

    List/retrieve open to any authenticated user.
    Create/update restricted to NATIONAL_ADMIN / NATIONAL_PHARMACIST.
    """

    permission_classes = [IsAuthenticated, CanModifyMedicine]
    filterset_fields = ['status', 'is_controlled', 'dosage_form', 'atc_code']
    search_fields = ['inn', 'brand_name', 'atc_code', 'manufacturer']
    ordering_fields = ['inn', 'authorized_price', 'created_at', 'atc_code']
    ordering = ['inn']

    def get_queryset(self):
        return NationalMedicine.objects.filter(is_deleted=False)

    def get_serializer_class(self):
        if self.action in ('list', 'retrieve'):
            return NationalMedicineReadSerializer
        return NationalMedicineWriteSerializer

    def perform_create(self, serializer):
        medicine = MedicineService.create_medicine(
            actor=self.request.user, **serializer.validated_data,
        )
        serializer.instance = medicine

    def perform_update(self, serializer):
        medicine = MedicineService.update_medicine(
            medicine_id=self.get_object().pk,
            actor=self.request.user,
            **serializer.validated_data,
        )
        serializer.instance = medicine

    def perform_destroy(self, instance):
        instance.soft_delete(user=self.request.user)

    # --- Block / Unblock ---

    @action(
        detail=True, methods=['post'], url_path='block',
        permission_classes=[IsAuthenticated, CanBlockMedicine],
    )
    def block(self, request, pk=None):
        ser = MedicineBlockSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        medicine = MedicineService.block_medicine(
            medicine_id=pk,
            reason=ser.validated_data.get('reason', ''),
            actor=request.user,
        )
        return Response({
            'success': True,
            'data': NationalMedicineReadSerializer(medicine).data,
        })

    @action(
        detail=True, methods=['post'], url_path='unblock',
        permission_classes=[IsAuthenticated, CanBlockMedicine],
    )
    def unblock(self, request, pk=None):
        medicine = MedicineService.unblock_medicine(
            medicine_id=pk, actor=request.user,
        )
        return Response({
            'success': True,
            'data': NationalMedicineReadSerializer(medicine).data,
        })

    # --- Nested lots ---

    @action(detail=True, methods=['get', 'post'], url_path='lots')
    def lots(self, request, pk=None):
        medicine = self.get_object()

        if request.method == 'GET':
            lots = NationalLot.objects.filter(
                medicine=medicine, is_deleted=False,
            ).order_by('-expiry_date')
            page = self.paginate_queryset(lots)
            if page is not None:
                ser = NationalLotReadSerializer(page, many=True)
                return self.get_paginated_response(ser.data)
            ser = NationalLotReadSerializer(lots, many=True)
            return Response({'success': True, 'data': ser.data})

        ser = NationalLotNestedWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        lot = LotService.create_lot(
            medicine=medicine, actor=request.user,
            **ser.validated_data,
        )
        return Response(
            {'success': True, 'data': NationalLotReadSerializer(lot).data},
            status=status.HTTP_201_CREATED,
        )


class NationalLotViewSet(viewsets.ModelViewSet):
    """
    Top-level lot endpoints for cross-medicine queries.
    """

    permission_classes = [IsAuthenticated, CanModifyMedicine]
    filterset_fields = ['status', 'medicine', 'medicine__is_controlled']
    search_fields = ['batch_number', 'import_reference', 'medicine__inn', 'medicine__brand_name']
    ordering_fields = ['expiry_date', 'created_at', 'batch_number']
    ordering = ['-expiry_date']

    def get_queryset(self):
        return (
            NationalLot.objects
            .filter(is_deleted=False)
            .select_related('medicine')
        )

    def get_serializer_class(self):
        if self.action in ('list', 'retrieve'):
            return NationalLotReadSerializer
        return NationalLotWriteSerializer

    def perform_create(self, serializer):
        lot = LotService.create_lot(actor=self.request.user, **serializer.validated_data)
        serializer.instance = lot

    def perform_update(self, serializer):
        lot = LotService.update_lot(
            lot_id=self.get_object().pk,
            actor=self.request.user,
            **serializer.validated_data,
        )
        serializer.instance = lot

    def perform_destroy(self, instance):
        instance.soft_delete(user=self.request.user)

    @action(
        detail=True, methods=['post'], url_path='recall',
        permission_classes=[IsAuthenticated, CanRecallLot],
    )
    def recall(self, request, pk=None):
        ser = LotRecallSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        lot = LotService.recall_lot(
            lot_id=pk, reason=ser.validated_data['reason'],
            actor=request.user,
        )
        return Response({
            'success': True,
            'data': NationalLotReadSerializer(lot).data,
        })

    @action(detail=False, methods=['get'], url_path='expiring-soon')
    def expiring_soon(self, request):
        days = int(request.query_params.get('days', 30))
        lots = LotService.get_expiring_soon(days=days)
        page = self.paginate_queryset(lots)
        if page is not None:
            ser = NationalLotReadSerializer(page, many=True)
            return self.get_paginated_response(ser.data)
        ser = NationalLotReadSerializer(lots, many=True)
        return Response({'success': True, 'data': ser.data})
