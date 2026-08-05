"""Tenant background music library for custom CMS-uploaded tracks."""

from __future__ import annotations

import uuid
from typing import Any

from django.db.models import Q

from apps.persistence.exceptions import TenantNotFoundError
from apps.persistence.models import Tenant, TenantMusicTrack


class MusicCatalogService:
    def list_tracks_for_tenant(self, tenant_id: uuid.UUID) -> list[TenantMusicTrack]:
        if not Tenant.objects.filter(id=tenant_id).exists():
            raise TenantNotFoundError(f'Tenant {tenant_id} not found')

        return list(
            TenantMusicTrack.objects.filter(
                Q(tenant_id=tenant_id) | Q(tenant__isnull=True),
                is_active=True,
            ).order_by('sort_order', 'created_at')
        )

    def build_music_catalog(self, tenant_id: uuid.UUID) -> list[dict[str, Any]]:
        return [self.serialize_track(track) for track in self.list_tracks_for_tenant(tenant_id)]

    def create_tenant_track(
        self,
        tenant_id: uuid.UUID,
        *,
        title: str,
        source: str,
        size: int = 0,
        meta_data: dict[str, Any] | None = None,
        sort_order: int = 0,
    ) -> TenantMusicTrack:
        try:
            tenant = Tenant.objects.get(id=tenant_id)
        except Tenant.DoesNotExist as exc:
            raise TenantNotFoundError(f'Tenant {tenant_id} not found') from exc

        resolved_title = title.strip() or 'Custom track'
        return TenantMusicTrack.objects.create(
            tenant=tenant,
            title=resolved_title,
            source=source,
            size=size,
            is_system_default=False,
            is_active=True,
            meta_data=meta_data or {},
            sort_order=sort_order,
        )

    @staticmethod
    def serialize_track(track: TenantMusicTrack) -> dict[str, Any]:
        return {
            'track_id': str(track.id),
            'tenant_id': str(track.tenant_id) if track.tenant_id else None,
            'title': track.title,
            'source': track.source,
            'size': track.size,
            'is_system_default': track.is_system_default,
            'is_active': track.is_active,
            'meta_data': track.meta_data or {},
            'sort_order': track.sort_order,
            'created_at': track.created_at.isoformat(),
            'updated_at': track.updated_at.isoformat(),
        }
