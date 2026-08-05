import uuid

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.persistence.models import TenantMusicTrack


class MusicCatalogTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.tenant_id = uuid.uuid4()
        self.client.post(
            reverse('tenant-bootstrap'),
            {'tenant_id': str(self.tenant_id), 'tenant_name': 'Studio'},
            format='json',
        )

    def test_bootstrap_includes_music_catalog(self):
        response = self.client.post(
            reverse('tenant-bootstrap'),
            {'tenant_id': str(self.tenant_id), 'tenant_name': 'Studio'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('music_catalog', response.data['configuration'])
        self.assertEqual(response.data['configuration']['music_catalog'], [])

    def test_create_and_list_tenant_music_track(self):
        create = self.client.post(
            reverse('tenant-music', kwargs={'tenant_id': self.tenant_id}),
            {
                'title': 'Custom Beat',
                'source': 'https://studio-assets.b-cdn.net/bgm/custom.mp3',
                'size': 1024,
                'meta_data': {'cms_music_uuid': 'music-1'},
            },
            format='json',
        )
        self.assertEqual(create.status_code, status.HTTP_201_CREATED)
        self.assertEqual(create.data['title'], 'Custom Beat')
        self.assertEqual(create.data['source'], 'https://studio-assets.b-cdn.net/bgm/custom.mp3')
        self.assertFalse(create.data['is_system_default'])
        self.assertEqual(create.data['meta_data']['cms_music_uuid'], 'music-1')

        listed = self.client.get(
            reverse('tenant-music', kwargs={'tenant_id': self.tenant_id}),
        )
        self.assertEqual(listed.status_code, status.HTTP_200_OK)
        self.assertEqual(len(listed.data), 1)
        self.assertEqual(listed.data[0]['track_id'], create.data['track_id'])

        bootstrap = self.client.post(
            reverse('tenant-bootstrap'),
            {'tenant_id': str(self.tenant_id), 'tenant_name': 'Studio'},
            format='json',
        )
        self.assertEqual(len(bootstrap.data['configuration']['music_catalog']), 1)

    def test_inactive_music_tracks_are_excluded(self):
        TenantMusicTrack.objects.create(
            tenant_id=self.tenant_id,
            title='Hidden',
            source='https://studio-assets.b-cdn.net/bgm/hidden.mp3',
            is_active=False,
        )
        response = self.client.get(
            reverse('tenant-music', kwargs={'tenant_id': self.tenant_id}),
        )
        self.assertEqual(response.data, [])

    def test_system_defaults_appear_in_catalog_for_all_tenants(self):
        system_id = uuid.uuid4()
        TenantMusicTrack.objects.create(
            id=system_id,
            tenant=None,
            title='Twilight Drift',
            source='https://studio-assets.b-cdn.net/bgm/twilight_drift.mp3',
            is_system_default=True,
            is_active=True,
        )

        response = self.client.get(
            reverse('tenant-music', kwargs={'tenant_id': self.tenant_id}),
        )
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['track_id'], str(system_id))
        self.assertTrue(response.data[0]['is_system_default'])
        self.assertIsNone(response.data[0]['tenant_id'])


class SeedStudioMusicCommandTests(TestCase):
    def test_seed_studio_music_loads_defaults(self):
        call_command('seed_studio_music')

        tracks = TenantMusicTrack.objects.filter(tenant__isnull=True, is_system_default=True)
        self.assertEqual(tracks.count(), 10)
        self.assertTrue(tracks.filter(title='Twilight Drift').exists())

    def test_seed_is_idempotent(self):
        call_command('seed_studio_music')
        call_command('seed_studio_music')
        self.assertEqual(
            TenantMusicTrack.objects.filter(tenant__isnull=True, is_system_default=True).count(),
            10,
        )
