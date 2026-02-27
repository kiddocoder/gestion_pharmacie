"""
Pharmacies — Serializers

Read and write serializers for Pharmacy and PharmacyDocument.
Explicit field lists; no __all__.

@file pharmacies/serializers.py
"""

from rest_framework import serializers

from geography.serializers import AdministrativeLevelMinimalSerializer

from .models import Pharmacy, PharmacyDocument

__all__ = [
    'PharmacyReadSerializer',
    'PharmacyWriteSerializer',
    'PharmacyApproveSerializer',
    'PharmacySuspendSerializer',
    'PharmacyDocumentReadSerializer',
    'PharmacyDocumentWriteSerializer',
]


# ---------------------------------------------------------------------------
# Pharmacy
# ---------------------------------------------------------------------------

class PharmacyReadSerializer(serializers.ModelSerializer):
    pharmacy_type_display = serializers.CharField(
        source='get_pharmacy_type_display', read_only=True,
    )
    status_display = serializers.CharField(
        source='get_status_display', read_only=True,
    )
    administrative_level_detail = AdministrativeLevelMinimalSerializer(
        source='administrative_level', read_only=True,
    )
    qr_code_url = serializers.SerializerMethodField()
    documents_count = serializers.SerializerMethodField()

    class Meta:
        model = Pharmacy
        fields = [
            'id', 'name', 'pharmacy_type', 'pharmacy_type_display',
            'national_code', 'latitude', 'longitude',
            'administrative_level', 'administrative_level_detail',
            'status', 'status_display',
            'qr_code', 'qr_code_url',
            'address', 'phone', 'metadata',
            'documents_count',
            'created_at', 'updated_at',
        ]
        read_only_fields = fields

    def get_qr_code_url(self, obj):
        if obj.qr_code:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.qr_code.url)
            return obj.qr_code.url
        return None

    def get_documents_count(self, obj):
        return obj.documents.filter(is_deleted=False).count()


class PharmacyWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Pharmacy
        fields = [
            'name', 'pharmacy_type', 'latitude', 'longitude',
            'administrative_level', 'address', 'phone', 'metadata',
        ]

    def validate_administrative_level(self, value):
        if value and value.level_type != 'COMMUNE':
            raise serializers.ValidationError(
                'Administrative level must be a commune.',
            )
        return value


class PharmacyApproveSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, default='', allow_blank=True)


class PharmacySuspendSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, default='', allow_blank=True)


# ---------------------------------------------------------------------------
# PharmacyDocument
# ---------------------------------------------------------------------------

class PharmacyDocumentReadSerializer(serializers.ModelSerializer):
    document_type_display = serializers.CharField(
        source='get_document_type_display', read_only=True,
    )
    status_display = serializers.CharField(
        source='get_status_display', read_only=True,
    )
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = PharmacyDocument
        fields = [
            'id', 'pharmacy', 'document_type', 'document_type_display',
            'file', 'file_url', 'status', 'status_display',
            'expiry_date', 'rejection_reason',
            'created_at', 'updated_at',
        ]
        read_only_fields = fields

    def get_file_url(self, obj):
        if obj.file:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.file.url)
            return obj.file.url
        return None


class PharmacyDocumentWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = PharmacyDocument
        fields = [
            'document_type', 'file', 'expiry_date',
        ]

    def validate_document_type(self, value):
        if value not in dict(PharmacyDocument.DocumentTypeChoices.choices):
            raise serializers.ValidationError('Invalid document type.')
        return value
