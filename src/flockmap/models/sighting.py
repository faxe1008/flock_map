from tortoise import fields
from tortoise.models import Model


class Sighting(Model):
    """A single bird sighting record.

    The ``location_lat`` / ``location_lon`` columns are plain floats managed
    by Tortoise ORM.  A *real* PostGIS ``geography(Point,4326)`` column called
    ``geog`` is maintained via a raw-SQL migration so we can use spatial
    indexes and ST_DWithin / ST_MakeEnvelope queries without needing a
    PostGIS-aware ORM layer.
    """

    id = fields.IntField(primary_key=True)

    species: fields.ForeignKeyRelation["Species"] = fields.ForeignKeyField(
        "models.Species",
        related_name="sightings",
        on_delete=fields.CASCADE,
        index=True,
    )

    source_id = fields.CharField(
        max_length=255,
        null=True,
        index=True,
        description="Identifier from the upstream data source",
    )

    observed_at = fields.DatetimeField(index=True)

    # Plain lat/lon so Tortoise can read/write them normally.
    location_lat = fields.FloatField()
    location_lon = fields.FloatField()

    count = fields.IntField(default=1)
    notes = fields.TextField(null=True)

    custom_attrs = fields.JSONField(
        null=True,
        description="Arbitrary extra attributes as JSONB",
    )

    dedupe_key = fields.CharField(
        max_length=64,
        unique=True,
        index=True,
        description="SHA-256 hex digest for deduplication",
    )

    user_id = fields.IntField(
        null=True,
        index=True,
        description="Optional: user who reported the sighting",
    )

    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "sighting"
        ordering = ["-observed_at"]

    def __str__(self) -> str:
        return f"Sighting(species={self.species_id}, {self.location_lat},{self.location_lon})"


# Avoid circular import — needed only for the type annotation above.
from flockmap.models.species import Species  # noqa: E402, F401
