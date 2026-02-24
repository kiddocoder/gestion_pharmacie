"""
Geography — Management Command: seed_geography

Loads all four levels of Burundi's administrative hierarchy from the
official JSON data source.

Usage::

    python manage.py seed_geography

Idempotent: safe to re-run (uses get_or_create).

@file geography/management/commands/seed_geography.py
"""

import json
import logging
import urllib.request
from collections import Counter

from django.core.management.base import BaseCommand
from django.db import transaction

from geography.models import AdministrativeLevel

logger = logging.getLogger('pharmatrack')

JSON_URL = (
    'https://raw.githubusercontent.com/'
    'mosiflow/burundi-new-subdivision-json/main/burundi-map.json'
)


class Command(BaseCommand):
    help = 'Seed the administrative hierarchy of Burundi from official JSON.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--file',
            type=str,
            help='Path to a local JSON file (overrides remote download).',
        )

    def handle(self, *args, **options):
        self.stdout.write('Loading Burundi administrative hierarchy…')

        if options.get('file'):
            with open(options['file'], 'r', encoding='utf-8') as f:
                data = json.load(f)
        else:
            self.stdout.write(f'Downloading from {JSON_URL}')
            with urllib.request.urlopen(JSON_URL) as resp:
                data = json.loads(resp.read().decode('utf-8'))

        counter = Counter()

        with transaction.atomic():
            self._process_data(data, counter)

        self.stdout.write(self.style.SUCCESS(
            f'Done. Provinces: {counter["PROVINCE"]}, Communes: {counter["COMMUNE"]}, '
            f'Zones: {counter["ZONE"]}, Collines: {counter["COLLINE"]}'
        ))

    def _process_data(self, data, counter):
        """
        Expected JSON shape (from mosiflow repo):

        [
          {
            "name": "Bubanza",
            "communes": [
              {
                "name": "Bubanza",
                "zones": [
                  {
                    "name": "Bubanza",
                    "collines": ["Colline1", "Colline2"]
                  }
                ]
              }
            ]
          }
        ]
        """
        if isinstance(data, dict):
            provinces = data.get('provinces', data.get('data', [data]))
        elif isinstance(data, list):
            provinces = data
        else:
            self.stderr.write('Unexpected JSON structure.')
            return

        for p_idx, province_data in enumerate(provinces):
            province_name = province_data.get('name', province_data.get('province', ''))
            if not province_name:
                continue

            province_code = f'PRV-{p_idx + 1:02d}'
            province, _ = AdministrativeLevel.objects.get_or_create(
                code=province_code,
                defaults={
                    'name': province_name.strip(),
                    'level_type': AdministrativeLevel.LevelType.PROVINCE,
                    'parent': None,
                },
            )
            counter['PROVINCE'] += 1
            self.stdout.write(f'  Province: {province_name}')

            communes = province_data.get('communes', province_data.get('districts', []))
            for c_idx, commune_data in enumerate(communes):
                if isinstance(commune_data, str):
                    commune_name = commune_data
                    zones_data = []
                else:
                    commune_name = commune_data.get('name', commune_data.get('commune', ''))
                    zones_data = commune_data.get('zones', commune_data.get('secteurs', []))

                if not commune_name:
                    continue

                commune_code = f'{province_code}-COM-{c_idx + 1:03d}'
                commune, _ = AdministrativeLevel.objects.get_or_create(
                    code=commune_code,
                    defaults={
                        'name': commune_name.strip(),
                        'level_type': AdministrativeLevel.LevelType.COMMUNE,
                        'parent': province,
                    },
                )
                counter['COMMUNE'] += 1

                for z_idx, zone_data in enumerate(zones_data):
                    if isinstance(zone_data, str):
                        zone_name = zone_data
                        collines_data = []
                    else:
                        zone_name = zone_data.get('name', zone_data.get('zone', ''))
                        collines_data = zone_data.get('collines', zone_data.get('quartiers', []))

                    if not zone_name:
                        continue

                    zone_code = f'{commune_code}-ZON-{z_idx + 1:03d}'
                    zone, _ = AdministrativeLevel.objects.get_or_create(
                        code=zone_code,
                        defaults={
                            'name': zone_name.strip(),
                            'level_type': AdministrativeLevel.LevelType.ZONE,
                            'parent': commune,
                        },
                    )
                    counter['ZONE'] += 1

                    for col_idx, colline_data in enumerate(collines_data):
                        if isinstance(colline_data, str):
                            colline_name = colline_data
                        else:
                            colline_name = colline_data.get('name', colline_data.get('colline', ''))

                        if not colline_name:
                            continue

                        colline_code = f'{zone_code}-COL-{col_idx + 1:04d}'
                        AdministrativeLevel.objects.get_or_create(
                            code=colline_code,
                            defaults={
                                'name': colline_name.strip(),
                                'level_type': AdministrativeLevel.LevelType.COLLINE,
                                'parent': zone,
                            },
                        )
                        counter['COLLINE'] += 1
