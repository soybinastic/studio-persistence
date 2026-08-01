import uuid

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.persistence.models import Tenant, TenantBannerMaterial, TenantTickerMaterial


class TextMaterialCatalogTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.tenant_id = uuid.uuid4()
        self.client.post(
            reverse('tenant-bootstrap'),
            {'tenant_id': str(self.tenant_id), 'tenant_name': 'Studio'},
            format='json',
        )

    def test_bootstrap_includes_text_material_catalog(self):
        TenantBannerMaterial.objects.create(
            tenant=None,
            label='System banner',
            title='Alex Rivera',
            description='Live from Studio A',
            is_system_default=True,
            is_active=True,
        )
        TenantTickerMaterial.objects.create(
            tenant=None,
            label='System ticker',
            ticker_text='Welcome!',
            is_system_default=True,
            is_active=True,
        )

        response = self.client.post(
            reverse('tenant-bootstrap'),
            {'tenant_id': str(self.tenant_id), 'tenant_name': 'Studio'},
            format='json',
        )

        catalog = response.data['configuration']['text_material_catalog']
        self.assertEqual(len(catalog['banners']), 1)
        self.assertEqual(len(catalog['tickers']), 1)
        self.assertEqual(catalog['banners'][0]['banner']['title'], 'Alex Rivera')
        self.assertEqual(catalog['tickers'][0]['ticker']['tickerText'], 'Welcome!')

    def test_create_banner_and_ticker_materials(self):
        banner_response = self.client.post(
            reverse('tenant-banners', kwargs={'tenant_id': self.tenant_id}),
            {
                'label': 'Opening',
                'title': 'Live Show',
                'description': 'Episode 12',
                'theme': 'classic',
            },
            format='json',
        )
        self.assertEqual(banner_response.status_code, status.HTTP_201_CREATED)
        banner_id = banner_response.data['material_id']
        self.assertEqual(banner_response.data['banner']['title'], 'Live Show')

        ticker_response = self.client.post(
            reverse('tenant-tickers', kwargs={'tenant_id': self.tenant_id}),
            {
                'label': 'Promo',
                'ticker_text': 'Subscribe for more content',
                'ticker_position': 'top',
            },
            format='json',
        )
        self.assertEqual(ticker_response.status_code, status.HTTP_201_CREATED)
        ticker_id = ticker_response.data['material_id']

        catalog_response = self.client.get(
            reverse('tenant-text-materials', kwargs={'tenant_id': self.tenant_id}),
        )
        self.assertEqual(catalog_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(catalog_response.data['banners']), 1)
        self.assertEqual(len(catalog_response.data['tickers']), 1)

        patch_response = self.client.patch(
            reverse(
                'tenant-banner-detail',
                kwargs={'tenant_id': self.tenant_id, 'banner_id': banner_id},
            ),
            {'title': 'Updated Show'},
            format='json',
        )
        self.assertEqual(patch_response.status_code, status.HTTP_200_OK)
        self.assertEqual(patch_response.data['banner']['title'], 'Updated Show')

        delete_response = self.client.delete(
            reverse(
                'tenant-ticker-detail',
                kwargs={'tenant_id': self.tenant_id, 'ticker_id': ticker_id},
            ),
        )
        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)

    def test_cannot_update_system_default_banner(self):
        system_banner = TenantBannerMaterial.objects.create(
            tenant=None,
            label='System',
            title='System Banner',
            is_system_default=True,
            is_active=True,
        )
        response = self.client.patch(
            reverse(
                'tenant-banner-detail',
                kwargs={'tenant_id': self.tenant_id, 'banner_id': system_banner.id},
            ),
            {'title': 'Hacked'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class SeedTextMaterialsCommandTests(TestCase):
    def test_seed_text_materials_loads_defaults(self):
        call_command('seed_text_materials')

        self.assertEqual(TenantBannerMaterial.objects.filter(tenant__isnull=True).count(), 3)
        self.assertEqual(TenantTickerMaterial.objects.filter(tenant__isnull=True).count(), 3)

    def test_seed_is_idempotent(self):
        call_command('seed_text_materials')
        call_command('seed_text_materials')
        self.assertEqual(TenantBannerMaterial.objects.filter(tenant__isnull=True).count(), 3)
