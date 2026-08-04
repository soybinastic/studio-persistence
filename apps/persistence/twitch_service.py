"""Twitch OAuth and Helix API helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import requests
from django.conf import settings

TWITCH_AUTH_URL = 'https://id.twitch.tv/oauth2/authorize'
TWITCH_TOKEN_URL = 'https://id.twitch.tv/oauth2/token'
TWITCH_HELIX_BASE = 'https://api.twitch.tv/helix'
TWITCH_RTMP_INGEST = 'rtmp://live.twitch.tv/app'
DEFAULT_SCOPES = ('channel:read:stream_key', 'user:read:email', 'chat:read', 'user:write:chat')


class TwitchIntegrationError(Exception):
    pass


@dataclass(frozen=True)
class TwitchTokenResponse:
    access_token: str
    refresh_token: str
    expires_in: int
    scope: list[str]
    token_type: str


@dataclass(frozen=True)
class TwitchUser:
    id: str
    login: str
    display_name: str
    email: str


@dataclass(frozen=True)
class TwitchConnectionResult:
    user: TwitchUser
    tokens: TwitchTokenResponse
    stream_key: str
    rtmp_url: str


def _client_id() -> str:
    client_id = getattr(settings, 'TWITCH_CLIENT_ID', '')
    if not client_id:
        raise TwitchIntegrationError('TWITCH_CLIENT_ID is not configured')
    return client_id


def _client_secret() -> str:
    client_secret = getattr(settings, 'TWITCH_CLIENT_SECRET', '')
    if not client_secret:
        raise TwitchIntegrationError('TWITCH_CLIENT_SECRET is not configured')
    return client_secret


def _redirect_uri() -> str:
    redirect_uri = getattr(settings, 'TWITCH_REDIRECT_URI', '')
    if not redirect_uri:
        raise TwitchIntegrationError('TWITCH_REDIRECT_URI is not configured')
    return redirect_uri


def build_authorize_url(*, state: str) -> str:
    params = {
        'client_id': _client_id(),
        'redirect_uri': _redirect_uri(),
        'response_type': 'code',
        'scope': ' '.join(DEFAULT_SCOPES),
        'state': state,
    }
    return f'{TWITCH_AUTH_URL}?{urlencode(params)}'


def exchange_code_for_tokens(code: str) -> TwitchTokenResponse:
    response = requests.post(
        TWITCH_TOKEN_URL,
        data={
            'client_id': _client_id(),
            'client_secret': _client_secret(),
            'code': code,
            'grant_type': 'authorization_code',
            'redirect_uri': _redirect_uri(),
        },
        timeout=15,
    )
    if response.status_code >= 400:
        raise TwitchIntegrationError(
            f'Twitch token exchange failed: {response.text or response.reason}',
        )
    payload = response.json()
    return TwitchTokenResponse(
        access_token=payload['access_token'],
        refresh_token=payload.get('refresh_token', ''),
        expires_in=int(payload.get('expires_in', 0)),
        scope=str(payload.get('scope', '')).split(),
        token_type=payload.get('token_type', 'bearer'),
    )


def refresh_access_token(refresh_token: str) -> TwitchTokenResponse:
    response = requests.post(
        TWITCH_TOKEN_URL,
        data={
            'client_id': _client_id(),
            'client_secret': _client_secret(),
            'grant_type': 'refresh_token',
            'refresh_token': refresh_token,
        },
        timeout=15,
    )
    if response.status_code >= 400:
        raise TwitchIntegrationError(
            f'Twitch token refresh failed: {response.text or response.reason}',
        )
    payload = response.json()
    return TwitchTokenResponse(
        access_token=payload['access_token'],
        refresh_token=payload.get('refresh_token', refresh_token),
        expires_in=int(payload.get('expires_in', 0)),
        scope=str(payload.get('scope', '')).split(),
        token_type=payload.get('token_type', 'bearer'),
    )


def _helix_get(path: str, access_token: str) -> dict[str, Any]:
    response = requests.get(
        f'{TWITCH_HELIX_BASE}{path}',
        headers={
            'Authorization': f'Bearer {access_token}',
            'Client-Id': _client_id(),
        },
        timeout=15,
    )
    if response.status_code >= 400:
        raise TwitchIntegrationError(
            f'Twitch Helix request failed ({path}): {response.text or response.reason}',
        )
    return response.json()


def fetch_current_user(access_token: str) -> TwitchUser:
    payload = _helix_get('/users', access_token)
    data = payload.get('data') or []
    if not data:
        raise TwitchIntegrationError('Twitch user profile not found')
    user = data[0]
    return TwitchUser(
        id=str(user['id']),
        login=str(user.get('login') or ''),
        display_name=str(user.get('display_name') or user.get('login') or ''),
        email=str(user.get('email') or ''),
    )


def fetch_stream_key(access_token: str, broadcaster_id: str) -> str:
    payload = _helix_get(f'/streams/key?broadcaster_id={broadcaster_id}', access_token)
    data = payload.get('data') or []
    if not data or not data[0].get('stream_key'):
        raise TwitchIntegrationError('Twitch stream key not available')
    return str(data[0]['stream_key'])


def complete_oauth_connection(code: str) -> TwitchConnectionResult:
    tokens = exchange_code_for_tokens(code)
    user = fetch_current_user(tokens.access_token)
    stream_key = fetch_stream_key(tokens.access_token, user.id)
    return TwitchConnectionResult(
        user=user,
        tokens=tokens,
        stream_key=stream_key,
        rtmp_url=f'{TWITCH_RTMP_INGEST}/{stream_key}',
    )
