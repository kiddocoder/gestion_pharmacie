"""
Tests — NationalMedicine & NationalLot model constraints and properties.

@file medicines/tests/test_models.py
"""

import pytest
from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.utils import timezone

from medicines.models import NationalLot, NationalMedicine
from tests.factories import NationalLotFactory, NationalMedicineFactory


pytestmark = pytest.mark.django_db


class TestNationalMedicine:

    def test_create_valid_medicine(self):
        med = NationalMedicineFactory()
        assert med.pk is not None
        assert med.status == 'AUTHORIZED'
        assert med.is_deleted is False

    def test_str(self):
        med = NationalMedicineFactory(brand_name='Doliprane', strength='1000mg', dosage_form='TABLET')
        assert 'Doliprane' in str(med)
        assert '1000mg' in str(med)

    def test_str_falls_back_to_inn(self):
        med = NationalMedicineFactory(brand_name='', inn='Paracetamol', strength='500mg')
        assert 'Paracetamol' in str(med)

    def test_atc_code_validation_rejects_bad_format(self):
        med = NationalMedicineFactory.build(atc_code='INVALID')
        with pytest.raises(ValidationError) as exc_info:
            med.full_clean()
        assert 'atc_code' in exc_info.value.message_dict

    def test_atc_code_validation_accepts_good_format(self):
        med = NationalMedicineFactory.build(atc_code='N02BE01')
        med.full_clean()

    def test_unique_active_medicine_constraint(self):
        med1 = NationalMedicineFactory(
            atc_code='N02BE01', dosage_form='TABLET', strength='500mg',
            packaging='Box of 20', manufacturer='Acme',
        )
        with pytest.raises(IntegrityError):
            NationalMedicineFactory(
                atc_code='N02BE01', dosage_form='TABLET', strength='500mg',
                packaging='Box of 20', manufacturer='Acme',
            )

    def test_soft_deleted_medicine_allows_duplicate(self):
        med1 = NationalMedicineFactory(
            atc_code='A01AB03', dosage_form='TABLET', strength='250mg',
            packaging='Box of 10', manufacturer='LabX',
        )
        med1.is_deleted = True
        med1.save()

        med2 = NationalMedicineFactory(
            atc_code='A01AB03', dosage_form='TABLET', strength='250mg',
            packaging='Box of 10', manufacturer='LabX',
        )
        assert med2.pk is not None


class TestNationalLot:

    def test_create_valid_lot(self):
        lot = NationalLotFactory()
        assert lot.pk is not None
        assert lot.status == 'ACTIVE'

    def test_str(self):
        lot = NationalLotFactory(batch_number='BATCH-001')
        assert 'BATCH-001' in str(lot)

    def test_days_to_expiry_positive(self):
        future = timezone.now().date() + timedelta(days=60)
        lot = NationalLotFactory(expiry_date=future)
        assert lot.days_to_expiry == 60

    def test_days_to_expiry_negative(self):
        past = timezone.now().date() - timedelta(days=10)
        lot = NationalLotFactory.build(expiry_date=past, manufacturing_date=past - timedelta(days=365))
        assert lot.days_to_expiry == -10

    def test_is_expired(self):
        past = timezone.now().date() - timedelta(days=1)
        lot = NationalLotFactory.build(expiry_date=past, manufacturing_date=past - timedelta(days=365))
        assert lot.is_expired is True

    def test_is_usable_active_not_expired(self):
        lot = NationalLotFactory()
        assert lot.is_usable is True

    def test_is_usable_false_when_blocked(self):
        lot = NationalLotFactory(status='BLOCKED')
        assert lot.is_usable is False

    def test_expiry_after_manufacturing_constraint(self):
        """DB check constraint: expiry > manufacturing."""
        today = timezone.now().date()
        with pytest.raises(IntegrityError):
            NationalLotFactory(
                manufacturing_date=today,
                expiry_date=today - timedelta(days=1),
            )

    def test_positive_quantity_constraint(self):
        with pytest.raises(IntegrityError):
            NationalLotFactory(quantity_imported=0)

    def test_unique_batch_per_medicine(self):
        med = NationalMedicineFactory()
        NationalLotFactory(medicine=med, batch_number='DUP-001')
        with pytest.raises(IntegrityError):
            NationalLotFactory(medicine=med, batch_number='DUP-001')

    def test_clean_rejects_bad_dates(self):
        today = timezone.now().date()
        lot = NationalLotFactory.build(
            manufacturing_date=today,
            expiry_date=today - timedelta(days=30),
        )
        with pytest.raises(ValidationError) as exc_info:
            lot.full_clean()
        assert 'expiry_date' in exc_info.value.message_dict
