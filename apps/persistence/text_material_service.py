"""Banner and ticker material catalog for tenant graphics panels."""

from __future__ import annotations

import copy
import uuid
from typing import Any

from django.db.models import Q

from apps.persistence.constants import DEFAULT_TEXT_MATERIAL_CATALOG
from apps.persistence.exceptions import (
    BannerMaterialNotFoundError,
    TenantNotFoundError,
    TickerMaterialNotFoundError,
)
from apps.persistence.models import Tenant, TenantBannerMaterial, TenantTickerMaterial


class TextMaterialService:
    def list_banners_for_tenant(self, tenant_id: uuid.UUID) -> list[TenantBannerMaterial]:
        if not Tenant.objects.filter(id=tenant_id).exists():
            raise TenantNotFoundError(f'Tenant {tenant_id} not found')

        return list(
            TenantBannerMaterial.objects.filter(
                Q(tenant_id=tenant_id) | Q(tenant__isnull=True),
                is_active=True,
            ).order_by('sort_order', 'created_at')
        )

    def list_tickers_for_tenant(self, tenant_id: uuid.UUID) -> list[TenantTickerMaterial]:
        if not Tenant.objects.filter(id=tenant_id).exists():
            raise TenantNotFoundError(f'Tenant {tenant_id} not found')

        return list(
            TenantTickerMaterial.objects.filter(
                Q(tenant_id=tenant_id) | Q(tenant__isnull=True),
                is_active=True,
            ).order_by('sort_order', 'created_at')
        )

    def build_text_material_catalog(self, tenant_id: uuid.UUID) -> dict[str, list[dict[str, Any]]]:
        return {
            'banners': [
                self.serialize_banner_material(banner)
                for banner in self.list_banners_for_tenant(tenant_id)
            ],
            'tickers': [
                self.serialize_ticker_material(ticker)
                for ticker in self.list_tickers_for_tenant(tenant_id)
            ],
        }

    def get_banner_material(
        self,
        tenant_id: uuid.UUID,
        banner_id: uuid.UUID,
    ) -> TenantBannerMaterial:
        banner = TenantBannerMaterial.objects.filter(
            Q(tenant_id=tenant_id) | Q(tenant__isnull=True),
            id=banner_id,
        ).first()
        if banner is None:
            raise BannerMaterialNotFoundError(f'Banner material {banner_id} not found')
        return banner

    def get_ticker_material(
        self,
        tenant_id: uuid.UUID,
        ticker_id: uuid.UUID,
    ) -> TenantTickerMaterial:
        ticker = TenantTickerMaterial.objects.filter(
            Q(tenant_id=tenant_id) | Q(tenant__isnull=True),
            id=ticker_id,
        ).first()
        if ticker is None:
            raise TickerMaterialNotFoundError(f'Ticker material {ticker_id} not found')
        return ticker

    def create_banner_material(
        self,
        tenant_id: uuid.UUID,
        *,
        label: str = '',
        title: str,
        description: str = '',
        theme: str = 'classic',
        primary: str = '#111111',
        secondary: str = '#374151',
        accent: str = '#38bdf8',
        font_size: int = 32,
        is_display_names: bool = True,
    ) -> TenantBannerMaterial:
        tenant = Tenant.objects.filter(id=tenant_id).first()
        if tenant is None:
            raise TenantNotFoundError(f'Tenant {tenant_id} not found')

        sort_order = tenant.banner_materials.count()
        return TenantBannerMaterial.objects.create(
            tenant=tenant,
            label=label.strip() or title.strip() or 'Custom banner',
            title=title.strip(),
            description=description.strip(),
            theme=theme,
            primary=primary,
            secondary=secondary,
            accent=accent,
            font_size=font_size,
            is_display_names=is_display_names,
            is_system_default=False,
            is_active=True,
            sort_order=sort_order,
        )

    def create_ticker_material(
        self,
        tenant_id: uuid.UUID,
        *,
        label: str = '',
        ticker_text: str,
        ticker_position: str = 'bottom',
        ticker_direction: str = 'rtl',
        ticker_speed: float = 2.0,
        primary: str = '#111827',
        secondary: str = '#ffffff',
    ) -> TenantTickerMaterial:
        tenant = Tenant.objects.filter(id=tenant_id).first()
        if tenant is None:
            raise TenantNotFoundError(f'Tenant {tenant_id} not found')

        sort_order = tenant.ticker_materials.count()
        preview = ticker_text.strip()[:48]
        return TenantTickerMaterial.objects.create(
            tenant=tenant,
            label=label.strip() or preview or 'Custom ticker',
            ticker_text=ticker_text.strip(),
            ticker_position=ticker_position,
            ticker_direction=ticker_direction,
            ticker_speed=ticker_speed,
            primary=primary,
            secondary=secondary,
            is_system_default=False,
            is_active=True,
            sort_order=sort_order,
        )

    def update_banner_material(
        self,
        tenant_id: uuid.UUID,
        banner_id: uuid.UUID,
        **fields: Any,
    ) -> TenantBannerMaterial:
        banner = TenantBannerMaterial.objects.filter(tenant_id=tenant_id, id=banner_id).first()
        if banner is None:
            raise BannerMaterialNotFoundError(f'Banner material {banner_id} not found')

        update_fields = ['updated_at']
        for key, value in fields.items():
            if value is None or not hasattr(banner, key):
                continue
            setattr(banner, key, value)
            update_fields.append(key)

        banner.save(update_fields=update_fields)
        return banner

    def update_ticker_material(
        self,
        tenant_id: uuid.UUID,
        ticker_id: uuid.UUID,
        **fields: Any,
    ) -> TenantTickerMaterial:
        ticker = TenantTickerMaterial.objects.filter(tenant_id=tenant_id, id=ticker_id).first()
        if ticker is None:
            raise TickerMaterialNotFoundError(f'Ticker material {ticker_id} not found')

        update_fields = ['updated_at']
        for key, value in fields.items():
            if value is None or not hasattr(ticker, key):
                continue
            setattr(ticker, key, value)
            update_fields.append(key)

        ticker.save(update_fields=update_fields)
        return ticker

    def delete_banner_material(self, tenant_id: uuid.UUID, banner_id: uuid.UUID) -> None:
        deleted, _ = TenantBannerMaterial.objects.filter(
            tenant_id=tenant_id,
            id=banner_id,
        ).delete()
        if not deleted:
            raise BannerMaterialNotFoundError(f'Banner material {banner_id} not found')

    def delete_ticker_material(self, tenant_id: uuid.UUID, ticker_id: uuid.UUID) -> None:
        deleted, _ = TenantTickerMaterial.objects.filter(
            tenant_id=tenant_id,
            id=ticker_id,
        ).delete()
        if not deleted:
            raise TickerMaterialNotFoundError(f'Ticker material {ticker_id} not found')

    @staticmethod
    def serialize_banner_material(banner: TenantBannerMaterial) -> dict[str, Any]:
        return {
            'material_id': str(banner.id),
            'tenant_id': str(banner.tenant_id) if banner.tenant_id else None,
            'label': banner.label or banner.title or 'Banner',
            'is_system_default': banner.is_system_default,
            'is_active': banner.is_active,
            'sort_order': banner.sort_order,
            'banner': TextMaterialService.banner_graphic_from_material(banner),
            'created_at': banner.created_at.isoformat(),
            'updated_at': banner.updated_at.isoformat(),
        }

    @staticmethod
    def serialize_ticker_material(ticker: TenantTickerMaterial) -> dict[str, Any]:
        return {
            'material_id': str(ticker.id),
            'tenant_id': str(ticker.tenant_id) if ticker.tenant_id else None,
            'label': ticker.label or 'Ticker',
            'is_system_default': ticker.is_system_default,
            'is_active': ticker.is_active,
            'sort_order': ticker.sort_order,
            'ticker': TextMaterialService.ticker_graphic_from_material(ticker),
            'created_at': ticker.created_at.isoformat(),
            'updated_at': ticker.updated_at.isoformat(),
        }

    @staticmethod
    def banner_graphic_from_material(banner: TenantBannerMaterial) -> dict[str, Any]:
        return {
            'title': banner.title,
            'description': banner.description,
            'is_display': True,
            'is_display_names': banner.is_display_names,
            'theme': banner.theme,
            'primary': banner.primary,
            'secondary': banner.secondary,
            'accent': banner.accent,
            'font_size': banner.font_size,
        }

    @staticmethod
    def ticker_graphic_from_material(ticker: TenantTickerMaterial) -> dict[str, Any]:
        return {
            'tickerText': ticker.ticker_text,
            'tickerEnabled': True,
            'tickerPosition': ticker.ticker_position,
            'tickerDirection': ticker.ticker_direction,
            'tickerSpeed': ticker.ticker_speed,
            'primary': ticker.primary,
            'secondary': ticker.secondary,
        }

    @staticmethod
    def empty_catalog() -> dict[str, list[dict[str, Any]]]:
        return copy.deepcopy(DEFAULT_TEXT_MATERIAL_CATALOG)
