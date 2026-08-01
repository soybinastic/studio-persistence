from rest_framework import serializers

from apps.persistence.constants import (
    DEFAULT_BACKGROUND_MUSIC_CONFIG,
    DEFAULT_DEVICES_CONFIG,
    DEFAULT_SOURCES_CONFIG,
)
from apps.persistence.models import (
    LayoutType,
    SceneType,
    TenantBannerMaterial,
    TenantDestination,
    TenantScene,
    TenantTickerMaterial,
)


class TenantBootstrapSerializer(serializers.Serializer):
    tenant_id = serializers.UUIDField()
    tenant_name = serializers.CharField(max_length=255, trim_whitespace=True)


class DevicesConfigSerializer(serializers.Serializer):
    cameraId = serializers.CharField(required=False, allow_null=True, default=None)
    microphoneId = serializers.CharField(required=False, allow_null=True, default=None)
    speakerId = serializers.CharField(required=False, allow_null=True, default=None)


class SourcesConfigSerializer(serializers.Serializer):
    version = serializers.IntegerField(required=False, default=1)
    sources = serializers.ListField(required=False, default=list)
    assignments = serializers.DictField(
        child=serializers.CharField(),
        required=False,
        default=dict,
    )


class UpdateConfigurationSerializer(serializers.Serializer):
    layout = serializers.ChoiceField(choices=LayoutType.choices, required=False)
    tile_order_config = serializers.JSONField(required=False)
    devices = DevicesConfigSerializer(required=False)
    graphics_config = serializers.JSONField(required=False)
    active_scene_id = serializers.UUIDField(required=False, allow_null=True)


class CreateCameraSceneSerializer(serializers.Serializer):
    type = serializers.ChoiceField(choices=[SceneType.CAMERA])
    name = serializers.CharField(max_length=120, required=False, trim_whitespace=True)
    devices = DevicesConfigSerializer(required=False)
    layout = serializers.ChoiceField(choices=LayoutType.choices, required=False)
    graphics_config = serializers.JSONField(required=False)


class CreateCountdownSceneSerializer(serializers.Serializer):
    type = serializers.ChoiceField(choices=[SceneType.COUNTDOWN])
    name = serializers.CharField(max_length=120, required=False, trim_whitespace=True)
    duration_seconds = serializers.IntegerField(min_value=1, max_value=3600)
    target_scene_id = serializers.UUIDField()


class CreateSceneSerializer(serializers.Serializer):
    type = serializers.ChoiceField(choices=SceneType.choices)
    name = serializers.CharField(max_length=120, required=False, trim_whitespace=True)
    devices = DevicesConfigSerializer(required=False)
    layout = serializers.ChoiceField(choices=LayoutType.choices, required=False)
    graphics_config = serializers.JSONField(required=False)
    duration_seconds = serializers.IntegerField(min_value=1, max_value=3600, required=False)
    target_scene_id = serializers.UUIDField(required=False)

    def validate(self, attrs):
        scene_type = attrs['type']
        if scene_type == SceneType.COUNTDOWN:
            if not attrs.get('duration_seconds'):
                raise serializers.ValidationError(
                    {'duration_seconds': 'Required for countdown scenes.'}
                )
            if not attrs.get('target_scene_id'):
                raise serializers.ValidationError(
                    {'target_scene_id': 'Required for countdown scenes.'}
                )
        return attrs


class UpdateSceneSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=120, trim_whitespace=True, required=False)
    layout = serializers.ChoiceField(choices=LayoutType.choices, required=False)
    graphics_config = serializers.JSONField(required=False)
    devices = DevicesConfigSerializer(required=False)
    sources = SourcesConfigSerializer(required=False)
    background_music = serializers.JSONField(required=False)
    sort_order = serializers.IntegerField(min_value=0, required=False)


class SceneSerializer(serializers.ModelSerializer):
    scene_id = serializers.UUIDField(source='id', read_only=True)
    tenant_id = serializers.UUIDField(read_only=True)
    type = serializers.CharField(source='scene_type', read_only=True)
    devices = serializers.SerializerMethodField()
    sources = serializers.SerializerMethodField()
    background_music = serializers.SerializerMethodField()
    countdown = serializers.SerializerMethodField()
    is_active = serializers.SerializerMethodField()

    class Meta:
        model = TenantScene
        fields = [
            'scene_id',
            'tenant_id',
            'name',
            'type',
            'sort_order',
            'layout',
            'graphics_config',
            'devices',
            'sources',
            'background_music',
            'countdown',
            'is_active',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields

    def get_devices(self, obj: TenantScene) -> dict:
        return obj.devices_config or dict(DEFAULT_DEVICES_CONFIG)

    def get_sources(self, obj: TenantScene) -> dict:
        return obj.sources_config or dict(DEFAULT_SOURCES_CONFIG)

    def get_background_music(self, obj: TenantScene) -> dict:
        return obj.background_music_config or dict(DEFAULT_BACKGROUND_MUSIC_CONFIG)

    def get_countdown(self, obj: TenantScene) -> dict | None:
        if obj.scene_type != SceneType.COUNTDOWN:
            return None
        return {
            'duration_seconds': obj.countdown_duration_seconds,
            'target_scene_id': (
                str(obj.countdown_target_scene_id)
                if obj.countdown_target_scene_id
                else None
            ),
        }

    def get_is_active(self, obj: TenantScene) -> bool:
        active_scene_id = self.context.get('active_scene_id')
        if active_scene_id is None:
            return False
        return str(obj.id) == str(active_scene_id)


class CreateDestinationSerializer(serializers.Serializer):
    url = serializers.CharField(max_length=2048)
    label = serializers.CharField(max_length=120, required=False, allow_blank=True, default='')
    platform = serializers.CharField(max_length=64, required=False, allow_blank=True, default='')


class UpdateDestinationSerializer(serializers.Serializer):
    url = serializers.CharField(max_length=2048, required=False)
    label = serializers.CharField(max_length=120, required=False, allow_blank=True)
    platform = serializers.CharField(max_length=64, required=False, allow_blank=True)
    sort_order = serializers.IntegerField(min_value=0, required=False)


class DestinationSerializer(serializers.ModelSerializer):
    destination_id = serializers.UUIDField(source='id', read_only=True)
    tenant_id = serializers.UUIDField(read_only=True)

    class Meta:
        model = TenantDestination
        fields = [
            'destination_id',
            'tenant_id',
            'label',
            'url',
            'platform',
            'sort_order',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields


class CreateBannerMaterialSerializer(serializers.Serializer):
    label = serializers.CharField(max_length=255, required=False, allow_blank=True, default='')
    title = serializers.CharField(max_length=255, trim_whitespace=True)
    description = serializers.CharField(max_length=512, required=False, allow_blank=True, default='')
    theme = serializers.CharField(max_length=32, required=False, default='classic')
    primary = serializers.CharField(max_length=32, required=False, default='#111111')
    secondary = serializers.CharField(max_length=32, required=False, default='#374151')
    accent = serializers.CharField(max_length=32, required=False, default='#38bdf8')
    font_size = serializers.IntegerField(min_value=8, max_value=200, required=False, default=32)
    is_display_names = serializers.BooleanField(required=False, default=True)

    def validate(self, attrs):
        if not attrs.get('title', '').strip() and not attrs.get('description', '').strip():
            raise serializers.ValidationError(
                'Banner requires at least a title or description.',
            )
        return attrs


class UpdateBannerMaterialSerializer(serializers.Serializer):
    label = serializers.CharField(max_length=255, required=False, allow_blank=True)
    title = serializers.CharField(max_length=255, required=False, trim_whitespace=True)
    description = serializers.CharField(max_length=512, required=False, allow_blank=True)
    theme = serializers.CharField(max_length=32, required=False)
    primary = serializers.CharField(max_length=32, required=False)
    secondary = serializers.CharField(max_length=32, required=False)
    accent = serializers.CharField(max_length=32, required=False)
    font_size = serializers.IntegerField(min_value=8, max_value=200, required=False)
    is_display_names = serializers.BooleanField(required=False)
    is_active = serializers.BooleanField(required=False)
    sort_order = serializers.IntegerField(min_value=0, required=False)


class BannerMaterialSerializer(serializers.ModelSerializer):
    material_id = serializers.UUIDField(source='id', read_only=True)
    tenant_id = serializers.UUIDField(read_only=True)
    banner = serializers.SerializerMethodField()

    class Meta:
        model = TenantBannerMaterial
        fields = [
            'material_id',
            'tenant_id',
            'label',
            'is_system_default',
            'is_active',
            'sort_order',
            'banner',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields

    def get_banner(self, obj: TenantBannerMaterial) -> dict:
        from apps.persistence.text_material_service import TextMaterialService

        return TextMaterialService.banner_graphic_from_material(obj)


class CreateTickerMaterialSerializer(serializers.Serializer):
    label = serializers.CharField(max_length=255, required=False, allow_blank=True, default='')
    ticker_text = serializers.CharField(trim_whitespace=True)
    ticker_position = serializers.ChoiceField(
        choices=('top', 'bottom'),
        required=False,
        default='bottom',
    )
    ticker_direction = serializers.ChoiceField(
        choices=('rtl', 'ltr'),
        required=False,
        default='rtl',
    )
    ticker_speed = serializers.FloatField(min_value=0.1, required=False, default=2.0)
    primary = serializers.CharField(max_length=32, required=False, default='#111827')
    secondary = serializers.CharField(max_length=32, required=False, default='#ffffff')


class UpdateTickerMaterialSerializer(serializers.Serializer):
    label = serializers.CharField(max_length=255, required=False, allow_blank=True)
    ticker_text = serializers.CharField(required=False, trim_whitespace=True)
    ticker_position = serializers.ChoiceField(choices=('top', 'bottom'), required=False)
    ticker_direction = serializers.ChoiceField(choices=('rtl', 'ltr'), required=False)
    ticker_speed = serializers.FloatField(min_value=0.1, required=False)
    primary = serializers.CharField(max_length=32, required=False)
    secondary = serializers.CharField(max_length=32, required=False)
    is_active = serializers.BooleanField(required=False)
    sort_order = serializers.IntegerField(min_value=0, required=False)


class TickerMaterialSerializer(serializers.ModelSerializer):
    material_id = serializers.UUIDField(source='id', read_only=True)
    tenant_id = serializers.UUIDField(read_only=True)
    ticker = serializers.SerializerMethodField()

    class Meta:
        model = TenantTickerMaterial
        fields = [
            'material_id',
            'tenant_id',
            'label',
            'is_system_default',
            'is_active',
            'sort_order',
            'ticker',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields

    def get_ticker(self, obj: TenantTickerMaterial) -> dict:
        from apps.persistence.text_material_service import TextMaterialService

        return TextMaterialService.ticker_graphic_from_material(obj)
