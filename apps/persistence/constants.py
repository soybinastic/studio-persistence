"""Default config blobs aligned with compositor-backend scene/session shapes."""

GRAPHICS_LAYERS = (
    'background',
    'overlay',
    'logo',
    'qr',
    'banner',
    'ticker',
    'chat',
)

DEFAULT_GRAPHICS_CONFIG: dict = {layer: None for layer in GRAPHICS_LAYERS}

DEFAULT_DEVICES_CONFIG: dict = {
    'cameraId': None,
    'microphoneId': None,
    'speakerId': None,
}

DEFAULT_SOURCES_CONFIG: dict = {
    'version': 1,
    'sources': [],
    'assignments': {},
}

DEFAULT_BACKGROUND_MUSIC_CONFIG: dict = {
    'version': 1,
    'enabled': False,
    'track': None,
    'volume': 0.5,
    'loop': True,
    'muted': False,
}

DEFAULT_TILE_ORDER_CONFIG: dict = {
    'version': 1,
    'assignments': {},
}

DEFAULT_LAYOUT = 'CONTAIN'
