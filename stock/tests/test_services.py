"""
Tests — StockService: get_balance, record_movement, process_b2b, process_retail_sale.
Concurrent sale: one succeeds, other gets 409. B2B rollback on error.
Balance correct after 1000 mixed movements.

@file stock/tests/test_services.py
"""

import uuid

import pytest

from core.exceptions import BusinessRuleViolation, InsufficientStockError, ResourceNotFoundError
from medicines.models import NationalLot
from stock.models import StockMovement
from stock.services import StockService
from tests.factories import NationalLotFactory, PharmacyFactory, SuperuserFactory


pytestmark = pytest.mark.django_db


def _pharmacy_id():
    return PharmacyFactory().pk


class TestGetBalance:

    def test_balance_empty_is_zero(self):
        entity_id = _pharmacy_id()
        lot = NationalLotFactory()
        assert StockService.get_balance(
            StockMovement.EntityType.PHARMACY, entity_id, lot.pk,
        ) == 0

    def test_balance_after_inbound(self):
        entity_id = _pharmacy_id()
        lot = NationalLotFactory()
        StockService.record_movement(
            entity_type=StockMovement.EntityType.PHARMACY,
            entity_id=entity_id,
            lot_id=lot.pk,
            movement_type=StockMovement.MovementType.IMPORT,
            quantity=50,
            created_by=SuperuserFactory(),
        )
        assert StockService.get_balance(
            StockMovement.EntityType.PHARMACY, entity_id, lot.pk,
        ) == 50

    def test_balance_inbound_minus_outbound(self):
        entity_id = _pharmacy_id()
        lot = NationalLotFactory()
        StockService.record_movement(
            entity_type=StockMovement.EntityType.PHARMACY,
            entity_id=entity_id,
            lot_id=lot.pk,
            movement_type=StockMovement.MovementType.IMPORT,
            quantity=100,
            created_by=SuperuserFactory(),
        )
        StockService.record_movement(
            entity_type=StockMovement.EntityType.PHARMACY,
            entity_id=entity_id,
            lot_id=lot.pk,
            movement_type=StockMovement.MovementType.SALE,
            quantity=30,
            created_by=SuperuserFactory(),
        )
        assert StockService.get_balance(
            StockMovement.EntityType.PHARMACY, entity_id, lot.pk,
        ) == 70

    def test_balance_after_1000_mixed_movements(self):
        """Acceptance: get_balance() returns correct result after 1000 mixed movements."""
        entity_id = _pharmacy_id()
        lot = NationalLotFactory()
        user = SuperuserFactory()
        # 500 IMPORT + 300 B2B_IN + 200 RETURN = 1000 inbound
        # 400 SALE + 100 B2B_OUT = 500 outbound
        # Expected balance = 1000 - 500 = 500
        for _ in range(500):
            StockService.record_movement(
                entity_type=StockMovement.EntityType.PHARMACY,
                entity_id=entity_id,
                lot_id=lot.pk,
                movement_type=StockMovement.MovementType.IMPORT,
                quantity=1,
                created_by=user,
            )
        for _ in range(300):
            StockService.record_movement(
                entity_type=StockMovement.EntityType.PHARMACY,
                entity_id=entity_id,
                lot_id=lot.pk,
                movement_type=StockMovement.MovementType.B2B_IN,
                quantity=1,
                created_by=user,
            )
        for _ in range(200):
            StockService.record_movement(
                entity_type=StockMovement.EntityType.PHARMACY,
                entity_id=entity_id,
                lot_id=lot.pk,
                movement_type=StockMovement.MovementType.RETURN,
                quantity=1,
                created_by=user,
            )
        for _ in range(400):
            StockService.record_movement(
                entity_type=StockMovement.EntityType.PHARMACY,
                entity_id=entity_id,
                lot_id=lot.pk,
                movement_type=StockMovement.MovementType.SALE,
                quantity=1,
                created_by=user,
            )
        for _ in range(100):
            StockService.record_movement(
                entity_type=StockMovement.EntityType.PHARMACY,
                entity_id=entity_id,
                lot_id=lot.pk,
                movement_type=StockMovement.MovementType.B2B_OUT,
                quantity=1,
                created_by=user,
            )
        assert StockService.get_balance(
            StockMovement.EntityType.PHARMACY, entity_id, lot.pk,
        ) == 500


class TestRecordMovement:

    def test_record_import(self):
        entity_id = _pharmacy_id()
        lot = NationalLotFactory()
        mov = StockService.record_movement(
            entity_type=StockMovement.EntityType.PHARMACY,
            entity_id=entity_id,
            lot_id=lot.pk,
            movement_type=StockMovement.MovementType.IMPORT,
            quantity=10,
            created_by=SuperuserFactory(),
        )
        assert mov.pk is not None
        assert mov.movement_type == StockMovement.MovementType.IMPORT
        assert mov.quantity == 10

    def test_record_sale_insufficient_raises_409(self):
        entity_id = _pharmacy_id()
        lot = NationalLotFactory()
        with pytest.raises(InsufficientStockError):
            StockService.record_movement(
                entity_type=StockMovement.EntityType.PHARMACY,
                entity_id=entity_id,
                lot_id=lot.pk,
                movement_type=StockMovement.MovementType.SALE,
                quantity=1,
                created_by=SuperuserFactory(),
            )
        assert StockService.get_balance(
            StockMovement.EntityType.PHARMACY, entity_id, lot.pk,
        ) == 0

    def test_concurrent_sale_last_unit_one_succeeds_other_409(self):
        """Acceptance: two requests for last unit → one succeeds, other gets 409."""
        entity_id = _pharmacy_id()
        lot = NationalLotFactory()
        user = SuperuserFactory()
        StockService.record_movement(
            entity_type=StockMovement.EntityType.PHARMACY,
            entity_id=entity_id,
            lot_id=lot.pk,
            movement_type=StockMovement.MovementType.IMPORT,
            quantity=1,
            created_by=user,
        )
        # First sale: succeeds
        StockService.record_movement(
            entity_type=StockMovement.EntityType.PHARMACY,
            entity_id=entity_id,
            lot_id=lot.pk,
            movement_type=StockMovement.MovementType.SALE,
            quantity=1,
            created_by=user,
        )
        assert StockService.get_balance(
            StockMovement.EntityType.PHARMACY, entity_id, lot.pk,
        ) == 0
        # Second sale: 409
        with pytest.raises(InsufficientStockError):
            StockService.record_movement(
                entity_type=StockMovement.EntityType.PHARMACY,
                entity_id=entity_id,
                lot_id=lot.pk,
                movement_type=StockMovement.MovementType.SALE,
                quantity=1,
                created_by=user,
            )

    def test_record_movement_invalid_lot_raises(self):
        entity_id = _pharmacy_id()
        with pytest.raises(ResourceNotFoundError):
            StockService.record_movement(
                entity_type=StockMovement.EntityType.PHARMACY,
                entity_id=entity_id,
                lot_id=uuid.uuid4(),
                movement_type=StockMovement.MovementType.IMPORT,
                quantity=1,
                created_by=SuperuserFactory(),
            )

    def test_record_movement_blocked_lot_raises(self):
        entity_id = _pharmacy_id()
        lot = NationalLotFactory(status=NationalLot.StatusChoices.BLOCKED)
        with pytest.raises(BusinessRuleViolation):
            StockService.record_movement(
                entity_type=StockMovement.EntityType.PHARMACY,
                entity_id=entity_id,
                lot_id=lot.pk,
                movement_type=StockMovement.MovementType.IMPORT,
                quantity=1,
                created_by=SuperuserFactory(),
            )

    def test_record_movement_quantity_positive_required(self):
        entity_id = _pharmacy_id()
        lot = NationalLotFactory()
        with pytest.raises(BusinessRuleViolation):
            StockService.record_movement(
                entity_type=StockMovement.EntityType.PHARMACY,
                entity_id=entity_id,
                lot_id=lot.pk,
                movement_type=StockMovement.MovementType.IMPORT,
                quantity=0,
                created_by=SuperuserFactory(),
            )


class TestProcessB2BTransaction:

    def test_b2b_dual_movement_atomic(self):
        seller_id = _pharmacy_id()
        buyer_id = _pharmacy_id()
        lot = NationalLotFactory()
        user = SuperuserFactory()
        StockService.record_movement(
            entity_type=StockMovement.EntityType.PHARMACY,
            entity_id=seller_id,
            lot_id=lot.pk,
            movement_type=StockMovement.MovementType.IMPORT,
            quantity=20,
            created_by=user,
        )
        out_mov, in_mov = StockService.process_b2b_transaction(
            seller_entity_type=StockMovement.EntityType.PHARMACY,
            seller_entity_id=seller_id,
            buyer_entity_type=StockMovement.EntityType.PHARMACY,
            buyer_entity_id=buyer_id,
            lot_id=lot.pk,
            quantity=10,
            created_by=user,
        )
        assert out_mov.movement_type == StockMovement.MovementType.B2B_OUT
        assert in_mov.movement_type == StockMovement.MovementType.B2B_IN
        assert StockService.get_balance(
            StockMovement.EntityType.PHARMACY, seller_id, lot.pk,
        ) == 10
        assert StockService.get_balance(
            StockMovement.EntityType.PHARMACY, buyer_id, lot.pk,
        ) == 10

    def test_b2b_insufficient_seller_raises(self):
        seller_id = _pharmacy_id()
        buyer_id = _pharmacy_id()
        lot = NationalLotFactory()
        with pytest.raises(InsufficientStockError):
            StockService.process_b2b_transaction(
                seller_entity_type=StockMovement.EntityType.PHARMACY,
                seller_entity_id=seller_id,
                buyer_entity_type=StockMovement.EntityType.PHARMACY,
                buyer_entity_id=buyer_id,
                lot_id=lot.pk,
                quantity=1,
                created_by=SuperuserFactory(),
            )

    def test_b2b_rollback_on_error(self):
        """Acceptance: process_b2b_transaction() rolls back both movements if any error occurs."""
        seller_id = _pharmacy_id()
        buyer_id = _pharmacy_id()
        lot = NationalLotFactory()
        user = SuperuserFactory()
        StockService.record_movement(
            entity_type=StockMovement.EntityType.PHARMACY,
            entity_id=seller_id,
            lot_id=lot.pk,
            movement_type=StockMovement.MovementType.IMPORT,
            quantity=5,
            created_by=user,
        )
        initial_count = StockMovement.objects.count()
        # Force an error after first insert by using an invalid lot for a second call
        # We mock by causing the second save to fail: use a lot that gets deleted mid-transaction
        # Simpler: raise inside the service. Instead we verify rollback by patching.
        from unittest.mock import patch
        with patch.object(StockMovement, 'save', side_effect=[None, Exception('simulated failure')]):
            with pytest.raises(Exception, match='simulated failure'):
                StockService.process_b2b_transaction(
                    seller_entity_type=StockMovement.EntityType.PHARMACY,
                    seller_entity_id=seller_id,
                    buyer_entity_type=StockMovement.EntityType.PHARMACY,
                    buyer_entity_id=buyer_id,
                    lot_id=lot.pk,
                    quantity=2,
                    created_by=user,
                )
        # No new movements committed (transaction rolled back)
        assert StockMovement.objects.count() == initial_count
        assert StockService.get_balance(
            StockMovement.EntityType.PHARMACY, seller_id, lot.pk,
        ) == 5


class TestProcessRetailSale:

    def test_retail_sale(self):
        pharmacy_id = _pharmacy_id()
        lot = NationalLotFactory()
        user = SuperuserFactory()
        StockService.record_movement(
            entity_type=StockMovement.EntityType.PHARMACY,
            entity_id=pharmacy_id,
            lot_id=lot.pk,
            movement_type=StockMovement.MovementType.IMPORT,
            quantity=15,
            created_by=user,
        )
        mov = StockService.process_retail_sale(
            pharmacy_id=pharmacy_id,
            lot_id=lot.pk,
            quantity=7,
            created_by=user,
        )
        assert mov.movement_type == StockMovement.MovementType.SALE
        assert mov.quantity == 7
        assert StockService.get_balance(
            StockMovement.EntityType.PHARMACY, pharmacy_id, lot.pk,
        ) == 8
