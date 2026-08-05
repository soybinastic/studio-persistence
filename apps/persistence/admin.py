from django.contrib import admin

from apps.persistence.models import (
    PlatformConnection,
    StudioMediaAsset,
    Tenant,
    TenantBannerMaterial,
    TenantConfiguration,
    TenantDestination,
    TenantMusicTrack,
    TenantScene,
    TenantTickerMaterial,
)


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'created_at', 'updated_at')
    search_fields = ('name', 'id')


@admin.register(TenantConfiguration)
class TenantConfigurationAdmin(admin.ModelAdmin):
    list_display = ('tenant', 'layout', 'active_scene', 'updated_at')


@admin.register(TenantScene)
class TenantSceneAdmin(admin.ModelAdmin):
    list_display = ('name', 'tenant', 'scene_type', 'sort_order', 'updated_at')
    list_filter = ('scene_type',)


@admin.register(TenantDestination)
class TenantDestinationAdmin(admin.ModelAdmin):
    list_display = ('label', 'tenant', 'platform', 'url', 'sort_order')


@admin.register(StudioMediaAsset)
class StudioMediaAssetAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'tenant',
        'asset_type',
        'media_format',
        'label',
        'is_system_default',
        'is_active',
        'sort_order',
    )
    list_filter = ('asset_type', 'media_format', 'is_system_default', 'is_active')
    search_fields = ('id', 'label', 'source')


@admin.register(TenantMusicTrack)
class TenantMusicTrackAdmin(admin.ModelAdmin):
    list_display = (
        'title',
        'tenant',
        'is_system_default',
        'is_active',
        'sort_order',
        'updated_at',
    )
    list_filter = ('is_system_default', 'is_active')
    search_fields = ('title', 'source', 'id')


@admin.register(TenantBannerMaterial)
class TenantBannerMaterialAdmin(admin.ModelAdmin):
    list_display = (
        'label',
        'title',
        'tenant',
        'theme',
        'is_system_default',
        'is_active',
        'sort_order',
    )
    list_filter = ('theme', 'is_system_default', 'is_active')
    search_fields = ('label', 'title', 'description')


@admin.register(TenantTickerMaterial)
class TenantTickerMaterialAdmin(admin.ModelAdmin):
    list_display = (
        'label',
        'tenant',
        'ticker_position',
        'ticker_direction',
        'is_system_default',
        'is_active',
        'sort_order',
    )
    list_filter = ('ticker_position', 'is_system_default', 'is_active')
    search_fields = ('label', 'ticker_text')


@admin.register(PlatformConnection)
class PlatformConnectionAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'tenant',
        'platform',
        'status',
        'platform_login',
        'updated_at',
    )
    list_filter = ('platform', 'status')
    search_fields = ('name', 'platform_login', 'platform_user_id')
    readonly_fields = (
        'access_token_encrypted',
        'refresh_token_encrypted',
        'stream_key_encrypted',
        'created_at',
        'updated_at',
    )
