"""
PharmaTrack-BI — Test Factories

Factory Boy factories for generating test data. Used across all test
modules.

@file tests/factories.py
"""

import uuid
from datetime import timedelta
from decimal import Decimal

import factory
from django.utils import timezone

from core.models import AuditLog
from geography.models import AdministrativeLevel
from medicines.models import NationalLot, NationalMedicine
from users.models import DeviceToken, OTPCode, Role, User, UserRole


# ---------------------------------------------------------------------------
# Geography
# ---------------------------------------------------------------------------

class ProvinceFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = AdministrativeLevel

    name = factory.Sequence(lambda n: f'Province-{n}')
    code = factory.Sequence(lambda n: f'PRV-{n:02d}')
    level_type = AdministrativeLevel.LevelType.PROVINCE
    parent = None


class CommuneFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = AdministrativeLevel

    name = factory.Sequence(lambda n: f'Commune-{n}')
    code = factory.Sequence(lambda n: f'COM-{n:03d}')
    level_type = AdministrativeLevel.LevelType.COMMUNE
    parent = factory.SubFactory(ProvinceFactory)


class ZoneFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = AdministrativeLevel

    name = factory.Sequence(lambda n: f'Zone-{n}')
    code = factory.Sequence(lambda n: f'ZON-{n:03d}')
    level_type = AdministrativeLevel.LevelType.ZONE
    parent = factory.SubFactory(CommuneFactory)


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User
        skip_postgeneration_save = True

    phone = factory.Sequence(lambda n: f'+2576{n:07d}')
    email = factory.LazyAttribute(lambda o: f'user-{o.phone[-7:]}@test.bi')
    first_name = factory.Faker('first_name')
    last_name = factory.Faker('last_name')
    cin = factory.Sequence(lambda n: f'CIN-{n:08d}')
    status = User.StatusChoices.ACTIVE
    is_active = True

    @factory.post_generation
    def password(self, create, extracted, **kwargs):
        password = extracted or 'TestPass2026!'
        self.set_password(password)
        if create:
            self.save(update_fields=['password'])


class SuperuserFactory(UserFactory):
    is_staff = True
    is_superuser = True


class RoleFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Role

    name = factory.Sequence(lambda n: f'ROLE_{n}')
    scope = Role.ScopeChoices.NATIONAL
    description = factory.Faker('sentence')
    is_system = False


class UserRoleFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = UserRole

    user = factory.SubFactory(UserFactory)
    role = factory.SubFactory(RoleFactory)
    is_active = True


# ---------------------------------------------------------------------------
# Medicines
# ---------------------------------------------------------------------------

class NationalMedicineFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = NationalMedicine

    atc_code = factory.Sequence(lambda n: f'N{n:02d}BE{n:02d}')
    inn = factory.Sequence(lambda n: f'Medicine-INN-{n}')
    brand_name = factory.Sequence(lambda n: f'Brand-{n}')
    dosage_form = NationalMedicine.DosageFormChoices.TABLET
    strength = '500mg'
    packaging = 'Box of 20 tablets'
    manufacturer = factory.Faker('company')
    country_of_origin = 'India'
    authorized_price = factory.LazyFunction(lambda: Decimal('5000.00'))
    is_controlled = False
    status = NationalMedicine.StatusChoices.AUTHORIZED


class NationalLotFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = NationalLot

    medicine = factory.SubFactory(NationalMedicineFactory)
    batch_number = factory.Sequence(lambda n: f'LOT-{n:06d}')
    manufacturing_date = factory.LazyFunction(lambda: (timezone.now() - timedelta(days=180)).date())
    expiry_date = factory.LazyFunction(lambda: (timezone.now() + timedelta(days=365)).date())
    quantity_imported = 10000
    import_reference = factory.Sequence(lambda n: f'IMP-{n:04d}')
    supplier = factory.Faker('company')
    status = NationalLot.StatusChoices.ACTIVE


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------

class AuditLogFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = AuditLog

    actor = factory.SubFactory(UserFactory)
    action = AuditLog.ActionChoices.CREATE
    model_name = 'User'
    object_id = factory.LazyFunction(lambda: str(uuid.uuid4()))
