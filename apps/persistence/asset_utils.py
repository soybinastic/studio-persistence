"""Helpers for studio media asset catalog."""

from __future__ import annotations

from apps.persistence.constants import (
    ASSET_TYPE_BACKGROUND,
    ASSET_TYPE_GREEN_SCREEN,
    ASSET_TYPE_LOGO,
    ASSET_TYPE_OVERLAY,
    ASSET_TYPE_QR_CODE,
    MEDIA_FORMAT_IMAGE,
    MEDIA_FORMAT_VIDEO,
)


def infer_media_format(source: str, asset_type: int) -> str:
    lowered = source.lower()
    if lowered.endswith(('.mp4', '.webm', '.mov', '.m4v')):
        return MEDIA_FORMAT_VIDEO
    if '/abg/' in lowered:
        return MEDIA_FORMAT_VIDEO
    return MEDIA_FORMAT_IMAGE


def asset_catalog_bucket(asset_type: int, media_format: str) -> str:
    if asset_type == ASSET_TYPE_LOGO:
        return 'logos'
    if asset_type == ASSET_TYPE_OVERLAY:
        return 'overlays'
    if asset_type == ASSET_TYPE_BACKGROUND:
        if media_format == MEDIA_FORMAT_VIDEO:
            return 'background_videos'
        return 'backgrounds'
    if asset_type == ASSET_TYPE_GREEN_SCREEN:
        return 'green_screens'
    if asset_type == ASSET_TYPE_QR_CODE:
        return 'qr_codes'
    return 'other'


def default_label_for_asset(asset_type: int, asset_id: str, source: str) -> str:
    if asset_type == ASSET_TYPE_LOGO:
        return 'Logo'
    if asset_type == ASSET_TYPE_OVERLAY:
        return 'Overlay'
    if asset_type == ASSET_TYPE_BACKGROUND:
        if source.lower().endswith('.mp4') or '/abg/' in source.lower():
            return 'Video background'
        return 'Background'
    if asset_type == ASSET_TYPE_GREEN_SCREEN:
        return 'Green screen'
    if asset_type == ASSET_TYPE_QR_CODE:
        return 'QR code'
    return asset_id[:8]
