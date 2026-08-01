import uuid

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.persistence.constants import (
    ASSET_TYPE_BACKGROUND,
    ASSET_TYPE_LOGO,
    ASSET_TYPE_OVERLAY,
    MEDIA_FORMAT_IMAGE,
    MEDIA_FORMAT_VIDEO,
)
from apps.persistence.models import StudioMediaAsset, Tenant


class AssetCatalogTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.tenant_id = uuid.uuid4()
        self.client.post(
            reverse('tenant-bootstrap'),
            {'tenant_id': str(self.tenant_id), 'tenant_name': 'Studio'},
            format='json',
        )

    def _create_system_asset(self, asset_id, asset_type, source, media_format=MEDIA_FORMAT_IMAGE):
        return StudioMediaAsset.objects.create(
            id=asset_id,
            tenant=None,
            asset_type=asset_type,
            source=source,
            media_format=media_format,
            is_system_default=True,
            is_active=True,
        )

    def test_bootstrap_includes_asset_catalog(self):
        logo_id = uuid.uuid4()
        bg_id = uuid.uuid4()
        video_id = uuid.uuid4()
        overlay_id = uuid.uuid4()

        self._create_system_asset(
            logo_id,
            ASSET_TYPE_LOGO,
            'https://studio-assets.b-cdn.net/logo/default.png',
        )
        self._create_system_asset(
            bg_id,
            ASSET_TYPE_BACKGROUND,
            'https://studio-assets.b-cdn.net/bg/default.jpg',
        )
        self._create_system_asset(
            video_id,
            ASSET_TYPE_BACKGROUND,
            'https://studio-assets.b-cdn.net/abg/default.mp4',
            media_format=MEDIA_FORMAT_VIDEO,
        )
        self._create_system_asset(
            overlay_id,
            ASSET_TYPE_OVERLAY,
            'https://studio-assets.b-cdn.net/overlay/default.png',
        )

        response = self.client.post(
            reverse('tenant-bootstrap'),
            {'tenant_id': str(self.tenant_id), 'tenant_name': 'Studio'},
            format='json',
        )

        catalog = response.data['configuration']['asset_catalog']
        self.assertEqual(len(catalog['logos']), 1)
        self.assertEqual(len(catalog['backgrounds']), 1)
        self.assertEqual(len(catalog['background_videos']), 1)
        self.assertEqual(len(catalog['overlays']), 1)
        self.assertEqual(catalog['logos'][0]['asset_id'], str(logo_id))

    def test_tenant_assets_endpoint_merges_system_and_tenant_assets(self):
        system_id = uuid.uuid4()
        tenant_id = uuid.uuid4()
        self._create_system_asset(
            system_id,
            ASSET_TYPE_LOGO,
            'https://studio-assets.b-cdn.net/logo/system.png',
        )
        tenant = Tenant.objects.get(id=self.tenant_id)
        StudioMediaAsset.objects.create(
            id=tenant_id,
            tenant=tenant,
            asset_type=ASSET_TYPE_LOGO,
            source='https://studio-assets.b-cdn.net/logo/custom.png',
            media_format=MEDIA_FORMAT_IMAGE,
            is_system_default=False,
            is_active=True,
        )

        response = self.client.get(
            reverse('tenant-assets', kwargs={'tenant_id': self.tenant_id}),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['logos']), 2)
        asset_ids = {item['asset_id'] for item in response.data['logos']}
        self.assertEqual(asset_ids, {str(system_id), str(tenant_id)})

    def test_inactive_assets_are_excluded(self):
        asset_id = uuid.uuid4()
        StudioMediaAsset.objects.create(
            id=asset_id,
            tenant=None,
            asset_type=ASSET_TYPE_LOGO,
            source='https://studio-assets.b-cdn.net/logo/hidden.png',
            media_format=MEDIA_FORMAT_IMAGE,
            is_system_default=True,
            is_active=False,
        )

        response = self.client.get(
            reverse('tenant-assets', kwargs={'tenant_id': self.tenant_id}),
        )

        self.assertEqual(response.data['logos'], [])


class SeedStudioAssetsCommandTests(TestCase):
    def test_seed_studio_assets_loads_defaults(self):
        call_command('seed_studio_assets')

        self.assertEqual(StudioMediaAsset.objects.filter(tenant__isnull=True).count(), 25)
        self.assertEqual(
            StudioMediaAsset.objects.filter(
                tenant__isnull=True,
                asset_type=ASSET_TYPE_BACKGROUND,
                media_format=MEDIA_FORMAT_IMAGE,
            ).count(),
            16,
        )
        self.assertEqual(
            StudioMediaAsset.objects.filter(
                tenant__isnull=True,
                asset_type=ASSET_TYPE_BACKGROUND,
                media_format=MEDIA_FORMAT_VIDEO,
            ).count(),
            4,
        )
        self.assertEqual(
            StudioMediaAsset.objects.filter(
                tenant__isnull=True,
                asset_type=ASSET_TYPE_OVERLAY,
            ).count(),
            4,
        )
        self.assertEqual(
            StudioMediaAsset.objects.filter(
                tenant__isnull=True,
                asset_type=ASSET_TYPE_LOGO,
            ).count(),
            1,
        )

    def test_seed_is_idempotent(self):
        call_command('seed_studio_assets')
        call_command('seed_studio_assets')
        self.assertEqual(StudioMediaAsset.objects.filter(tenant__isnull=True).count(), 25)
