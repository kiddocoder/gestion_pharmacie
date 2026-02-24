"""
PharmaTrack-BI — Test Factories

Factory Boy factories for generating test data. Used across all test
modules.

@file tests/factories.py
"""

import uuid

import factory
from django.utils import timezone

from core.models import AuditLog
from geography.models import AdministrativeLevel
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
# Audit
# ---------------------------------------------------------------------------

class AuditLogFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = AuditLog

    actor = factory.SubFactory(UserFactory)
    action = AuditLog.ActionChoices.CREATE
    model_name = 'User'
    object_id = factory.LazyFunction(lambda: str(uuid.uuid4()))
