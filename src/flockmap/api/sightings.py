from fastapi import APIRouter, HTTPException, Query
from tortoise import connections
from tortoise.exceptions import IntegrityError

from flockmap.dedupe import compute_dedupe_key
from flockmap.models.sighting import Sighting
from flockmap.schemas.schemas import SightingCreate, SightingRead

router = APIRouter(prefix="/sightings", tags=["sightings"])


def _row_to_read(s: Sighting, distance_m: float | None = None) -> SightingRead:
    return SightingRead(
        id=s.id,
        species_id=s.species_id,  # type: ignore[attr-defined]
        source_id=s.source_id,
        observed_at=s.observed_at,
        latitude=s.location_lat,
        longitude=s.location_lon,
        count=s.count,
        notes=s.notes,
        custom_attrs=s.custom_attrs,
        dedupe_key=s.dedupe_key,
        user_id=s.user_id,
        created_at=s.created_at,
        distance_m=distance_m,
    )


def _dict_to_read(r: dict, distance_m: float | None = None, seconds_ago: float | None = None) -> SightingRead:
    return SightingRead(
        id=r["id"],
        species_id=r["species_id"],
        source_id=r["source_id"],
        observed_at=r["observed_at"],
        latitude=r["location_lat"],
        longitude=r["location_lon"],
        count=r["count"],
        notes=r["notes"],
        custom_attrs=r["custom_attrs"],
        dedupe_key=r["dedupe_key"],
        user_id=r["user_id"],
        created_at=r["created_at"],
        distance_m=distance_m,
        seconds_ago=seconds_ago,
    )


# ---- Create ---------------------------------------------------------------

@router.post("", response_model=SightingRead, status_code=201)
async def create_sighting(body: SightingCreate):
    dedupe_key = compute_dedupe_key(
        species_id=body.species_id,
        latitude=body.latitude,
        longitude=body.longitude,
        count=body.count,
        observed_at=body.observed_at,
    )

    try:
        s = await Sighting.create(
            species_id=body.species_id,
            source_id=body.source_id,
            observed_at=body.observed_at,
            location_lat=body.latitude,
            location_lon=body.longitude,
            count=body.count,
            notes=body.notes,
            custom_attrs=body.custom_attrs,
            user_id=body.user_id,
            dedupe_key=dedupe_key,
        )
    except IntegrityError:
        raise HTTPException(
            409,
            f"Duplicate sighting (dedupe_key={dedupe_key})",
        )

    # Sync the PostGIS geog column via raw SQL.
    conn = connections.get("default")
    await conn.execute_query(
        "UPDATE sighting SET geog = ST_SetSRID(ST_MakePoint($1, $2), 4326)::geography WHERE id = $3",
        [body.longitude, body.latitude, s.id],
    )

    return _row_to_read(s)


# ---- Nearby (PostGIS ST_DWithin) ------------------------------------------
# NOTE: fixed paths (/nearby, /viewport) MUST be registered before the
#       parameterised path (/{sighting_id}) so FastAPI doesn't try to
#       parse "nearby" as an integer.

@router.get("/nearby", response_model=list[SightingRead])
async def sightings_nearby(
    latitude: float = Query(ge=-90, le=90),
    longitude: float = Query(ge=-180, le=180),
    radius_m: float = Query(default=5000, gt=0, le=50000),
    limit: int = Query(default=50, ge=1, le=500),
    duration_seconds: int | None = Query(default=None, gt=0, le=604800, description="Only sightings from the last X seconds (max 1 week)"),
):
    """Return sightings within *radius_m* metres of the given point.
    If duration_seconds is specified, only return sightings from the last X seconds.
    Results are ordered by duration (most recent first) if duration filter is used,
    otherwise ordered by distance (nearest first).
    """
    conn = connections.get("default")
    
    # Build the SQL query based on whether duration filtering is requested
    if duration_seconds:
        # With duration filtering: calculate seconds_ago and filter by time
        sql = """
        SELECT s.*,
               ST_Distance(s.geog, ST_SetSRID(ST_MakePoint($1, $2), 4326)::geography) AS distance_m,
               EXTRACT(EPOCH FROM (NOW() - s.observed_at)) AS seconds_ago
          FROM sighting s
         WHERE ST_DWithin(s.geog, ST_SetSRID(ST_MakePoint($1, $2), 4326)::geography, $3)
           AND s.observed_at >= NOW() - make_interval(secs => $4)
         ORDER BY s.observed_at DESC
         LIMIT $5
        """
        rows = await conn.execute_query_dict(
            sql,
            [longitude, latitude, radius_m, duration_seconds, limit],
        )
        return [_dict_to_read(r, distance_m=r["distance_m"], seconds_ago=r["seconds_ago"]) for r in rows]
    else:
        # Without duration filtering: original behavior (ordered by distance)
        sql = """
        SELECT s.*,
               ST_Distance(s.geog, ST_SetSRID(ST_MakePoint($1, $2), 4326)::geography) AS distance_m
          FROM sighting s
         WHERE ST_DWithin(s.geog, ST_SetSRID(ST_MakePoint($1, $2), 4326)::geography, $3)
         ORDER BY distance_m
         LIMIT $4
        """
        rows = await conn.execute_query_dict(
            sql,
            [longitude, latitude, radius_m, limit],
        )
        return [_dict_to_read(r, distance_m=r["distance_m"]) for r in rows]


# ---- Viewport (bounding-box) query ----------------------------------------

@router.get("/viewport", response_model=list[SightingRead])
async def sightings_viewport(
    sw_lat: float = Query(ge=-90, le=90),
    sw_lon: float = Query(ge=-180, le=180),
    ne_lat: float = Query(ge=-90, le=90),
    ne_lon: float = Query(ge=-180, le=180),
    limit: int = Query(default=200, ge=1, le=2000),
    duration_seconds: int | None = Query(default=None, gt=0, le=604800, description="Only sightings from the last X seconds (max 1 week)"),
):
    """Return sightings within the given map viewport (bounding box).
    If duration_seconds is specified, only return sightings from the last X seconds.
    Results are always ordered by observation time (most recent first).
    """
    conn = connections.get("default")
    
    # Build the SQL query based on whether duration filtering is requested
    if duration_seconds:
        # With duration filtering: calculate seconds_ago and filter by time
        sql = """
        SELECT s.*,
               EXTRACT(EPOCH FROM (NOW() - s.observed_at)) AS seconds_ago
          FROM sighting s
         WHERE ST_Covers(
                 ST_MakeEnvelope($1, $2, $3, $4, 4326)::geography,
                 s.geog
               )
           AND s.observed_at >= NOW() - make_interval(secs => $5)
         ORDER BY s.observed_at DESC
         LIMIT $6
        """
        rows = await conn.execute_query_dict(
            sql,
            [sw_lon, sw_lat, ne_lon, ne_lat, duration_seconds, limit],
        )
        return [_dict_to_read(r, seconds_ago=r["seconds_ago"]) for r in rows]
    else:
        # Without duration filtering: original behavior
        sql = """
        SELECT s.*
          FROM sighting s
         WHERE ST_Covers(
                 ST_MakeEnvelope($1, $2, $3, $4, 4326)::geography,
                 s.geog
               )
         ORDER BY s.observed_at DESC
         LIMIT $5
        """
        rows = await conn.execute_query_dict(
            sql,
            [sw_lon, sw_lat, ne_lon, ne_lat, limit],
        )
        return [_dict_to_read(r) for r in rows]


# ---- Single sighting (parameterised — must be LAST) -----------------------

@router.get("/{sighting_id}", response_model=SightingRead)
async def get_sighting(sighting_id: int):
    s = await Sighting.get_or_none(id=sighting_id)
    if not s:
        raise HTTPException(404, "Sighting not found")
    return _row_to_read(s)
