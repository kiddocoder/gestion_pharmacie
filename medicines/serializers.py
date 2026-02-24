"""
Medicines — Serializers

Read and write serializers for NationalMedicine and NationalLot.

@file medicines/serializers.py
"""

import re

from rest_framework import serializers

from .models import ATC_CODE_REGEX, NationalLot, NationalMedicine


# ---------------------------------------------------------------------------
# NationalMedicine
# ---------------------------------------------------------------------------

class NationalMedicineReadSerializer(serializers.ModelSerializer):
    dosage_form_display = serializers.CharField(
        source='get_dosage_form_display', read_only=True,
    )
    status_display = serializers.CharField(
        source='get_status_display', read_only=True,
    )
    active_lots_count = serializers.SerializerMethodField()

    class Meta:
        model = NationalMedicine
        fields = [
            'id', 'atc_code', 'inn', 'brand_name',
            'dosage_form', 'dosage_form_display',
            'strength', 'packaging', 'manufacturer', 'country_of_origin',
            'authorized_price', 'is_controlled',
            'status', 'status_display', 'description',
            'active_lots_count',
            'created_at', 'updated_at',
        ]
        read_only_fields = fields

    def get_active_lots_count(self, obj):
        return obj.lots.filter(status='ACTIVE', is_deleted=False).count()


class NationalMedicineWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = NationalMedicine
        fields = [
            'atc_code', 'inn', 'brand_name',
            'dosage_form', 'strength', 'packaging',
            'manufacturer', 'country_of_origin',
            'authorized_price', 'is_controlled',
            'description',
        ]

    def validate_atc_code(self, value):
        value = value.upper().strip()
        if not ATC_CODE_REGEX.match(value):
            raise serializers.ValidationError(
                'Invalid ATC code format. Expected pattern: A00AA00 (e.g. N02BE01).',
            )
        return value

    def validate_authorized_price(self, value):
        if value <= 0:
            raise serializers.ValidationError('Authorized price must be positive.')
        return value


class MedicineBlockSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, default='')


# ---------------------------------------------------------------------------
# NationalLot
# ---------------------------------------------------------------------------

class NationalLotReadSerializer(serializers.ModelSerializer):
    medicine_name = serializers.CharField(source='medicine.__str__', read_only=True)
    medicine_inn = serializers.CharField(source='medicine.inn', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    days_to_expiry = serializers.IntegerField(read_only=True)
    is_usable = serializers.BooleanField(read_only=True)

    class Meta:
        model = NationalLot
        fields = [
            'id', 'medicine', 'medicine_name', 'medicine_inn',
            'batch_number', 'manufacturing_date', 'expiry_date',
            'quantity_imported', 'import_reference', 'supplier',
            'status', 'status_display',
            'recall_reason', 'days_to_expiry', 'is_usable',
            'created_at', 'updated_at',
        ]
        read_only_fields = fields


class NationalLotWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = NationalLot
        fields = [
            'medicine', 'batch_number',
            'manufacturing_date', 'expiry_date',
            'quantity_imported', 'import_reference', 'supplier',
        ]

    def validate(self, attrs):
        mfg = attrs.get('manufacturing_date')
        exp = attrs.get('expiry_date')
        if mfg and exp and exp <= mfg:
            raise serializers.ValidationError({
                'expiry_date': 'Expiry date must be after manufacturing date.',
            })

        medicine = attrs.get('medicine')
        if medicine and medicine.status == NationalMedicine.StatusChoices.BLOCKED:
            raise serializers.ValidationError({
                'medicine': 'Cannot create lot for a BLOCKED medicine.',
            })

        return attrs


class NationalLotNestedWriteSerializer(serializers.ModelSerializer):
    """Write serializer for creating lots under /medicines/{id}/lots/."""

    class Meta:
        model = NationalLot
        fields = [
            'batch_number',
            'manufacturing_date', 'expiry_date',
            'quantity_imported', 'import_reference', 'supplier',
        ]

    def validate(self, attrs):
        mfg = attrs.get('manufacturing_date')
        exp = attrs.get('expiry_date')
        if mfg and exp and exp <= mfg:
            raise serializers.ValidationError({
                'expiry_date': 'Expiry date must be after manufacturing date.',
            })
        return attrs


class LotRecallSerializer(serializers.Serializer):
    reason = serializers.CharField(min_length=5)
