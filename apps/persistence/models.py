import uuid

from django.db import models

from apps.persistence.constants import (
    DEFAULT_BACKGROUND_MUSIC_CONFIG,
    DEFAULT_DEVICES_CONFIG,
    DEFAULT_LAYOUT,
    DEFAULT_SOURCES_CONFIG,
    DEFAULT_TILE_ORDER_CONFIG,
)


class LayoutType(models.TextChoices):
    CONTAIN = 'CONTAIN', 'Contain'
    COVER = 'COVER', 'Cover'
    THUMBNAIL = 'THUMBNAIL', 'Thumbnail'
    GRID = 'GRID', 'Grid'
    SIDE_BY_SIDE = 'SIDE_BY_SIDE', 'Side by side'
    HALFSCREEN = 'HALFSCREEN', 'Half screen'
    SPOTLIGHT = 'SPOTLIGHT', 'Spotlight'
    CINEMA = 'CINEMA', 'Cinema'
    PICTURE_IN_PICTURE = 'PICTURE_IN_PICTURE', 'Picture in picture'
    OVERLAY = 'OVERLAY', 'Overlay'
    FULLSCREEN = 'FULLSCREEN', 'Fullscreen'


class SceneType(models.TextChoices):
    CAMERA = 'CAMERA', 'Camera'
    COUNTDOWN = 'COUNTDOWN', 'Countdown'


class Tenant(models.Model):
    """Studio owner account. The client supplies tenant_id on first load."""

    id = models.UUIDField(primary_key=True, editable=False)
    name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'tenants'
        ordering = ['name']

    def __str__(self) -> str:
        return f'{self.name} ({self.id})'


class TenantConfiguration(models.Model):
    """Session-level studio defaults persisted for a tenant."""

    tenant = models.OneToOneField(
        Tenant,
        on_delete=models.CASCADE,
        related_name='configuration',
        primary_key=True,
    )
    layout = models.CharField(
        max_length=32,
        choices=LayoutType.choices,
        default=DEFAULT_LAYOUT,
    )
    tile_order_config = models.JSONField(default=dict, blank=True)
    devices_config = models.JSONField(default=dict, blank=True)
    graphics_config = models.JSONField(default=dict, blank=True)
    active_scene = models.ForeignKey(
        'TenantScene',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'tenant_configurations'

    def save(self, *args, **kwargs):
        if not self.tile_order_config:
            self.tile_order_config = dict(DEFAULT_TILE_ORDER_CONFIG)
        if not self.devices_config:
            self.devices_config = dict(DEFAULT_DEVICES_CONFIG)
        super().save(*args, **kwargs)


class TenantScene(models.Model):
    """A saved scene template belonging to a tenant."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name='scenes',
    )
    name = models.CharField(max_length=120)
    scene_type = models.CharField(max_length=16, choices=SceneType.choices)
    sort_order = models.IntegerField(default=0)

    layout = models.CharField(
        max_length=32,
        choices=LayoutType.choices,
        blank=True,
        default='',
    )
    graphics_config = models.JSONField(default=dict, blank=True)
    devices_config = models.JSONField(default=dict, blank=True)
    sources_config = models.JSONField(default=dict, blank=True)
    background_music_config = models.JSONField(default=dict, blank=True)

    countdown_duration_seconds = models.PositiveIntegerField(null=True, blank=True)
    countdown_target_scene = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='countdown_references',
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'tenant_scenes'
        ordering = ['sort_order', 'created_at']

    def save(self, *args, **kwargs):
        if not self.devices_config:
            self.devices_config = dict(DEFAULT_DEVICES_CONFIG)
        if not self.sources_config:
            self.sources_config = dict(DEFAULT_SOURCES_CONFIG)
        if not self.background_music_config:
            self.background_music_config = dict(DEFAULT_BACKGROUND_MUSIC_CONFIG)
        super().save(*args, **kwargs)


class TenantDestination(models.Model):
    """Saved RTMP/HLS destination URLs for a tenant."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name='destinations',
    )
    label = models.CharField(max_length=120, blank=True, default='')
    url = models.CharField(max_length=2048)
    platform = models.CharField(max_length=64, blank=True, default='')
    sort_order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'tenant_destinations'
        ordering = ['sort_order', 'created_at']


class StudioMediaAsset(models.Model):
    """
    Studio graphics material (background, overlay, logo, QR, green screen).

    tenant=NULL rows are system defaults available to every tenant.
    tenant=<uuid> rows are tenant-owned uploads or custom materials.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        Tenant,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='media_assets',
    )
    asset_type = models.PositiveSmallIntegerField()
    source = models.CharField(max_length=2048)
    thumbnail = models.CharField(max_length=2048, blank=True, default='')
    size = models.BigIntegerField(default=0)
    media_format = models.CharField(max_length=16, default='image')
    label = models.CharField(max_length=255, blank=True, default='')
    is_system_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    meta_data = models.JSONField(default=dict, blank=True)
    sort_order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'studio_media_assets'
        ordering = ['asset_type', 'sort_order', 'created_at']
        indexes = [
            models.Index(fields=['tenant', 'asset_type']),
            models.Index(fields=['asset_type', 'is_system_default']),
        ]

    def __str__(self) -> str:
        scope = 'system' if self.tenant_id is None else str(self.tenant_id)
        return f'{scope}:{self.asset_type}:{self.id}'


class TenantBannerMaterial(models.Model):
    """
    Saved banner lower-third template for a tenant graphics panel.

    tenant=NULL rows are system defaults available to every tenant.
    tenant=<uuid> rows are tenant-created banner materials.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        Tenant,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='banner_materials',
    )
    label = models.CharField(max_length=255, blank=True, default='')
    title = models.CharField(max_length=255, blank=True, default='')
    description = models.CharField(max_length=512, blank=True, default='')
    theme = models.CharField(max_length=32, default='classic')
    primary = models.CharField(max_length=32, default='#111111')
    secondary = models.CharField(max_length=32, default='#374151')
    accent = models.CharField(max_length=32, default='#38bdf8')
    font_size = models.PositiveSmallIntegerField(default=32)
    is_display_names = models.BooleanField(default=True)
    is_system_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    sort_order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'tenant_banner_materials'
        ordering = ['sort_order', 'created_at']
        indexes = [
            models.Index(fields=['tenant', 'is_active']),
            models.Index(fields=['is_system_default']),
        ]

    def __str__(self) -> str:
        scope = 'system' if self.tenant_id is None else str(self.tenant_id)
        return f'{scope}:banner:{self.label or self.title or self.id}'


class TenantTickerMaterial(models.Model):
    """
    Saved scrolling ticker template for a tenant graphics panel.

    tenant=NULL rows are system defaults available to every tenant.
    tenant=<uuid> rows are tenant-created ticker materials.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        Tenant,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='ticker_materials',
    )
    label = models.CharField(max_length=255, blank=True, default='')
    ticker_text = models.TextField(blank=True, default='')
    ticker_position = models.CharField(max_length=16, default='bottom')
    ticker_direction = models.CharField(max_length=8, default='rtl')
    ticker_speed = models.FloatField(default=2.0)
    primary = models.CharField(max_length=32, default='#111827')
    secondary = models.CharField(max_length=32, default='#ffffff')
    is_system_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    sort_order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'tenant_ticker_materials'
        ordering = ['sort_order', 'created_at']
        indexes = [
            models.Index(fields=['tenant', 'is_active']),
            models.Index(fields=['is_system_default']),
        ]

    def __str__(self) -> str:
        scope = 'system' if self.tenant_id is None else str(self.tenant_id)
        return f'{scope}:ticker:{self.label or self.id}'
