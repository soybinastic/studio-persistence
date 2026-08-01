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
    "destinations": []
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

Scene and configuration shapes mirror compositor-backend so the frontend can reuse existing types.

## Tests

```bash
python manage.py test apps.persistence
```
