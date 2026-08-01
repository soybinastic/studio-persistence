import uuid

from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient


class TenantBootstrapTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.tenant_id = uuid.uuid4()

    def test_creates_tenant_with_empty_configuration(self):
        response = self.client.post(
            reverse('tenant-bootstrap'),
            {'tenant_id': str(self.tenant_id), 'tenant_name': 'My Studio'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data['created'])
        self.assertEqual(response.data['tenant_id'], str(self.tenant_id))
        self.assertEqual(response.data['tenant_name'], 'My Studio')
        self.assertEqual(response.data['configuration']['scenes'], [])
        self.assertEqual(response.data['configuration']['destinations'], [])
        self.assertEqual(response.data['configuration']['layout'], 'CONTAIN')
        self.assertIsNone(response.data['configuration']['active_scene_id'])
        self.assertIn('asset_catalog', response.data['configuration'])
        self.assertEqual(response.data['configuration']['asset_catalog']['logos'], [])
        self.assertIn('text_material_catalog', response.data['configuration'])
        self.assertEqual(response.data['configuration']['text_material_catalog']['banners'], [])

    def test_returns_existing_tenant_without_creating(self):
        payload = {'tenant_id': str(self.tenant_id), 'tenant_name': 'My Studio'}
        self.client.post(reverse('tenant-bootstrap'), payload, format='json')

        response = self.client.post(reverse('tenant-bootstrap'), payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data['created'])
        self.assertEqual(response.data['tenant_name'], 'My Studio')

    def test_updates_tenant_name_on_existing_tenant(self):
        payload = {'tenant_id': str(self.tenant_id), 'tenant_name': 'Old Name'}
        self.client.post(reverse('tenant-bootstrap'), payload, format='json')

        response = self.client.post(
            reverse('tenant-bootstrap'),
            {'tenant_id': str(self.tenant_id), 'tenant_name': 'New Name'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['tenant_name'], 'New Name')


class ScenePersistenceTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.tenant_id = uuid.uuid4()
        self.client.post(
            reverse('tenant-bootstrap'),
            {'tenant_id': str(self.tenant_id), 'tenant_name': 'Studio'},
            format='json',
        )

    def test_create_and_update_scene(self):
        create_response = self.client.post(
            reverse('tenant-scenes', kwargs={'tenant_id': self.tenant_id}),
            {'type': 'CAMERA', 'name': 'Opening', 'layout': 'GRID'},
            format='json',
        )
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        scene_id = create_response.data['scene_id']
        self.assertEqual(create_response.data['name'], 'Opening')
        self.assertEqual(create_response.data['layout'], 'GRID')
        self.assertTrue(create_response.data['is_active'])

        patch_response = self.client.patch(
            reverse(
                'tenant-scene-detail',
                kwargs={'tenant_id': self.tenant_id, 'scene_id': scene_id},
            ),
            {
                'graphics_config': {
                    'logo': {'url': 'https://example.com/logo.png', 'is_active': True},
                },
                'devices': {'cameraId': 'cam-1'},
                'background_music': {'enabled': True, 'volume': 0.8},
            },
            format='json',
        )
        self.assertEqual(patch_response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            patch_response.data['graphics_config']['logo']['url'],
            'https://example.com/logo.png',
        )
        self.assertEqual(patch_response.data['devices']['cameraId'], 'cam-1')
        self.assertTrue(patch_response.data['background_music']['enabled'])

        bootstrap_response = self.client.post(
            reverse('tenant-bootstrap'),
            {'tenant_id': str(self.tenant_id), 'tenant_name': 'Studio'},
            format='json',
        )
        self.assertEqual(len(bootstrap_response.data['configuration']['scenes']), 1)
        self.assertEqual(
            bootstrap_response.data['configuration']['scenes'][0]['scene_id'],
            scene_id,
        )


class DestinationPersistenceTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.tenant_id = uuid.uuid4()
        self.client.post(
            reverse('tenant-bootstrap'),
            {'tenant_id': str(self.tenant_id), 'tenant_name': 'Studio'},
            format='json',
        )

    def test_create_update_delete_destination(self):
        create_response = self.client.post(
            reverse('tenant-destinations', kwargs={'tenant_id': self.tenant_id}),
            {
                'url': 'rtmp://live.twitch.tv/app/stream-key',
                'label': 'Twitch',
                'platform': 'twitch',
            },
            format='json',
        )
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        destination_id = create_response.data['destination_id']

        patch_response = self.client.patch(
            reverse(
                'tenant-destination-detail',
                kwargs={
                    'tenant_id': self.tenant_id,
                    'destination_id': destination_id,
                },
            ),
            {'label': 'Twitch Main'},
            format='json',
        )
        self.assertEqual(patch_response.status_code, status.HTTP_200_OK)
        self.assertEqual(patch_response.data['label'], 'Twitch Main')

        delete_response = self.client.delete(
            reverse(
                'tenant-destination-detail',
                kwargs={
                    'tenant_id': self.tenant_id,
                    'destination_id': destination_id,
                },
            ),
        )
        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)

        bootstrap_response = self.client.post(
            reverse('tenant-bootstrap'),
            {'tenant_id': str(self.tenant_id), 'tenant_name': 'Studio'},
            format='json',
        )
        self.assertEqual(bootstrap_response.data['configuration']['destinations'], [])


class ConfigurationPersistenceTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.tenant_id = uuid.uuid4()
        self.client.post(
            reverse('tenant-bootstrap'),
            {'tenant_id': str(self.tenant_id), 'tenant_name': 'Studio'},
            format='json',
        )

    def test_patch_configuration(self):
        response = self.client.patch(
            reverse('tenant-configuration', kwargs={'tenant_id': self.tenant_id}),
            {
                'layout': 'CINEMA',
                'devices': {'speakerId': 'speaker-1'},
                'tile_order_config': {'version': 1, 'assignments': {'0': 'host-peer'}},
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['layout'], 'CINEMA')
        self.assertEqual(response.data['devices']['speakerId'], 'speaker-1')
        self.assertEqual(response.data['tile_order_config']['assignments']['0'], 'host-peer')
