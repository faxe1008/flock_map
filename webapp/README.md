# FlockMap Web App

Mobile-first frontend for viewing nearby bird sightings on an interactive map.

## Stack

- Next.js (App Router)
- React + TypeScript
- Tailwind CSS v4
- MapLibre GL JS (WebGL map rendering)

## Setup

1. Install dependencies:

```bash
npm install
```

2. Configure environment:

```bash
cp .env.example .env.local
```

3. Start development server:

```bash
npm run dev
```

4. Open:

```text
http://localhost:3000
```

## API Integration

The frontend proxies backend requests through Next.js route handlers:

- `GET /api/sightings/nearby` -> `${FLOCKMAP_API_BASE_URL}/sightings/nearby`
- `GET /api/sightings/viewport` -> `${FLOCKMAP_API_BASE_URL}/sightings/viewport`
- `GET /api/species` -> `${FLOCKMAP_API_BASE_URL}/species`

By default, `FLOCKMAP_API_BASE_URL` is `http://localhost:8000`.

## Features

- Requests browser geolocation and recenters map to the user
- Renders sightings with MapLibre GL JS (WebGL)
- Mobile-first layout optimized for phones
- Species dropdown sourced from database species only
- Viewport-driven sightings loading (based on current map rectangle)
- Time-range filter

## Docker

From repository root:

```bash
docker compose up -d
```

Services:

- PostGIS: `localhost:5432`
- Web app + API proxy: `localhost:3000`
- Scheduled scraper: runs continuously in its own container

The backend is reachable through the same web port via `/api/*`.

Examples:

- `http://localhost:3000/api/species`
- `http://localhost:3000/api/sightings/viewport?...`

By default, the compose stack pulls images from GHCR:

- `ghcr.io/faxe1008/flockmap-server:latest`
- `ghcr.io/faxe1008/flockmap-scraper:latest`
- `ghcr.io/faxe1008/flockmap-webapp:latest`

To test local image builds instead, use the local override:

```bash
docker compose -f docker-compose.yml -f docker-compose.local.yml up --build
```
