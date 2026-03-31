from datetime import datetime

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Species
# ---------------------------------------------------------------------------

class SpeciesCreate(BaseModel):
    common_name: str
    scientific_name: str
    family: str
    rarity_rank: int = 0
    is_rare: bool = False


class SpeciesRead(SpeciesCreate):
    id: int
    has_image: bool = False

    class Config:
        from_attributes = True


class SpeciesUpdate(BaseModel):
    common_name: str | None = None
    scientific_name: str | None = None
    family: str | None = None
    rarity_rank: int | None = None
    is_rare: bool | None = None


# ---------------------------------------------------------------------------
# Sighting
# ---------------------------------------------------------------------------

class SightingCreate(BaseModel):
    species_id: int
    source_id: str | None = None
    observed_at: datetime
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    count: int = Field(default=1, ge=0)
    notes: str | None = None
    custom_attrs: dict | None = None
    user_id: int | None = None


class SightingRead(BaseModel):
    id: int
    species_id: int
    source_id: str | None
    observed_at: datetime
    latitude: float
    longitude: float
    count: int
    notes: str | None
    custom_attrs: dict | None
    dedupe_key: str
    user_id: int | None
    created_at: datetime
    distance_m: float | None = None  # populated by nearby queries
    seconds_ago: float | None = None  # populated by duration-filtered queries

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------

class NearbyQuery(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    radius_m: float = Field(default=5000, gt=0, le=50000, description="Search radius in metres")
    limit: int = Field(default=50, ge=1, le=500)
    duration_seconds: int | None = Field(default=None, gt=0, le=604800, description="Only sightings from the last X seconds (max 1 week)")


class ViewportQuery(BaseModel):
    sw_lat: float = Field(ge=-90, le=90, description="Southwest corner latitude")
    sw_lon: float = Field(ge=-180, le=180, description="Southwest corner longitude")
    ne_lat: float = Field(ge=-90, le=90, description="Northeast corner latitude")
    ne_lon: float = Field(ge=-180, le=180, description="Northeast corner longitude")
    limit: int = Field(default=200, ge=1, le=2000)
    duration_seconds: int | None = Field(default=None, gt=0, le=604800, description="Only sightings from the last X seconds (max 1 week)")
