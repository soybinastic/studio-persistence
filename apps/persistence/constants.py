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
    'cameraLabel': None,
    'microphoneId': None,
    'microphoneLabel': None,
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

# Legacy numeric asset types from the studio CMS catalog.
ASSET_TYPE_LOGO = 1
ASSET_TYPE_OVERLAY = 2
ASSET_TYPE_BACKGROUND = 4
ASSET_TYPE_GREEN_SCREEN = 5
ASSET_TYPE_QR_CODE = 6

ASSET_TYPE_CHOICES = (
    (ASSET_TYPE_LOGO, 'Logo'),
    (ASSET_TYPE_OVERLAY, 'Overlay'),
    (ASSET_TYPE_BACKGROUND, 'Background'),
    (ASSET_TYPE_GREEN_SCREEN, 'Green screen'),
    (ASSET_TYPE_QR_CODE, 'QR code'),
)

MEDIA_FORMAT_IMAGE = 'image'
MEDIA_FORMAT_VIDEO = 'video'

MEDIA_FORMAT_CHOICES = (
    (MEDIA_FORMAT_IMAGE, 'Image'),
    (MEDIA_FORMAT_VIDEO, 'Video'),
)

DEFAULT_ASSET_CATALOG: dict = {
    'backgrounds': [],
    'background_videos': [],
    'overlays': [],
    'logos': [],
    'green_screens': [],
    'qr_codes': [],
}

# Banner lower-third theme styles (aligned with compositor + studio-frontend).
BANNER_THEME_CLASSIC = 'classic'
BANNER_THEME_DEFAULT = 'default'
BANNER_THEME_ROUNDED = 'rounded'
BANNER_THEME_BRACKET = 'bracket'
BANNER_THEME_OUTLINED = 'outlined'
BANNER_THEME_PILL = 'pill'

BANNER_THEME_CHOICES = (
    (BANNER_THEME_CLASSIC, 'Classic'),
    (BANNER_THEME_DEFAULT, 'Default'),
    (BANNER_THEME_ROUNDED, 'Rounded'),
    (BANNER_THEME_BRACKET, 'Bracket'),
    (BANNER_THEME_OUTLINED, 'Outlined'),
    (BANNER_THEME_PILL, 'Pill'),
)

TICKER_POSITION_TOP = 'top'
TICKER_POSITION_BOTTOM = 'bottom'

TICKER_POSITION_CHOICES = (
    (TICKER_POSITION_TOP, 'Top'),
    (TICKER_POSITION_BOTTOM, 'Bottom'),
)

TICKER_DIRECTION_RTL = 'rtl'
TICKER_DIRECTION_LTR = 'ltr'

TICKER_DIRECTION_CHOICES = (
    (TICKER_DIRECTION_RTL, 'Right to left'),
    (TICKER_DIRECTION_LTR, 'Left to right'),
)

DEFAULT_TEXT_MATERIAL_CATALOG: dict = {
    'banners': [],
    'tickers': [],
}

DEFAULT_MUSIC_CATALOG: list = []
