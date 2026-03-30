from tortoise import fields
from tortoise.models import Model


class Species(Model):
    """Bird species reference table."""

    id = fields.IntField(primary_key=True)
    common_name = fields.CharField(max_length=255, index=True)
    scientific_name = fields.CharField(max_length=255, unique=True, index=True)
    family = fields.CharField(max_length=255, index=True)
    rarity_rank = fields.IntField(default=0, description="Lower = more common")
    is_rare = fields.BooleanField(default=False, index=True)

    # Small thumbnail stored directly in the DB (bytea).
    # Nullable because we won't have images for every species right away.
    image_data = fields.BinaryField(null=True, description="Raw image bytes (thumbnail)")
    image_mime = fields.CharField(
        max_length=64,
        null=True,
        description="MIME type of image_data, e.g. image/webp",
    )

    class Meta:
        table = "species"
        ordering = ["common_name"]

    def __str__(self) -> str:
        return f"{self.common_name} ({self.scientific_name})"
