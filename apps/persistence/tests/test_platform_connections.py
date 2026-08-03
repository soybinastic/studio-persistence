"""Tests for platform connections and Twitch OAuth integration."""

from __future__ import annotations

import uuid
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from cryptography.fernet import Fernet

from apps.persistence.models import ConnectionStatus, PlatformConnection, PlatformType, TenantDestination
from apps.persistence.platform_connection_service import PlatformConnectionService
from apps.persistence.exceptions import PlatformIntegrationError
from apps.persistence.twitch_service import (
    TwitchConnectionResult,
    TwitchIntegrationError,
    TwitchTokenResponse,
    TwitchUser,
)


TWITCH_SETTINGS = {
    'TWITCH_CLIENT_ID': 'test-client-id',
    'TWITCH_CLIENT_SECRET': 'test-client-secret',
    'TWITCH_REDIRECT_URI': 'http://testserver/api/persistence/oauth/twitch/callback/',
    'FRONTEND_URL': 'http://localhost:5173',
    'TOKEN_ENCRYPTION_KEY': Fernet.generate_key().decode(),
}


def _mock_twitch_result() -> TwitchConnectionResult:
    return TwitchConnectionResult(
        user=TwitchUser(
            id='12345',
            login='streamer_pro',
            display_name='Streamer Pro',
            email='streamer@example.com',
        ),
        tokens=TwitchTokenResponse(
            access_token='access-token',
            refresh_token='refresh-token',
            expires_in=3600,
            scope=['channel:read:stream_key', 'user:read:email', 'chat:read'],
            token_type='bearer',
        ),
        stream_key='live-stream-key',
        rtmp_url='rtmp://live.twitch.tv/app/live-stream-key',
    )


@override_settings(**TWITCH_SETTINGS)
class PlatformConnectionTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.tenant_id = uuid.uuid4()
        self.client.post(
            reverse('tenant-bootstrap'),
            {'tenant_id': str(self.tenant_id), 'tenant_name': 'Studio'},
            format='json',
        )

    def test_bootstrap_includes_empty_platform_connections(self):
        response = self.client.post(
            reverse('tenant-bootstrap'),
            {'tenant_id': str(self.tenant_id), 'tenant_name': 'Studio'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['configuration']['platform_connections'], [])

    @patch('apps.persistence.platform_connection_service.complete_oauth_connection')
    def test_twitch_oauth_callback_creates_connection_and_destination(self, mock_complete):
        mock_complete.return_value = _mock_twitch_result()

        authorize_response = self.client.get(
            reverse('twitch-oauth-authorize'),
            {'tenant_id': str(self.tenant_id), 'return_url': 'http://localhost:5173/'},
        )
        self.assertEqual(authorize_response.status_code, status.HTTP_200_OK)
        self.assertIn('authorize_url', authorize_response.data)

        service = __import__(
            'apps.persistence.platform_connection_service',
            fromlist=['PlatformConnectionService'],
        ).PlatformConnectionService()
        state = service._sign_state(
            {
                'tenant_id': str(self.tenant_id),
                'platform': PlatformType.TWITCH,
                'return_url': 'http://localhost:5173/',
            },
        )

        callback_response = self.client.get(
            reverse('twitch-oauth-callback'),
            {'code': 'oauth-code', 'state': state},
        )
        self.assertEqual(callback_response.status_code, status.HTTP_302_FOUND)
        self.assertIn('twitch=connected', callback_response['Location'])

        connections = PlatformConnection.objects.filter(tenant_id=self.tenant_id)
        self.assertEqual(connections.count(), 1)
        connection = connections.first()
        assert connection is not None
        self.assertEqual(connection.platform, PlatformType.TWITCH)
        self.assertEqual(connection.status, ConnectionStatus.CONNECTED)
        self.assertEqual(connection.platform_login, 'streamer_pro')
        self.assertTrue(connection.stream_key_encrypted)
        self.assertFalse(connection.access_token_encrypted.startswith('access-token'))

        destinations = TenantDestination.objects.filter(tenant_id=self.tenant_id, platform='twitch')
        self.assertEqual(destinations.count(), 1)
        self.assertEqual(destinations.first().url, 'rtmp://live.twitch.tv/app/live-stream-key')

        list_response = self.client.get(
            reverse('tenant-platform-connections', kwargs={'tenant_id': self.tenant_id}),
        )
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(list_response.data), 1)
        self.assertTrue(list_response.data[0]['has_stream_key'])
        self.assertNotIn('access_token', list_response.data[0])

    @patch('apps.persistence.platform_connection_service.complete_oauth_connection')
    def test_twitch_chat_credentials_endpoint(self, mock_complete):
        mock_complete.return_value = _mock_twitch_result()
        service = PlatformConnectionService()
        state = service._sign_state({'tenant_id': str(self.tenant_id), 'platform': PlatformType.TWITCH})
        self.client.get(reverse('twitch-oauth-callback'), {'code': 'oauth-code', 'state': state})

        response = self.client.get(
            reverse('twitch-chat-credentials', kwargs={'tenant_id': self.tenant_id}),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['nick'], 'streamer_pro')
        self.assertEqual(response.data['channel'], 'streamer_pro')
        self.assertEqual(response.data['access_token'], 'access-token')

    @patch('apps.persistence.platform_connection_service.complete_oauth_connection')
    def test_delete_platform_connection_removes_linked_destination(self, mock_complete):
        mock_complete.return_value = _mock_twitch_result()
        service = __import__(
            'apps.persistence.platform_connection_service',
            fromlist=['PlatformConnectionService'],
        ).PlatformConnectionService()
        state = service._sign_state({'tenant_id': str(self.tenant_id), 'platform': PlatformType.TWITCH})
        self.client.get(reverse('twitch-oauth-callback'), {'code': 'oauth-code', 'state': state})

        connection = PlatformConnection.objects.get(tenant_id=self.tenant_id)
        delete_response = self.client.delete(
            reverse(
                'tenant-platform-connection-detail',
                kwargs={'tenant_id': self.tenant_id, 'connection_id': connection.id},
            ),
        )
        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(PlatformConnection.objects.filter(tenant_id=self.tenant_id).count(), 0)
        self.assertEqual(TenantDestination.objects.filter(tenant_id=self.tenant_id).count(), 0)

    @override_settings(TWITCH_CLIENT_ID='')
    def test_build_authorize_url_requires_client_id(self):
        service = PlatformConnectionService()
        with self.assertRaises(PlatformIntegrationError):
            service.build_twitch_authorize_url(self.tenant_id)

    def test_import_twitch_connection_from_embed(self):
        payload = {
            'platform': PlatformType.TWITCH,
            'name': 'Streamer Pro',
            'platform_login': 'streamer_pro',
            'platform_user_id': '12345',
            'access_token': 'access-token',
            'refresh_token': 'refresh-token',
            'stream_key': 'live-stream-key',
            'rtmp_url': 'rtmp://live.twitch.tv/app',
            'metadata': {'source': 'cms_embed'},
        }

        response = self.client.post(
            reverse('tenant-platform-connection-import', kwargs={'tenant_id': self.tenant_id}),
            payload,
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['platform'], PlatformType.TWITCH)
        self.assertEqual(response.data['platform_login'], 'streamer_pro')
        self.assertTrue(response.data['has_stream_key'])

        connection = PlatformConnection.objects.get(tenant_id=self.tenant_id)
        self.assertEqual(connection.status, ConnectionStatus.CONNECTED)
        self.assertFalse(connection.access_token_encrypted.startswith('access-token'))

        destination = TenantDestination.objects.get(tenant_id=self.tenant_id, platform='twitch')
        self.assertEqual(destination.url, 'rtmp://live.twitch.tv/app/live-stream-key')

    def test_import_facebook_connection_from_embed(self):
        payload = {
            'platform': PlatformType.FACEBOOK,
            'name': 'My Page (Page)',
            'platform_login': 'My Page (Page)',
            'platform_user_id': '123456789',
            'access_token': 'fb-access-token',
            'stream_key': 'fb-stream-key',
            'rtmp_url': 'rtmps://live-api-s.facebook.com:443/rtmp/',
            'metadata': {
                'source': 'cms_oauth',
                'account_type': 'Page',
                'page_id': '123456789',
                'facebook_user_id': '987654321',
                'live_video_id': 'live-video-id',
            },
        }

        response = self.client.post(
            reverse('tenant-platform-connection-import', kwargs={'tenant_id': self.tenant_id}),
            payload,
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['platform'], PlatformType.FACEBOOK)
        self.assertTrue(response.data['has_stream_key'])

        connection = PlatformConnection.objects.get(tenant_id=self.tenant_id, platform=PlatformType.FACEBOOK)
        self.assertEqual(connection.status, ConnectionStatus.CONNECTED)
        self.assertEqual(connection.metadata.get('live_video_id'), 'live-video-id')

        destination = TenantDestination.objects.get(tenant_id=self.tenant_id, platform='facebook')
        self.assertEqual(
            destination.url,
            'rtmps://live-api-s.facebook.com:443/rtmp/fb-stream-key',
        )

    def test_facebook_embed_credentials_endpoint(self):
        import_response = self.client.post(
            reverse('tenant-platform-connection-import', kwargs={'tenant_id': self.tenant_id}),
            {
                'platform': PlatformType.FACEBOOK,
                'name': 'My Page (Page)',
                'platform_login': 'My Page (Page)',
                'platform_user_id': 'page-123',
                'access_token': 'fb-page-token',
                'stream_key': 'fb-stream-key',
                'rtmp_url': 'rtmps://live-api-s.facebook.com:443/rtmp/',
                'metadata': {
                    'source': 'cms_embed',
                    'account_type': 'Page',
                    'page_id': 'page-123',
                    'facebook_user_id': 'user-456',
                },
            },
            format='json',
        )
        self.assertEqual(import_response.status_code, status.HTTP_200_OK)
        connection_id = import_response.data['connection_id']

        credentials_response = self.client.get(
            reverse(
                'facebook-embed-credentials',
                kwargs={'tenant_id': self.tenant_id, 'connection_id': connection_id},
            ),
        )
        self.assertEqual(credentials_response.status_code, status.HTTP_200_OK)
        self.assertEqual(credentials_response.data['access_token'], 'fb-page-token')
        self.assertEqual(credentials_response.data['platform_user_id'], 'page-123')
        self.assertEqual(credentials_response.data['metadata']['page_id'], 'page-123')

    def test_youtube_embed_credentials_endpoint(self):
        import_response = self.client.post(
            reverse('tenant-platform-connection-import', kwargs={'tenant_id': self.tenant_id}),
            {
                'platform': PlatformType.YOUTUBE,
                'name': 'My Channel',
                'platform_login': 'My Channel',
                'platform_user_id': 'channel-123',
                'access_token': 'yt-access-token',
                'refresh_token': 'yt-refresh-token',
                'metadata': {
                    'source': 'cms_embed',
                    'channel_id': 'channel-123',
                },
            },
            format='json',
        )
        self.assertEqual(import_response.status_code, status.HTTP_200_OK)
        connection_id = import_response.data['connection_id']

        credentials_response = self.client.get(
            reverse(
                'facebook-embed-credentials',
                kwargs={'tenant_id': self.tenant_id, 'connection_id': connection_id},
            ),
        )
        self.assertEqual(credentials_response.status_code, status.HTTP_200_OK)
        self.assertEqual(credentials_response.data['access_token'], 'yt-access-token')
        self.assertEqual(credentials_response.data['refresh_token'], 'yt-refresh-token')
        self.assertEqual(credentials_response.data['platform_user_id'], 'channel-123')
        self.assertEqual(credentials_response.data['metadata']['channel_id'], 'channel-123')

    def test_youtube_import_resolves_rtmp_url_from_stream_key(self):
        import_response = self.client.post(
            reverse('tenant-platform-connection-import', kwargs={'tenant_id': self.tenant_id}),
            {
                'platform': PlatformType.YOUTUBE,
                'name': 'My Channel',
                'platform_login': 'My Channel',
                'platform_user_id': 'channel-123',
                'access_token': 'yt-access-token',
                'stream_key': 'yt-stream-key',
                'rtmp_url': 'rtmp://a.rtmp.youtube.com/live2',
                'metadata': {'source': 'cms_embed'},
            },
            format='json',
        )
        self.assertEqual(import_response.status_code, status.HTTP_200_OK)
        self.assertTrue(import_response.data['has_stream_key'])

        destination = TenantDestination.objects.get(tenant_id=self.tenant_id)
        self.assertEqual(
            destination.url,
            'rtmp://a.rtmp.youtube.com/live2/yt-stream-key',
        )

    def test_refresh_skips_cms_embed_connection_with_stream_key(self):
        import_response = self.client.post(
            reverse('tenant-platform-connection-import', kwargs={'tenant_id': self.tenant_id}),
            {
                'platform': PlatformType.TWITCH,
                'name': 'Streamer Pro',
                'platform_login': 'streamer_pro',
                'platform_user_id': '12345',
                'access_token': 'access-token',
                'stream_key': 'live-stream-key',
                'rtmp_url': 'rtmp://live.twitch.tv/app',
                'metadata': {'source': 'cms_oauth'},
            },
            format='json',
        )
        self.assertEqual(import_response.status_code, status.HTTP_200_OK)

        connection = PlatformConnection.objects.get(tenant_id=self.tenant_id)
        connection.status = ConnectionStatus.ERROR
        connection.save(update_fields=['status', 'updated_at'])
        original_stream_key = connection.stream_key_encrypted

        with patch('apps.persistence.platform_connection_service.fetch_stream_key') as mock_fetch:
            refresh_response = self.client.post(
                reverse(
                    'tenant-platform-connection-refresh',
                    kwargs={'tenant_id': self.tenant_id, 'connection_id': connection.id},
                ),
            )

        self.assertEqual(refresh_response.status_code, status.HTTP_200_OK)
        self.assertEqual(refresh_response.data['status'], ConnectionStatus.CONNECTED)
        mock_fetch.assert_not_called()

        connection.refresh_from_db()
        self.assertEqual(connection.status, ConnectionStatus.CONNECTED)
        self.assertEqual(connection.stream_key_encrypted, original_stream_key)

    @patch('apps.persistence.platform_connection_service.fetch_stream_key')
    @patch('apps.persistence.platform_connection_service.complete_oauth_connection')
    def test_refresh_failure_does_not_set_error_status(self, mock_complete, mock_fetch):
        mock_complete.return_value = _mock_twitch_result()
        service = PlatformConnectionService()
        state = service._sign_state({'tenant_id': str(self.tenant_id), 'platform': PlatformType.TWITCH})
        self.client.get(reverse('twitch-oauth-callback'), {'code': 'oauth-code', 'state': state})

        connection = PlatformConnection.objects.get(tenant_id=self.tenant_id)
        mock_fetch.side_effect = TwitchIntegrationError('Helix failed')

        refresh_response = self.client.post(
            reverse(
                'tenant-platform-connection-refresh',
                kwargs={'tenant_id': self.tenant_id, 'connection_id': connection.id},
            ),
        )
        self.assertEqual(refresh_response.status_code, status.HTTP_400_BAD_REQUEST)

        connection.refresh_from_db()
        self.assertEqual(connection.status, ConnectionStatus.CONNECTED)

    def test_import_youtube_connection_without_rtmp(self):
        payload = {
            'platform': PlatformType.YOUTUBE,
            'name': 'My Channel',
            'platform_login': 'my-channel',
            'platform_user_id': 'UC123',
            'access_token': 'yt-access',
            'refresh_token': 'yt-refresh',
        }

        response = self.client.post(
            reverse('tenant-platform-connection-import', kwargs={'tenant_id': self.tenant_id}),
            payload,
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['platform'], PlatformType.YOUTUBE)
        self.assertEqual(
            PlatformConnection.objects.filter(
                tenant_id=self.tenant_id,
                platform=PlatformType.YOUTUBE,
            ).count(),
            1,
        )
        self.assertEqual(
            TenantDestination.objects.filter(
                tenant_id=self.tenant_id,
                platform=PlatformType.YOUTUBE,
            ).count(),
            0,
        )
