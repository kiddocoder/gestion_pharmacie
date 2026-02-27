"""
B2B — Views

DRF ViewSet for B2B orders: CRUD and workflow actions (submit, approve,
ship, deliver, cancel, reject). Movements list for an order.

@file b2b/views.py
"""

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from stock.models import StockMovement

from .models import B2BOrder, B2BOrderItem
from .permissions import CanApproveOrRejectOrder, CanManageB2BOrder
from .serializers import (
    B2BOrderApproveSerializer,
    B2BOrderReadSerializer,
    B2BOrderUpdateSerializer,
    B2BOrderWriteSerializer,
    StockMovementMinimalSerializer,
)
from .services import B2BOrderService


class B2BOrderViewSet(viewsets.ModelViewSet):
    """
    B2B orders: list, create, retrieve, update (DRAFT only), destroy (soft delete).
    Workflow: submit, approve, ship, deliver, cancel, reject.
    """

    permission_classes = [IsAuthenticated, CanManageB2BOrder]
    filterset_fields = ['status', 'seller', 'buyer', 'payment_status']
    search_fields = ['id']
    ordering_fields = ['created_at', 'total_amount', 'status']
    ordering = ['-created_at']

    def get_queryset(self):
        return B2BOrder.objects.filter(is_deleted=False).select_related(
            'seller', 'buyer',
        ).prefetch_related('items__lot', 'items__lot__medicine')

    def get_serializer_class(self):
        if self.action in ('list', 'retrieve'):
            return B2BOrderReadSerializer
        if self.action in ('update', 'partial_update'):
            return B2BOrderUpdateSerializer
        if self.action == 'approve':
            return B2BOrderApproveSerializer
        return B2BOrderWriteSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order = B2BOrderService.create_order(
            seller_id=serializer.validated_data['seller_id'],
            buyer_id=serializer.validated_data['buyer_id'],
            items=serializer.validated_data['items'],
            actor=request.user,
            price_override_approved=serializer.validated_data.get('price_override_approved', False),
        )
        read_ser = B2BOrderReadSerializer(order, context={'request': request})
        return Response(read_ser.data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        order = self.get_object()
        if order.status != B2BOrder.StatusChoices.DRAFT:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({'status': 'Only DRAFT orders can be updated.'})
        serializer = self.get_serializer(data=request.data, partial=kwargs.get('partial', False))
        serializer.is_valid(raise_exception=True)
        updated = B2BOrderService.update_draft_order(
            order_id=order.pk,
            items=serializer.validated_data.get('items'),
            price_override_approved=serializer.validated_data.get('price_override_approved'),
            actor=request.user,
        )
        return Response(B2BOrderReadSerializer(updated, context={'request': request}).data)

    def perform_update(self, serializer):
        pass  # update() overridden above

    def perform_destroy(self, instance):
        instance.soft_delete(user=self.request.user)

    @action(
        detail=True,
        methods=['post'],
        url_path='submit',
        permission_classes=[IsAuthenticated, CanManageB2BOrder],
    )
    def submit(self, request, pk=None):
        order = B2BOrderService.submit_order(order_id=pk, actor=request.user)
        return Response(
            B2BOrderReadSerializer(order, context={'request': request}).data,
            status=status.HTTP_200_OK,
        )

    @action(
        detail=True,
        methods=['post'],
        url_path='approve',
        permission_classes=[IsAuthenticated, CanApproveOrRejectOrder],
    )
    def approve(self, request, pk=None):
        ser = B2BOrderApproveSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        credit_used = ser.validated_data.get('credit_used')
        order = B2BOrderService.approve_order(
            order_id=pk,
            credit_used=credit_used,
            actor=request.user,
        )
        return Response(
            B2BOrderReadSerializer(order, context={'request': request}).data,
            status=status.HTTP_200_OK,
        )

    @action(
        detail=True,
        methods=['post'],
        url_path='ship',
        permission_classes=[IsAuthenticated, CanApproveOrRejectOrder],
    )
    def ship(self, request, pk=None):
        order = B2BOrderService.ship_order(order_id=pk, actor=request.user)
        return Response(
            B2BOrderReadSerializer(order, context={'request': request}).data,
            status=status.HTTP_200_OK,
        )

    @action(
        detail=True,
        methods=['post'],
        url_path='deliver',
        permission_classes=[IsAuthenticated, CanApproveOrRejectOrder],
    )
    def deliver(self, request, pk=None):
        order = B2BOrderService.deliver_order(order_id=pk, actor=request.user)
        return Response(
            B2BOrderReadSerializer(order, context={'request': request}).data,
            status=status.HTTP_200_OK,
        )

    @action(
        detail=True,
        methods=['post'],
        url_path='cancel',
        permission_classes=[IsAuthenticated, CanApproveOrRejectOrder],
    )
    def cancel(self, request, pk=None):
        order = B2BOrderService.cancel_order(order_id=pk, actor=request.user)
        return Response(
            B2BOrderReadSerializer(order, context={'request': request}).data,
            status=status.HTTP_200_OK,
        )

    @action(
        detail=True,
        methods=['post'],
        url_path='reject',
        permission_classes=[IsAuthenticated, CanApproveOrRejectOrder],
    )
    def reject(self, request, pk=None):
        order = B2BOrderService.reject_order(order_id=pk, actor=request.user)
        return Response(
            B2BOrderReadSerializer(order, context={'request': request}).data,
            status=status.HTTP_200_OK,
        )

    @action(
        detail=True,
        methods=['get'],
        url_path='movements',
    )
    def movements(self, request, pk=None):
        order = self.get_object()
        movements = StockMovement.objects.filter(
            reference_type='B2BOrder',
            reference_id=order.pk,
        ).select_related('lot').order_by('-created_at')
        ser = StockMovementMinimalSerializer(movements, many=True)
        return Response(ser.data)
