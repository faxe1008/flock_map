import hashlib
import math
from datetime import datetime, timezone


# ---------------------------------------------------------------------------
# Dedupe-key generation
#
# The key is a deterministic SHA-256 hex digest built from:
#   - species_id
#   - latitude  rounded to ~111 m   (3 decimal places)
#   - longitude rounded to ~111 m   (3 decimal places)
#   - observation count
#   - a 1-hour time bucket (floor of observed_at to the hour)
#
# This lets us reject duplicate rows that come from different scrape runs
# without losing genuinely distinct sightings.
# ---------------------------------------------------------------------------

_TIME_BUCKET_SECONDS = 3600  # 1 hour


def _round_coord(value: float, decimals: int = 3) -> float:
    """Round a coordinate to *decimals* places (default 3 ≈ 111 m)."""
    factor = 10**decimals
    return math.floor(value * factor) / factor


def _time_bucket(dt: datetime) -> int:
    """Return the unix timestamp floored to the nearest hour."""
    ts = int(dt.replace(tzinfo=timezone.utc).timestamp()) if dt.tzinfo is None else int(dt.timestamp())
    return ts - (ts % _TIME_BUCKET_SECONDS)


def compute_dedupe_key(
    species_id: int,
    latitude: float,
    longitude: float,
    count: int,
    observed_at: datetime,
) -> str:
    """Return a hex SHA-256 dedupe key for a sighting."""
    bucket = _time_bucket(observed_at)
    lat = _round_coord(latitude)
    lon = _round_coord(longitude)

    raw = f"{species_id}:{lat}:{lon}:{count}:{bucket}"
    return hashlib.sha256(raw.encode()).hexdigest()
