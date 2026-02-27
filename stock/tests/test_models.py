"""
Tests — StockMovement model (insert-only, no delete).

@file stock/tests/test_models.py
"""

import uuid

import pytest

from stock.models import StockMovement
from tests.factories import NationalLotFactory, StockMovementFactory, UserFactory


pytestmark = pytest.mark.django_db


class TestStockMovementInsertOnly:

    def test_create_movement(self):
        lot = NationalLotFactory()
        movement = StockMovement(
            entity_type=StockMovement.EntityType.PHARMACY,
            entity_id=uuid.uuid4(),
            lot=lot,
            movement_type=StockMovement.MovementType.IMPORT,
            quantity=100,
            created_by=UserFactory(),
        )
        movement.save()
        assert movement.pk is not None
        assert movement.quantity == 100

    def test_update_raises(self):
        movement = StockMovementFactory()
        movement.quantity = 999
        with pytest.raises(NotImplementedError) as exc_info:
            movement.save()
        assert 'insert-only' in str(exc_info.value).lower() or 'update' in str(exc_info.value).lower()

    def test_delete_raises(self):
        movement = StockMovementFactory()
        with pytest.raises(NotImplementedError) as exc_info:
            movement.delete()
        assert 'delete' in str(exc_info.value).lower()
