"""
Tests — MedicineService & LotService business logic.

@file medicines/tests/test_services.py
"""

import pytest
from datetime import timedelta
from decimal import Decimal

from django.utils import timezone

from core.exceptions import (
    BusinessRuleViolation,
    InvalidStateTransition,
    ResourceNotFoundError,
)
from medicines.models import NationalLot, NationalMedicine
from medicines.services import LotService, MedicineService
from tests.factories import (
    NationalLotFactory,
    NationalMedicineFactory,
    SuperuserFactory,
)


pytestmark = pytest.mark.django_db


class TestMedicineService:

    def test_create_medicine(self):
        med = MedicineService.create_medicine(
            atc_code='N02BE01', inn='Paracetamol', brand_name='Doliprane',
            dosage_form='TABLET', strength='500mg', packaging='Box of 20',
            authorized_price=Decimal('3000.00'),
        )
        assert med.pk is not None
        assert med.status == 'AUTHORIZED'

    def test_update_medicine(self):
        med = NationalMedicineFactory()
        updated = MedicineService.update_medicine(
            medicine_id=med.pk,
            authorized_price=Decimal('9999.00'),
        )
        assert updated.authorized_price == Decimal('9999.00')

    def test_update_nonexistent_raises(self):
        import uuid
        with pytest.raises(ResourceNotFoundError):
            MedicineService.update_medicine(medicine_id=uuid.uuid4(), inn='X')

    def test_block_medicine(self):
        med = NationalMedicineFactory()
        blocked = MedicineService.block_medicine(medicine_id=med.pk, reason='Safety concern')
        assert blocked.status == 'BLOCKED'

    def test_block_cascades_to_lots(self):
        med = NationalMedicineFactory()
        lot1 = NationalLotFactory(medicine=med, status='ACTIVE')
        lot2 = NationalLotFactory(medicine=med, status='EXPIRED')
        MedicineService.block_medicine(medicine_id=med.pk)
        lot1.refresh_from_db()
        lot2.refresh_from_db()
        assert lot1.status == 'BLOCKED'
        assert lot2.status == 'EXPIRED'  # not affected

    def test_block_already_blocked_raises(self):
        med = NationalMedicineFactory(status='BLOCKED')
        with pytest.raises(InvalidStateTransition):
            MedicineService.block_medicine(medicine_id=med.pk)

    def test_unblock_medicine(self):
        med = NationalMedicineFactory(status='BLOCKED')
        unblocked = MedicineService.unblock_medicine(medicine_id=med.pk)
        assert unblocked.status == 'AUTHORIZED'

    def test_unblock_non_blocked_raises(self):
        med = NationalMedicineFactory(status='AUTHORIZED')
        with pytest.raises(InvalidStateTransition):
            MedicineService.unblock_medicine(medicine_id=med.pk)


class TestLotService:

    def test_create_lot(self):
        med = NationalMedicineFactory()
        today = timezone.now().date()
        lot = LotService.create_lot(
            medicine=med, batch_number='B001',
            manufacturing_date=today - timedelta(days=90),
            expiry_date=today + timedelta(days=365),
            quantity_imported=5000,
        )
        assert lot.pk is not None
        assert lot.status == 'ACTIVE'

    def test_create_lot_blocked_medicine_raises(self):
        med = NationalMedicineFactory(status='BLOCKED')
        today = timezone.now().date()
        with pytest.raises(BusinessRuleViolation):
            LotService.create_lot(
                medicine=med, batch_number='B002',
                manufacturing_date=today - timedelta(days=90),
                expiry_date=today + timedelta(days=365),
                quantity_imported=1000,
            )

    def test_update_lot_rejects_immutable_fields(self):
        lot = NationalLotFactory()
        with pytest.raises(BusinessRuleViolation):
            LotService.update_lot(lot_id=lot.pk, batch_number='CHANGED')

    def test_update_lot_allows_mutable_fields(self):
        lot = NationalLotFactory(supplier='Old Supplier')
        updated = LotService.update_lot(lot_id=lot.pk, supplier='New Supplier')
        assert updated.supplier == 'New Supplier'

    def test_recall_active_lot(self):
        lot = NationalLotFactory(status='ACTIVE')
        recalled = LotService.recall_lot(lot_id=lot.pk, reason='Contamination detected')
        assert recalled.status == 'RECALLED'
        assert recalled.recall_reason == 'Contamination detected'

    def test_recall_expired_lot_raises(self):
        lot = NationalLotFactory(status='EXPIRED')
        with pytest.raises(InvalidStateTransition):
            LotService.recall_lot(lot_id=lot.pk, reason='Too late')

    def test_recall_already_recalled_raises(self):
        lot = NationalLotFactory(status='RECALLED')
        with pytest.raises(InvalidStateTransition):
            LotService.recall_lot(lot_id=lot.pk, reason='Again')

    def test_expire_overdue_lots(self):
        past = timezone.now().date() - timedelta(days=5)
        lot_expired = NationalLotFactory(
            expiry_date=past,
            manufacturing_date=past - timedelta(days=365),
            status='ACTIVE',
        )
        lot_valid = NationalLotFactory(status='ACTIVE')

        count = LotService.expire_overdue_lots()
        assert count == 1
        lot_expired.refresh_from_db()
        lot_valid.refresh_from_db()
        assert lot_expired.status == 'EXPIRED'
        assert lot_valid.status == 'ACTIVE'

    def test_get_expiring_soon(self):
        soon = timezone.now().date() + timedelta(days=15)
        far = timezone.now().date() + timedelta(days=200)
        NationalLotFactory(expiry_date=soon, manufacturing_date=soon - timedelta(days=365))
        NationalLotFactory(expiry_date=far, manufacturing_date=far - timedelta(days=365))

        expiring = LotService.get_expiring_soon(days=30)
        assert expiring.count() == 1
