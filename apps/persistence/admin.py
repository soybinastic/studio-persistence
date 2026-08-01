from django.contrib import admin

from apps.persistence.models import (
    Tenant,
    TenantConfiguration,
    TenantDestination,
    TenantScene,
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
