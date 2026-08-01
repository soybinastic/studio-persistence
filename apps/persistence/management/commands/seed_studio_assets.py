"""Seed system-default studio media assets from fixtures."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.persistence.asset_utils import default_label_for_asset, infer_media_format
from apps.persistence.models import StudioMediaAsset

FIXTURE_PATH = (
    Path(__file__).resolve().parents[2] / 'fixtures' / 'default_studio_assets.json'
)


class Command(BaseCommand):
    help = 'Seed system-default studio media assets (backgrounds, overlays, logos, etc.)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--file',
            default=str(FIXTURE_PATH),
            help='Path to JSON fixture (default: apps/persistence/fixtures/default_studio_assets.json)',
        )
        parser.add_argument(
            '--include-tenant-assets',
            action='store_true',
            default=False,
            help='Import all rows from the fixture, including tenant-specific uploads',
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

        if not isinstance(payload, list):
            raise CommandError('Fixture must be a JSON array of asset objects')

        include_all = options['include_tenant_assets']
        created = 0
        updated = 0
        skipped = 0

        with transaction.atomic():
            for index, row in enumerate(payload):
                if not include_all and not row.get('is_default', False):
                    skipped += 1
                    continue

                asset_id = uuid.UUID(str(row['uuid']))
                asset_type = int(row['type'])
                source = str(row['source']).strip()
                if not source:
                    skipped += 1
                    continue

                media_format = infer_media_format(source, asset_type)
                defaults = {
                    'tenant': None,
                    'asset_type': asset_type,
                    'source': source,
                    'thumbnail': row.get('thumbnail') or '',
                    'size': int(row.get('size') or 0),
                    'media_format': media_format,
                    'label': default_label_for_asset(asset_type, str(asset_id), source),
                    'is_system_default': bool(row.get('is_default', False)),
                    'is_active': bool(row.get('is_active', True)),
                    'meta_data': row.get('meta_data') or {},
                    'sort_order': index,
                }

                if options['dry_run']:
                    self.stdout.write(
                        f"Would upsert {asset_id} type={asset_type} format={media_format}"
                    )
                    continue

                _, was_created = StudioMediaAsset.objects.update_or_create(
                    id=asset_id,
                    defaults=defaults,
                )
                if was_created:
                    created += 1
                else:
                    updated += 1

            if options['dry_run']:
                transaction.set_rollback(True)

        self.stdout.write(
            self.style.SUCCESS(
                f'Seed complete: created={created}, updated={updated}, skipped={skipped}'
            )
        )
