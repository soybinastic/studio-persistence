"""Platform connection persistence and OAuth orchestration."""

from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Any

from django.core.signing import BadSignature, SignatureExpired, TimestampSigner
from django.db import transaction
from django.utils import timezone

from apps.persistence.crypto_utils import decrypt_secret, encrypt_secret
from apps.persistence.exceptions import (
    OAuthStateError,
    PlatformConnectionNotFoundError,
    PlatformIntegrationError,
    TenantNotFoundError,
)
from apps.persistence.models import (
    ConnectionStatus,
    PlatformConnection,
    PlatformType,
    Tenant,
    TenantDestination,
)
from apps.persistence.services import TenantService
from apps.persistence.twitch_service import (
    TWITCH_RTMP_INGEST,
    TwitchIntegrationError,
    complete_oauth_connection,
    refresh_access_token,
    fetch_stream_key,
    build_authorize_url,
)

FACEBOOK_RTMP_INGEST = 'rtmps://live-api-s.facebook.com:443/rtmp'


class PlatformConnectionService:
    OAUTH_STATE_MAX_AGE = 600

    def __init__(self, tenant_service: TenantService | None = None) -> None:
        self._tenant_service = tenant_service or TenantService()
        self._signer = TimestampSigner(salt='platform-oauth-state')

    def list_connections(self, tenant_id: uuid.UUID) -> list[PlatformConnection]:
        tenant = self._tenant_service.get_tenant(tenant_id)
        return list(
            tenant.platform_connections.select_related('destination').order_by(
                'sort_order',
                'created_at',
            ),
        )

    def get_connection(
        self,
        tenant_id: uuid.UUID,
        connection_id: uuid.UUID,
    ) -> PlatformConnection:
        connection = PlatformConnection.objects.select_related('destination').filter(
            tenant_id=tenant_id,
            id=connection_id,
        ).first()
        if connection is None:
            raise PlatformConnectionNotFoundError(
                f'Platform connection {connection_id} not found',
            )
        return connection

    def delete_connection(self, tenant_id: uuid.UUID, connection_id: uuid.UUID) -> None:
        connection = self.get_connection(tenant_id, connection_id)
        linked_destination = connection.destination
        connection.delete()
        if linked_destination is not None:
            linked_destination.delete()

    def disconnect_connection(self, tenant_id: uuid.UUID, connection_id: uuid.UUID) -> PlatformConnection:
        connection = self.get_connection(tenant_id, connection_id)
        connection.status = ConnectionStatus.DISCONNECTED
        connection.save(update_fields=['status', 'updated_at'])
        return connection

    def build_twitch_authorize_url(
        self,
        tenant_id: uuid.UUID,
        *,
        return_url: str = '',
    ) -> str:
        self._tenant_service.get_tenant(tenant_id)
        state = self._sign_state(
            {
                'tenant_id': str(tenant_id),
                'platform': PlatformType.TWITCH,
                'return_url': return_url,
            },
        )
        try:
            return build_authorize_url(state=state)
        except TwitchIntegrationError as exc:
            raise PlatformIntegrationError(str(exc)) from exc

    def complete_twitch_oauth(self, *, code: str, state: str) -> tuple[PlatformConnection, str]:
        payload = self._unsign_state(state)
        tenant_id = uuid.UUID(payload['tenant_id'])
        tenant = self._tenant_service.get_tenant(tenant_id)

        try:
            result = complete_oauth_connection(code)
        except TwitchIntegrationError as exc:
            raise PlatformIntegrationError(str(exc)) from exc

        expires_at = timezone.now() + timedelta(seconds=result.tokens.expires_in)

        with transaction.atomic():
            connection = PlatformConnection.objects.filter(
                tenant=tenant,
                platform=PlatformType.TWITCH,
            ).first()

            if connection is None:
                connection = PlatformConnection(
                    tenant=tenant,
                    platform=PlatformType.TWITCH,
                    sort_order=tenant.platform_connections.count(),
                )

            connection.name = result.user.display_name or result.user.login
            connection.status = ConnectionStatus.CONNECTED
            connection.platform_user_id = result.user.id
            connection.platform_login = result.user.login
            connection.access_token_encrypted = encrypt_secret(result.tokens.access_token)
            connection.refresh_token_encrypted = encrypt_secret(result.tokens.refresh_token)
            connection.token_expires_at = expires_at
            connection.stream_key_encrypted = encrypt_secret(result.stream_key)
            connection.metadata = {
                'email': result.user.email,
                'scopes': result.tokens.scope,
            }
            connection.save()

            destination = self._sync_twitch_destination(
                tenant=tenant,
                connection=connection,
                label=connection.name,
                rtmp_url=result.rtmp_url,
            )
            connection.destination = destination
            connection.save(update_fields=['destination', 'updated_at'])

        return connection, payload.get('return_url', '')

    def import_platform_connection_from_embed(
        self,
        tenant_id: uuid.UUID,
        platform: str,
        *,
        name: str,
        platform_login: str,
        platform_user_id: str = '',
        access_token: str = '',
        refresh_token: str = '',
        stream_key: str = '',
        rtmp_url: str = '',
        token_expires_at=None,
        metadata: dict[str, Any] | None = None,
    ) -> PlatformConnection:
        """Persist OAuth credentials supplied by CMS parent via studio-embed postMessage."""
        if platform not in PlatformType.values:
            raise PlatformIntegrationError(f'Unsupported platform "{platform}"')

        platform_type = PlatformType(platform)
        tenant = self._tenant_service.get_tenant(tenant_id)

        login = platform_login.strip()
        if not login:
            raise PlatformIntegrationError('platform_login is required')

        display_name = (name or login).strip() or login
        resolved_rtmp_url = self._resolve_embed_rtmp_url(platform_type, rtmp_url, stream_key)

        if platform_type == PlatformType.TWITCH and not resolved_rtmp_url:
            raise PlatformIntegrationError('Twitch import requires stream_key or rtmp_url')

        embed_metadata = dict(metadata or {})
        embed_metadata.setdefault('source', 'cms_embed')

        with transaction.atomic():
            connection = PlatformConnection.objects.filter(
                tenant=tenant,
                platform=platform_type,
            ).first()

            if connection is None:
                connection = PlatformConnection(
                    tenant=tenant,
                    platform=platform_type,
                    sort_order=tenant.platform_connections.count(),
                )

            connection.name = display_name
            connection.status = ConnectionStatus.CONNECTED
            connection.platform_user_id = platform_user_id.strip()
            connection.platform_login = login
            connection.metadata = embed_metadata

            if access_token.strip():
                connection.access_token_encrypted = encrypt_secret(access_token.strip())
            if refresh_token.strip():
                connection.refresh_token_encrypted = encrypt_secret(refresh_token.strip())
            if token_expires_at is not None:
                connection.token_expires_at = token_expires_at
            elif not refresh_token.strip():
                connection.token_expires_at = None

            if stream_key.strip():
                connection.stream_key_encrypted = encrypt_secret(stream_key.strip())

            connection.save()

            if resolved_rtmp_url:
                destination = self._sync_platform_destination(
                    tenant=tenant,
                    connection=connection,
                    platform=platform_type,
                    label=display_name,
                    rtmp_url=resolved_rtmp_url,
                )
                connection.destination = destination
                connection.save(update_fields=['destination', 'updated_at'])

        return connection

    def refresh_twitch_stream_key(
        self,
        tenant_id: uuid.UUID,
        connection_id: uuid.UUID,
    ) -> PlatformConnection:
        connection = self.get_connection(tenant_id, connection_id)
        if connection.platform != PlatformType.TWITCH:
            raise PlatformIntegrationError('Stream key refresh is only supported for Twitch')

        if self._is_cms_embed_connection(connection) and connection.stream_key_encrypted:
            if connection.status != ConnectionStatus.CONNECTED:
                connection.status = ConnectionStatus.CONNECTED
                connection.save(update_fields=['status', 'updated_at'])
            return connection

        access_token = self._ensure_valid_access_token(connection)
        try:
            stream_key = fetch_stream_key(access_token, connection.platform_user_id)
        except TwitchIntegrationError as exc:
            raise PlatformIntegrationError(str(exc)) from exc

        rtmp_url = f'rtmp://live.twitch.tv/app/{stream_key}'
        connection.stream_key_encrypted = encrypt_secret(stream_key)
        connection.status = ConnectionStatus.CONNECTED
        connection.save(update_fields=['stream_key_encrypted', 'status', 'updated_at'])

        destination = self._sync_twitch_destination(
            tenant=connection.tenant,
            connection=connection,
            label=connection.name,
            rtmp_url=rtmp_url,
        )
        connection.destination = destination
        connection.save(update_fields=['destination', 'updated_at'])
        return connection

    def serialize_connection(self, connection: PlatformConnection) -> dict[str, Any]:
        return {
            'connection_id': str(connection.id),
            'tenant_id': str(connection.tenant_id),
            'platform': connection.platform,
            'name': connection.name,
            'status': connection.status,
            'platform_user_id': connection.platform_user_id,
            'platform_login': connection.platform_login,
            'destination_id': str(connection.destination_id) if connection.destination_id else None,
            'has_stream_key': bool(connection.stream_key_encrypted),
            'metadata': connection.metadata or {},
            'sort_order': connection.sort_order,
            'created_at': connection.created_at.isoformat(),
            'updated_at': connection.updated_at.isoformat(),
        }

    def _ensure_valid_access_token(self, connection: PlatformConnection) -> str:
        if not connection.access_token_encrypted:
            connection.status = ConnectionStatus.AUTH_EXPIRED
            connection.save(update_fields=['status', 'updated_at'])
            raise PlatformIntegrationError('Missing Twitch access token')

        if connection.token_expires_at and connection.token_expires_at <= timezone.now():
            if not connection.refresh_token_encrypted:
                connection.status = ConnectionStatus.AUTH_EXPIRED
                connection.save(update_fields=['status', 'updated_at'])
                raise PlatformIntegrationError('Twitch access token expired')

            try:
                refreshed = refresh_access_token(
                    decrypt_secret(connection.refresh_token_encrypted),
                )
            except TwitchIntegrationError as exc:
                connection.status = ConnectionStatus.AUTH_EXPIRED
                connection.save(update_fields=['status', 'updated_at'])
                raise PlatformIntegrationError(str(exc)) from exc

            connection.access_token_encrypted = encrypt_secret(refreshed.access_token)
            connection.refresh_token_encrypted = encrypt_secret(refreshed.refresh_token)
            connection.token_expires_at = timezone.now() + timedelta(seconds=refreshed.expires_in)
            connection.save(
                update_fields=[
                    'access_token_encrypted',
                    'refresh_token_encrypted',
                    'token_expires_at',
                    'updated_at',
                ],
            )

        return decrypt_secret(connection.access_token_encrypted)

    def get_twitch_chat_credentials(self, tenant_id: uuid.UUID) -> dict[str, str]:
        connection = PlatformConnection.objects.filter(
            tenant_id=tenant_id,
            platform=PlatformType.TWITCH,
            status=ConnectionStatus.CONNECTED,
        ).first()
        if connection is None:
            raise PlatformConnectionNotFoundError(
                f'No connected Twitch platform for tenant {tenant_id}',
            )
        if not connection.platform_login:
            raise PlatformIntegrationError('Twitch connection is missing channel login')

        access_token = self._ensure_valid_access_token(connection)
        return {
            'nick': connection.platform_login,
            'channel': connection.platform_login,
            'access_token': access_token,
        }

    def _sync_twitch_destination(
        self,
        *,
        tenant: Tenant,
        connection: PlatformConnection,
        label: str,
        rtmp_url: str,
    ) -> TenantDestination:
        return self._sync_platform_destination(
            tenant=tenant,
            connection=connection,
            platform=PlatformType.TWITCH,
            label=label,
            rtmp_url=rtmp_url,
        )

    def _sync_platform_destination(
        self,
        *,
        tenant: Tenant,
        connection: PlatformConnection,
        platform: PlatformType,
        label: str,
        rtmp_url: str,
    ) -> TenantDestination:
        destination = connection.destination
        if destination is None:
            destination = TenantDestination.objects.filter(
                tenant=tenant,
                platform=platform,
            ).first()

        if destination is None:
            return TenantDestination.objects.create(
                tenant=tenant,
                label=label,
                url=rtmp_url,
                platform=platform,
                sort_order=tenant.destinations.count(),
            )

        destination.label = label
        destination.url = rtmp_url
        destination.platform = platform
        destination.save(update_fields=['label', 'url', 'platform', 'updated_at'])
        return destination

    @staticmethod
    def _is_cms_embed_connection(connection: PlatformConnection) -> bool:
        source = (connection.metadata or {}).get('source', '')
        return source in ('cms_oauth', 'cms_embed')

    @staticmethod
    def _resolve_embed_rtmp_url(
        platform: PlatformType,
        rtmp_url: str,
        stream_key: str,
    ) -> str:
        url = rtmp_url.strip()
        key = stream_key.strip()

        if not url and not key:
            return ''

        if url and key:
            if key in url:
                return url
            return f'{url.rstrip("/")}/{key}'

        if key and platform == PlatformType.TWITCH:
            return f'{TWITCH_RTMP_INGEST}/{key}'

        if key and platform == PlatformType.FACEBOOK:
            return f'{FACEBOOK_RTMP_INGEST}/{key}'

        return url

    def _sign_state(self, payload: dict[str, str]) -> str:
        import json

        return self._signer.sign(json.dumps(payload, sort_keys=True))

    def _unsign_state(self, state: str) -> dict[str, str]:
        import json

        try:
            raw = self._signer.unsign(state, max_age=self.OAUTH_STATE_MAX_AGE)
        except SignatureExpired as exc:
            raise OAuthStateError('OAuth state expired') from exc
        except BadSignature as exc:
            raise OAuthStateError('Invalid OAuth state') from exc

        payload = json.loads(raw)
        if 'tenant_id' not in payload:
            raise OAuthStateError('OAuth state missing tenant_id')
        return payload
