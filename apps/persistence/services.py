"""Tenant bootstrap and configuration persistence."""

from __future__ import annotations

import copy
import uuid
from typing import Any

from django.db import transaction

from apps.persistence.constants import (
    DEFAULT_BACKGROUND_MUSIC_CONFIG,
    DEFAULT_DEVICES_CONFIG,
    DEFAULT_GRAPHICS_CONFIG,
    DEFAULT_SOURCES_CONFIG,
    DEFAULT_TILE_ORDER_CONFIG,
)
from apps.persistence.exceptions import (
    ActiveSceneDeleteError,
    DestinationNotFoundError,
    InvalidCountdownTargetError,
    SceneNotFoundError,
    TenantNotFoundError,
)
from apps.persistence.models import (
    SceneType,
    Tenant,
    TenantConfiguration,
    TenantDestination,
    TenantScene,
)


def _empty_configuration() -> dict[str, Any]:
    return {
        'layout': 'CONTAIN',
        'tile_order_config': copy.deepcopy(DEFAULT_TILE_ORDER_CONFIG),
        'active_scene_id': None,
        'devices': copy.deepcopy(DEFAULT_DEVICES_CONFIG),
        'graphics_config': copy.deepcopy(DEFAULT_GRAPHICS_CONFIG),
        'scenes': [],
        'destinations': [],
    }


def _merge_background_music_config(
    current: dict[str, Any] | None,
    partial: dict[str, Any],
) -> dict[str, Any]:
    merged = copy.deepcopy(current or DEFAULT_BACKGROUND_MUSIC_CONFIG)
    merged.update(partial)
    return merged


def _merge_devices_config(
    current: dict[str, Any] | None,
    partial: dict[str, Any],
) -> dict[str, Any]:
    merged = copy.deepcopy(current or DEFAULT_DEVICES_CONFIG)
    merged.update(partial)
    return merged


def _merge_sources_config(
    current: dict[str, Any] | None,
    partial: dict[str, Any],
) -> dict[str, Any]:
    merged = copy.deepcopy(current or DEFAULT_SOURCES_CONFIG)
    if 'assignments' in partial:
        assignments = dict(merged.get('assignments') or {})
        assignments.update(partial['assignments'])
        merged['assignments'] = assignments
    for key, value in partial.items():
        if key == 'assignments':
            continue
        merged[key] = value
    return merged


class TenantService:
    def get_or_create_tenant(
        self,
        tenant_id: uuid.UUID,
        tenant_name: str,
    ) -> tuple[Tenant, bool]:
        tenant = Tenant.objects.filter(id=tenant_id).first()
        if tenant is not None:
            if tenant.name != tenant_name:
                tenant.name = tenant_name
                tenant.save(update_fields=['name', 'updated_at'])
            return tenant, False

        with transaction.atomic():
            tenant = Tenant.objects.create(id=tenant_id, name=tenant_name)
            TenantConfiguration.objects.create(tenant=tenant)
        return tenant, True

    def get_tenant(self, tenant_id: uuid.UUID) -> Tenant:
        tenant = (
            Tenant.objects.select_related('configuration', 'configuration__active_scene')
            .filter(id=tenant_id)
            .first()
        )
        if tenant is None:
            raise TenantNotFoundError(f'Tenant {tenant_id} not found')
        return tenant

    def build_configuration_payload(self, tenant: Tenant) -> dict[str, Any]:
        config = getattr(tenant, 'configuration', None)
        if config is None:
            return _empty_configuration()

        scenes = tenant.scenes.select_related('countdown_target_scene').order_by(
            'sort_order',
            'created_at',
        )
        destinations = tenant.destinations.order_by('sort_order', 'created_at')

        return {
            'layout': config.layout,
            'tile_order_config': config.tile_order_config or dict(DEFAULT_TILE_ORDER_CONFIG),
            'active_scene_id': (
                str(config.active_scene_id) if config.active_scene_id else None
            ),
            'devices': config.devices_config or dict(DEFAULT_DEVICES_CONFIG),
            'graphics_config': config.graphics_config or dict(DEFAULT_GRAPHICS_CONFIG),
            'scenes': [self._serialize_scene(scene, config.active_scene_id) for scene in scenes],
            'destinations': [
                self._serialize_destination(destination) for destination in destinations
            ],
        }

    def update_configuration(
        self,
        tenant_id: uuid.UUID,
        *,
        layout: str | None = None,
        tile_order_config: dict[str, Any] | None = None,
        devices: dict[str, Any] | None = None,
        graphics_config: dict[str, Any] | None = None,
        active_scene_id: uuid.UUID | None = ...,  # noqa: E704
    ) -> TenantConfiguration:
        tenant = self.get_tenant(tenant_id)
        config = tenant.configuration

        update_fields = ['updated_at']
        if layout is not None:
            config.layout = layout
            update_fields.append('layout')
        if tile_order_config is not None:
            config.tile_order_config = tile_order_config
            update_fields.append('tile_order_config')
        if devices is not None:
            config.devices_config = _merge_devices_config(config.devices_config, devices)
            update_fields.append('devices_config')
        if graphics_config is not None:
            merged = copy.deepcopy(config.graphics_config or DEFAULT_GRAPHICS_CONFIG)
            for key, value in graphics_config.items():
                merged[key] = copy.deepcopy(value)
            config.graphics_config = merged
            update_fields.append('graphics_config')
        if active_scene_id is not ...:
            if active_scene_id is None:
                config.active_scene = None
            else:
                scene = tenant.scenes.filter(id=active_scene_id).first()
                if scene is None:
                    raise SceneNotFoundError(f'Scene {active_scene_id} not found')
                config.active_scene = scene
            update_fields.append('active_scene')

        config.save(update_fields=update_fields)
        return config

    def list_scenes(self, tenant_id: uuid.UUID) -> list[TenantScene]:
        tenant = self.get_tenant(tenant_id)
        return list(
            tenant.scenes.select_related('countdown_target_scene').order_by(
                'sort_order',
                'created_at',
            )
        )

    def get_scene(self, tenant_id: uuid.UUID, scene_id: uuid.UUID) -> TenantScene:
        scene = (
            TenantScene.objects.select_related('countdown_target_scene', 'tenant__configuration')
            .filter(tenant_id=tenant_id, id=scene_id)
            .first()
        )
        if scene is None:
            raise SceneNotFoundError(f'Scene {scene_id} not found')
        return scene

    def create_scene(
        self,
        tenant_id: uuid.UUID,
        *,
        scene_type: str,
        name: str | None = None,
        devices: dict[str, Any] | None = None,
        layout: str | None = None,
        graphics_config: dict[str, Any] | None = None,
        duration_seconds: int | None = None,
        target_scene_id: uuid.UUID | None = None,
    ) -> TenantScene:
        tenant = self.get_tenant(tenant_id)

        if scene_type == SceneType.COUNTDOWN:
            if not duration_seconds or not target_scene_id:
                raise InvalidCountdownTargetError(
                    'Countdown scenes require duration_seconds and target_scene_id.'
                )
            target_scene = tenant.scenes.filter(
                id=target_scene_id,
                scene_type=SceneType.CAMERA,
            ).first()
            if target_scene is None:
                raise InvalidCountdownTargetError(
                    'Countdown target must reference an existing camera scene.'
                )

            sort_order = tenant.scenes.count()
            scene = TenantScene.objects.create(
                tenant=tenant,
                name=name or f'Countdown {sort_order + 1}',
                scene_type=SceneType.COUNTDOWN,
                sort_order=sort_order,
                countdown_duration_seconds=duration_seconds,
                countdown_target_scene=target_scene,
            )
            return scene

        sort_order = tenant.scenes.count()
        scene = TenantScene.objects.create(
            tenant=tenant,
            name=name or f'Scene {sort_order + 1}',
            scene_type=SceneType.CAMERA,
            sort_order=sort_order,
            layout=layout or tenant.configuration.layout,
            graphics_config=graphics_config or copy.deepcopy(DEFAULT_GRAPHICS_CONFIG),
            devices_config=_merge_devices_config(None, devices or {}),
        )

        config = tenant.configuration
        if config.active_scene_id is None:
            config.active_scene = scene
            config.save(update_fields=['active_scene', 'updated_at'])

        return scene

    def update_scene(
        self,
        tenant_id: uuid.UUID,
        scene_id: uuid.UUID,
        *,
        name: str | None = None,
        layout: str | None = None,
        graphics_config: dict[str, Any] | None = None,
        devices: dict[str, Any] | None = None,
        sources: dict[str, Any] | None = None,
        background_music: dict[str, Any] | None = None,
        sort_order: int | None = None,
    ) -> TenantScene:
        scene = self.get_scene(tenant_id, scene_id)

        update_fields = ['updated_at']
        if name is not None:
            scene.name = name
            update_fields.append('name')
        if layout is not None and scene.scene_type == SceneType.CAMERA:
            scene.layout = layout
            update_fields.append('layout')
        if graphics_config is not None and scene.scene_type == SceneType.CAMERA:
            merged = copy.deepcopy(scene.graphics_config or DEFAULT_GRAPHICS_CONFIG)
            for key, value in graphics_config.items():
                merged[key] = copy.deepcopy(value)
            scene.graphics_config = merged
            update_fields.append('graphics_config')
        if devices is not None and scene.scene_type == SceneType.CAMERA:
            scene.devices_config = _merge_devices_config(scene.devices_config, devices)
            update_fields.append('devices_config')
        if sources is not None and scene.scene_type == SceneType.CAMERA:
            scene.sources_config = _merge_sources_config(scene.sources_config, sources)
            update_fields.append('sources_config')
        if background_music is not None and scene.scene_type == SceneType.CAMERA:
            scene.background_music_config = _merge_background_music_config(
                scene.background_music_config,
                background_music,
            )
            update_fields.append('background_music_config')
        if sort_order is not None:
            scene.sort_order = sort_order
            update_fields.append('sort_order')

        scene.save(update_fields=update_fields)
        return scene

    def delete_scene(self, tenant_id: uuid.UUID, scene_id: uuid.UUID) -> None:
        tenant = self.get_tenant(tenant_id)
        scene = self.get_scene(tenant_id, scene_id)
        config = tenant.configuration

        if config.active_scene_id == scene.id:
            raise ActiveSceneDeleteError('Cannot delete the active scene.')

        if scene.scene_type == SceneType.CAMERA:
            referenced = TenantScene.objects.filter(
                tenant_id=tenant_id,
                countdown_target_scene_id=scene.id,
            ).exists()
            if referenced:
                raise InvalidCountdownTargetError(
                    'Cannot delete a camera scene referenced by a countdown scene.'
                )

        scene.delete()

    def list_destinations(self, tenant_id: uuid.UUID) -> list[TenantDestination]:
        tenant = self.get_tenant(tenant_id)
        return list(tenant.destinations.order_by('sort_order', 'created_at'))

    def create_destination(
        self,
        tenant_id: uuid.UUID,
        *,
        url: str,
        label: str = '',
        platform: str = '',
    ) -> TenantDestination:
        tenant = self.get_tenant(tenant_id)
        sort_order = tenant.destinations.count()
        return TenantDestination.objects.create(
            tenant=tenant,
            url=url,
            label=label,
            platform=platform,
            sort_order=sort_order,
        )

    def update_destination(
        self,
        tenant_id: uuid.UUID,
        destination_id: uuid.UUID,
        *,
        url: str | None = None,
        label: str | None = None,
        platform: str | None = None,
        sort_order: int | None = None,
    ) -> TenantDestination:
        destination = TenantDestination.objects.filter(
            tenant_id=tenant_id,
            id=destination_id,
        ).first()
        if destination is None:
            raise DestinationNotFoundError(f'Destination {destination_id} not found')

        update_fields = ['updated_at']
        if url is not None:
            destination.url = url
            update_fields.append('url')
        if label is not None:
            destination.label = label
            update_fields.append('label')
        if platform is not None:
            destination.platform = platform
            update_fields.append('platform')
        if sort_order is not None:
            destination.sort_order = sort_order
            update_fields.append('sort_order')

        destination.save(update_fields=update_fields)
        return destination

    def delete_destination(self, tenant_id: uuid.UUID, destination_id: uuid.UUID) -> None:
        deleted, _ = TenantDestination.objects.filter(
            tenant_id=tenant_id,
            id=destination_id,
        ).delete()
        if not deleted:
            raise DestinationNotFoundError(f'Destination {destination_id} not found')

    def _serialize_scene(
        self,
        scene: TenantScene,
        active_scene_id: uuid.UUID | None,
    ) -> dict[str, Any]:
        return {
            'scene_id': str(scene.id),
            'tenant_id': str(scene.tenant_id),
            'name': scene.name,
            'type': scene.scene_type,
            'sort_order': scene.sort_order,
            'layout': scene.layout,
            'graphics_config': scene.graphics_config or dict(DEFAULT_GRAPHICS_CONFIG),
            'devices': scene.devices_config or dict(DEFAULT_DEVICES_CONFIG),
            'sources': scene.sources_config or dict(DEFAULT_SOURCES_CONFIG),
            'background_music': scene.background_music_config or dict(
                DEFAULT_BACKGROUND_MUSIC_CONFIG
            ),
            'countdown': (
                {
                    'duration_seconds': scene.countdown_duration_seconds,
                    'target_scene_id': (
                        str(scene.countdown_target_scene_id)
                        if scene.countdown_target_scene_id
                        else None
                    ),
                }
                if scene.scene_type == SceneType.COUNTDOWN
                else None
            ),
            'is_active': str(scene.id) == str(active_scene_id) if active_scene_id else False,
            'created_at': scene.created_at.isoformat(),
            'updated_at': scene.updated_at.isoformat(),
        }

    @staticmethod
    def _serialize_destination(destination: TenantDestination) -> dict[str, Any]:
        return {
            'destination_id': str(destination.id),
            'tenant_id': str(destination.tenant_id),
            'label': destination.label,
            'url': destination.url,
            'platform': destination.platform,
            'sort_order': destination.sort_order,
            'created_at': destination.created_at.isoformat(),
            'updated_at': destination.updated_at.isoformat(),
        }
