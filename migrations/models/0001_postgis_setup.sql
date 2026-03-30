-- Initial migration for FlockMap
-- This must run AFTER `aerich init-db` creates the base tables,
-- or can be applied standalone against a fresh database.
--
-- Prerequisite: the PostGIS extension.
CREATE EXTENSION IF NOT EXISTS postgis;

-- ---------------------------------------------------------------------------
-- 1. Add the PostGIS geography column that Tortoise ORM cannot manage.
-- ---------------------------------------------------------------------------
ALTER TABLE sighting
  ADD COLUMN IF NOT EXISTS geog geography(Point, 4326);

-- Back-fill from the plain lat/lon columns (idempotent).
UPDATE sighting
   SET geog = ST_SetSRID(ST_MakePoint(location_lon, location_lat), 4326)::geography
 WHERE geog IS NULL
   AND location_lat IS NOT NULL
   AND location_lon IS NOT NULL;

-- ---------------------------------------------------------------------------
-- 2. Spatial index on the geography column (GiST).
--    This is what makes ST_DWithin and ST_Covers queries fast.
-- ---------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_sighting_geog
    ON sighting USING GIST (geog);

-- ---------------------------------------------------------------------------
-- 3. Composite indexes for common query patterns.
-- ---------------------------------------------------------------------------

-- Fast species + time range lookups (e.g. "all sightings of species X this month").
CREATE INDEX IF NOT EXISTS idx_sighting_species_observed
    ON sighting (species_id, observed_at DESC);

-- Support the viewport query: bounding-box filter + time order.
-- The GIST index above handles the spatial part; this B-tree helps with
-- the ORDER BY observed_at DESC that follows.
CREATE INDEX IF NOT EXISTS idx_sighting_observed_desc
    ON sighting (observed_at DESC);

-- GIN index on custom_attrs JSONB for ad-hoc attribute queries.
CREATE INDEX IF NOT EXISTS idx_sighting_custom_attrs
    ON sighting USING GIN (custom_attrs jsonb_path_ops);
