# Studio Persistence API

Django service that persists studio configuration per tenant: scenes, graphics, overlays, sources, background music, RTMP destinations, and device selections.

## Setup

```bash
cd studio-persistence
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py seed_studio_assets
python manage.py seed_text_materials
python manage.py runserver 8001
```

## Bootstrap (Studio Frontend on load)

**POST** `/api/persistence/tenant`

Request:

```json
{
  "tenant_id": "550e8400-e29b-41d4-a716-446655440000",
  "tenant_name": "My Studio"
}
```

Response (new tenant, HTTP 201):

```json
{
  "tenant_id": "550e8400-e29b-41d4-a716-446655440000",
  "tenant_name": "My Studio",
  "created": true,
  "configuration": {
    "layout": "CONTAIN",
    "tile_order_config": { "version": 1, "assignments": {} },
    "active_scene_id": null,
    "devices": { "cameraId": null, "microphoneId": null, "speakerId": null },
    "graphics_config": {
      "background": null,
      "overlay": null,
      "logo": null,
      "qr": null,
      "banner": null,
      "ticker": null,
      "chat": null
    },
    "scenes": [],
    "destinations": [],
    "asset_catalog": {
      "backgrounds": [],
      "background_videos": [],
      "overlays": [],
      "logos": [],
      "green_screens": [],
      "qr_codes": []
    }
  }
}
```

If the tenant already exists, returns HTTP 200 with `created: false` and the saved configuration.

## Studio frontend integration

The frontend bootstraps the tenant on app load using env vars (until iframe postMessage is wired):

```env
VITE_PERSISTENCE_API_URL=http://localhost:8001/api/persistence
VITE_TENANT_ID=550e8400-e29b-41d4-a716-446655440000
VITE_TENANT_NAME=My Studio
VITE_PERSISTENCE_ENABLED=true
```

Studio changes are dual-written to compositor (live session) and persistence (tenant config).

## Persistence endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET/PATCH | `/api/persistence/tenant/{tenant_id}/configuration/` | Session-level layout, devices, tile order, graphics |
| GET/POST | `/api/persistence/tenant/{tenant_id}/scenes/` | List or create scenes |
| PATCH/DELETE | `/api/persistence/tenant/{tenant_id}/scenes/{scene_id}/` | Update or delete a scene |
| GET/POST | `/api/persistence/tenant/{tenant_id}/destinations/` | List or create RTMP destinations |
| PATCH/DELETE | `/api/persistence/tenant/{tenant_id}/destinations/{destination_id}/` | Update or delete a destination |
| GET | `/api/persistence/tenant/{tenant_id}/assets/` | Studio media catalog (backgrounds, overlays, logos, etc.) |
| GET | `/api/persistence/tenant/{tenant_id}/text-materials/` | Banner and ticker material catalog |
| GET/POST | `/api/persistence/tenant/{tenant_id}/banners/` | List or create banner materials |
| PATCH/DELETE | `/api/persistence/tenant/{tenant_id}/banners/{banner_id}/` | Update or delete a tenant banner |
| GET/POST | `/api/persistence/tenant/{tenant_id}/tickers/` | List or create ticker materials |
| PATCH/DELETE | `/api/persistence/tenant/{tenant_id}/tickers/{ticker_id}/` | Update or delete a tenant ticker |

Scene and configuration shapes mirror compositor-backend so the frontend can reuse existing types.

## Studio media assets

System-default graphics materials (backgrounds, animated backgrounds, overlays, logos) are stored in `StudioMediaAsset` with `tenant=NULL`. Tenant uploads are stored with `tenant=<uuid>`.

Asset type codes (legacy CMS):

| Type | Category |
|------|----------|
| 1 | Logo |
| 2 | Overlay |
| 4 | Background (image or video) |
| 5 | Green screen |
| 6 | QR code |

Seed the 25 system defaults after migrating:

```bash
python manage.py seed_studio_assets
```

The bootstrap and configuration responses include `asset_catalog`, grouped as:

```json
{
  "backgrounds": [],
  "background_videos": [],
  "overlays": [],
  "logos": [],
  "green_screens": [],
  "qr_codes": []
}
```

## Banner and ticker materials

Host-created banner lower-thirds and scrolling tickers are stored as tenant materials:

- `TenantBannerMaterial` — title, description, theme, colors, font size
- `TenantTickerMaterial` — scrolling text, position, direction, speed, colors

System defaults use `tenant=NULL` (same pattern as media assets). Bootstrap includes `text_material_catalog`:

```json
{
  "banners": [],
  "tickers": []
}
```

Each catalog item includes a compositor-ready `banner` or `ticker` payload for the graphics panel.

Seed the 3 system banner + 3 system ticker presets:

```bash
python manage.py seed_text_materials
```

## Tests

```bash
python manage.py test apps.persistence
```
