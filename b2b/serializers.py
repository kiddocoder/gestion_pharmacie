"""
B2B — Serializers

Read and write serializers for B2BOrder and B2BOrderItem.
Explicit field lists; no __all__.

@file b2b/serializers.py
"""

from decimal import Decimal

from rest_framework import serializers

from medicines.models import NationalLot

from .models import B2BOrder, B2BOrderItem, PharmacyCredit


class B2BOrderItemReadSerializer(serializers.ModelSerializer):
    lot_display = serializers.CharField(source='lot.__str__', read_only=True)
    medicine_inn = serializers.CharField(source='lot.medicine.inn', read_only=True)
    line_total = serializers.SerializerMethodField()

    class Meta:
        model = B2BOrderItem
        fields = [
            'id', 'order', 'lot', 'lot_display', 'medicine_inn',
            'quantity_ordered', 'quantity_delivered', 'unit_price', 'line_total',
            'created_at', 'updated_at',
        ]
        read_only_fields = fields

    def get_line_total(self, obj):
        return obj.unit_price * obj.quantity_ordered


class B2BOrderItemWriteSerializer(serializers.Serializer):
    lot_id = serializers.UUIDField()
    quantity_ordered = serializers.IntegerField(min_value=1)
    unit_price = serializers.DecimalField(max_digits=15, decimal_places=2, required=False)

    def validate_lot_id(self, value):
        try:
            lot = NationalLot.objects.get(pk=value, is_deleted=False)
        except NationalLot.DoesNotExist:
            raise serializers.ValidationError('Lot not found.')
        if not lot.is_usable:
            raise serializers.ValidationError('Lot is not usable for stock.')
        return value


class B2BOrderReadSerializer(serializers.ModelSerializer):
    seller_name = serializers.CharField(source='seller.name', read_only=True)
    buyer_name = serializers.CharField(source='buyer.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    payment_status_display = serializers.CharField(source='get_payment_status_display', read_only=True)
    items = B2BOrderItemReadSerializer(many=True, read_only=True)

    class Meta:
        model = B2BOrder
        fields = [
            'id', 'seller', 'seller_name', 'buyer', 'buyer_name',
            'status', 'status_display', 'total_amount', 'credit_used',
            'payment_status', 'payment_status_display', 'price_override_approved',
            'items', 'created_at', 'updated_at',
        ]
        read_only_fields = fields


class B2BOrderWriteSerializer(serializers.Serializer):
    seller_id = serializers.UUIDField()
    buyer_id = serializers.UUIDField()
    items = B2BOrderItemWriteSerializer(many=True)
    price_override_approved = serializers.BooleanField(default=False)

    def validate_items(self, value):
        if not value:
            raise serializers.ValidationError('At least one item is required.')
        return value


class B2BOrderUpdateSerializer(serializers.Serializer):
    """For PATCH/PUT on DRAFT orders: update items only."""
    items = B2BOrderItemWriteSerializer(many=True)
    price_override_approved = serializers.BooleanField(required=False)


class B2BOrderApproveSerializer(serializers.Serializer):
    credit_used = serializers.DecimalField(
        max_digits=15, decimal_places=2, required=False, allow_null=True,
    )


class StockMovementMinimalSerializer(serializers.Serializer):
    """Minimal stock movement fields for order movements list."""

    id = serializers.UUIDField(read_only=True)
    movement_type = serializers.CharField(read_only=True)
    quantity = serializers.IntegerField(read_only=True)
    lot_id = serializers.UUIDField(read_only=True)
    entity_type = serializers.CharField(read_only=True)
    entity_id = serializers.UUIDField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)

    def to_representation(self, instance):
        return {
            'id': instance.pk,
            'movement_type': instance.movement_type,
            'quantity': instance.quantity,
            'lot_id': instance.lot_id,
            'entity_type': instance.entity_type,
            'entity_id': instance.entity_id,
            'created_at': instance.created_at,
        }
