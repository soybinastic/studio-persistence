"""Seed system-default studio background music tracks from fixtures."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.persistence.models import TenantMusicTrack

FIXTURE_PATH = (
    Path(__file__).resolve().parents[2] / 'fixtures' / 'default_studio_music.json'
)


class Command(BaseCommand):
    help = 'Seed system-default studio background music tracks'

    def add_arguments(self, parser):
        parser.add_argument(
            '--file',
            default=str(FIXTURE_PATH),
            help='Path to JSON fixture (default: apps/persistence/fixtures/default_studio_music.json)',
        )
        parser.add_argument(
            '--include-non-defaults',
            action='store_true',
            default=False,
            help='Import all rows from the fixture, including non-default tracks',
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
            raise CommandError('Fixture must be a JSON array of music track objects')

        include_all = options['include_non_defaults']
        created = 0
        updated = 0
        skipped = 0

        with transaction.atomic():
            for index, row in enumerate(payload):
                is_default = bool(row.get('default', False) or row.get('is_default', False))
                if not include_all and not is_default:
                    skipped += 1
                    continue

                track_id = uuid.UUID(str(row['uuid']))
                source = str(row.get('source') or '').strip()
                title = str(row.get('title') or '').strip() or 'Studio track'
                if not source:
                    skipped += 1
                    continue

                defaults = {
                    'tenant': None,
                    'title': title,
                    'source': source,
                    'size': int(row.get('size') or 0),
                    'is_system_default': True if is_default else bool(row.get('is_system_default', False)),
                    'is_active': bool(row.get('is_active', True)),
                    'meta_data': row.get('meta_data') or {},
                    'sort_order': index,
                }

                if options['dry_run']:
                    self.stdout.write(f'Would upsert {track_id} title={title!r}')
                    continue

                _, was_created = TenantMusicTrack.objects.update_or_create(
                    id=track_id,
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
