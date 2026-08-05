"""Studio media asset catalog for tenant graphics panels."""

from __future__ import annotations

import copy
import uuid
from typing import Any

from django.db.models import Q

from apps.persistence.asset_utils import (
    asset_catalog_bucket,
    default_label_for_asset,
    infer_media_format,
)
from apps.persistence.constants import DEFAULT_ASSET_CATALOG
from apps.persistence.exceptions import TenantNotFoundError
from apps.persistence.models import StudioMediaAsset, Tenant


class AssetCatalogService:
    def list_assets_for_tenant(self, tenant_id: uuid.UUID) -> list[StudioMediaAsset]:
        if not Tenant.objects.filter(id=tenant_id).exists():
            raise TenantNotFoundError(f'Tenant {tenant_id} not found')

        return list(
            StudioMediaAsset.objects.filter(
                Q(tenant_id=tenant_id) | Q(tenant__isnull=True),
                is_active=True,
            ).order_by('asset_type', 'sort_order', 'created_at')
        )

    def build_asset_catalog(self, tenant_id: uuid.UUID) -> dict[str, list[dict[str, Any]]]:
        catalog = copy.deepcopy(DEFAULT_ASSET_CATALOG)
        for asset in self.list_assets_for_tenant(tenant_id):
            bucket = asset_catalog_bucket(asset.asset_type, asset.media_format)
            if bucket not in catalog:
                continue
            catalog[bucket].append(self.serialize_asset(asset))
        return catalog

    def create_tenant_asset(
        self,
        tenant_id: uuid.UUID,
        *,
        asset_type: int,
        source: str,
        thumbnail: str = '',
        size: int = 0,
        media_format: str | None = None,
        label: str = '',
        meta_data: dict[str, Any] | None = None,
        sort_order: int = 0,
    ) -> StudioMediaAsset:
        try:
            tenant = Tenant.objects.get(id=tenant_id)
        except Tenant.DoesNotExist as exc:
            raise TenantNotFoundError(f'Tenant {tenant_id} not found') from exc

        resolved_format = media_format or infer_media_format(source, asset_type)
        resolved_label = label.strip() or default_label_for_asset(
            asset_type,
            str(uuid.uuid4()),
            source,
        )

        return StudioMediaAsset.objects.create(
            tenant=tenant,
            asset_type=asset_type,
            source=source,
            thumbnail=thumbnail or '',
            size=size,
            media_format=resolved_format,
            label=resolved_label,
            is_system_default=False,
            is_active=True,
            meta_data=meta_data or {},
            sort_order=sort_order,
        )

    @staticmethod
    def serialize_asset(asset: StudioMediaAsset) -> dict[str, Any]:
        return {
            'asset_id': str(asset.id),
            'tenant_id': str(asset.tenant_id) if asset.tenant_id else None,
            'asset_type': asset.asset_type,
            'source': asset.source,
            'thumbnail': asset.thumbnail or None,
            'size': asset.size,
            'media_format': asset.media_format,
            'label': asset.label or default_label_for_asset(
                asset.asset_type,
                str(asset.id),
                asset.source,
            ),
            'is_system_default': asset.is_system_default,
            'is_active': asset.is_active,
            'meta_data': asset.meta_data or {},
            'sort_order': asset.sort_order,
            'created_at': asset.created_at.isoformat(),
            'updated_at': asset.updated_at.isoformat(),
        }
