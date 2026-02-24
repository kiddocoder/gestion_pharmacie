"""
Users — Management Command: seed_roles

Populates the Role table with the system-default roles required
by PharmaTrack-BI.

Usage::

    python manage.py seed_roles

Idempotent: safe to re-run (uses get_or_create).

@file users/management/commands/seed_roles.py
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from users.models import Role


SYSTEM_ROLES = [
    # National scope
    {'name': 'NATIONAL_ADMIN', 'scope': 'NATIONAL', 'description': 'Full national platform administrator'},
    {'name': 'NATIONAL_ANALYST', 'scope': 'NATIONAL', 'description': 'Read-only analytics access'},
    {'name': 'NATIONAL_PHARMACIST', 'scope': 'NATIONAL', 'description': 'National pharmacy regulatory officer'},
    # Public scope
    {'name': 'PROVINCIAL_ADMIN', 'scope': 'PUBLIC', 'description': 'Provincial health administrator'},
    {'name': 'PUBLIC_MANAGER', 'scope': 'PUBLIC', 'description': 'Public health facility manager'},
    {'name': 'INSPECTOR', 'scope': 'PUBLIC', 'description': 'Field pharmacy inspector'},
    # Private scope
    {'name': 'PHARMACY_OWNER', 'scope': 'PRIVATE', 'description': 'Pharmacy owner / licensee'},
    {'name': 'PHARMACY_MANAGER', 'scope': 'PRIVATE', 'description': 'Day-to-day pharmacy manager'},
    {'name': 'PHARMACY_STAFF', 'scope': 'PRIVATE', 'description': 'Pharmacy counter staff'},
    {'name': 'WHOLESALER_ADMIN', 'scope': 'PRIVATE', 'description': 'Wholesaler administrator'},
]


class Command(BaseCommand):
    help = 'Seed system-default RBAC roles.'

    @transaction.atomic
    def handle(self, *args, **options):
        created_count = 0
        for role_data in SYSTEM_ROLES:
            _, created = Role.objects.get_or_create(
                name=role_data['name'],
                defaults={
                    'scope': role_data['scope'],
                    'description': role_data['description'],
                    'is_system': True,
                },
            )
            if created:
                created_count += 1
                self.stdout.write(f'  Created role: {role_data["name"]}')
            else:
                self.stdout.write(f'  Exists: {role_data["name"]}')

        self.stdout.write(self.style.SUCCESS(
            f'Done. {created_count} new roles created, {len(SYSTEM_ROLES) - created_count} already existed.'
        ))
