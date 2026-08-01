"""Seed system-default banner and ticker materials from fixtures."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.persistence.models import TenantBannerMaterial, TenantTickerMaterial

FIXTURE_PATH = (
    Path(__file__).resolve().parents[2] / 'fixtures' / 'default_text_materials.json'
)


class Command(BaseCommand):
    help = 'Seed system-default banner and ticker materials'

    def add_arguments(self, parser):
        parser.add_argument(
            '--file',
            default=str(FIXTURE_PATH),
            help='Path to JSON fixture',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Parse and validate without writing to the database',
        )

    def handle(self, *args, **options):
        fixture_path = Path(options['file'])
        if not fixture_path.exists():
            raise CommandError(f'Fixture not found: {fixture_path}')

        with fixture_path.open(encoding='utf-8') as handle:
            payload = json.load(handle)

        created = 0
        updated = 0

        with transaction.atomic():
            for index, row in enumerate(payload.get('banners', [])):
                if not row.get('is_default', False):
                    continue
                material_id = uuid.UUID(str(row['uuid']))
                defaults = {
                    'tenant': None,
                    'label': str(row.get('label') or row.get('title') or 'Banner'),
                    'title': str(row.get('title') or ''),
                    'description': str(row.get('description') or ''),
                    'theme': str(row.get('theme') or 'classic'),
                    'primary': str(row.get('primary') or '#111111'),
                    'secondary': str(row.get('secondary') or '#374151'),
                    'accent': str(row.get('accent') or '#38bdf8'),
                    'font_size': int(row.get('font_size') or 32),
                    'is_display_names': bool(row.get('is_display_names', True)),
                    'is_system_default': True,
                    'is_active': bool(row.get('is_active', True)),
                    'sort_order': index,
                }
                if options['dry_run']:
                    self.stdout.write(f'Would upsert banner {material_id}')
                    continue
                _, was_created = TenantBannerMaterial.objects.update_or_create(
                    id=material_id,
                    defaults=defaults,
                )
                created += int(was_created)
                updated += int(not was_created)

            for index, row in enumerate(payload.get('tickers', [])):
                if not row.get('is_default', False):
                    continue
                material_id = uuid.UUID(str(row['uuid']))
                defaults = {
                    'tenant': None,
                    'label': str(row.get('label') or 'Ticker'),
                    'ticker_text': str(row.get('ticker_text') or ''),
                    'ticker_position': str(row.get('ticker_position') or 'bottom'),
                    'ticker_direction': str(row.get('ticker_direction') or 'rtl'),
                    'ticker_speed': float(row.get('ticker_speed') or 2.0),
                    'primary': str(row.get('primary') or '#111827'),
                    'secondary': str(row.get('secondary') or '#ffffff'),
                    'is_system_default': True,
                    'is_active': bool(row.get('is_active', True)),
                    'sort_order': index,
                }
                if options['dry_run']:
                    self.stdout.write(f'Would upsert ticker {material_id}')
                    continue
                _, was_created = TenantTickerMaterial.objects.update_or_create(
                    id=material_id,
                    defaults=defaults,
                )
                created += int(was_created)
                updated += int(not was_created)

            if options['dry_run']:
                transaction.set_rollback(True)

        self.stdout.write(
            self.style.SUCCESS(f'Seed complete: created={created}, updated={updated}')
        )
