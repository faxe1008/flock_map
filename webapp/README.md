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
