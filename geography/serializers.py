"""
Geography — Serializers

Read and write serializers for AdministrativeLevel.

@file geography/serializers.py
"""

from rest_framework import serializers

from .models import AdministrativeLevel


class AdministrativeLevelMinimalSerializer(serializers.ModelSerializer):
    """Minimal fields for embedding in other serializers (e.g. pharmacy commune)."""

    class Meta:
        model = AdministrativeLevel
        fields = ['id', 'name', 'code', 'level_type']


class AdministrativeLevelReadSerializer(serializers.ModelSerializer):
    """Flat read representation with parent name."""

    parent_name = serializers.CharField(source='parent.name', read_only=True, default=None)
    full_path = serializers.CharField(read_only=True)
    children_count = serializers.SerializerMethodField()

    class Meta:
        model = AdministrativeLevel
        fields = [
            'id', 'name', 'code', 'level_type',
            'parent', 'parent_name', 'full_path',
            'children_count', 'created_at',
        ]
        read_only_fields = fields

    def get_children_count(self, obj):
        return obj.children.count()


class AdministrativeLevelWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdministrativeLevel
        fields = ['name', 'code', 'level_type', 'parent']

    def validate(self, attrs):
        level_type = attrs.get('level_type')
        parent = attrs.get('parent')

        if level_type == 'PROVINCE' and parent is not None:
            raise serializers.ValidationError(
                {'parent': 'Province must not have a parent.'},
            )

        if level_type != 'PROVINCE' and parent is None:
            raise serializers.ValidationError(
                {'parent': f'{level_type} requires a parent.'},
            )

        expected_parent_type = AdministrativeLevel.PARENT_LEVEL_MAP.get(level_type)
        if parent and expected_parent_type and parent.level_type != expected_parent_type:
            raise serializers.ValidationError(
                {'parent': f'{level_type} parent must be a {expected_parent_type}, got {parent.level_type}.'},
            )

        return attrs


class AdministrativeLevelTreeSerializer(serializers.ModelSerializer):
    """Recursive tree representation for hierarchy display."""

    children = serializers.SerializerMethodField()

    class Meta:
        model = AdministrativeLevel
        fields = ['id', 'name', 'code', 'level_type', 'children']

    def get_children(self, obj):
        children = obj.children.all().order_by('name')
        depth = self.context.get('depth', 2)
        if depth <= 0:
            return []
        return AdministrativeLevelTreeSerializer(
            children, many=True,
            context={'depth': depth - 1},
        ).data
