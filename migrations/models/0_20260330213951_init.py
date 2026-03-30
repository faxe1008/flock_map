from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "species" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "common_name" VARCHAR(255) NOT NULL,
    "scientific_name" VARCHAR(255) NOT NULL UNIQUE,
    "family" VARCHAR(255) NOT NULL,
    "rarity_rank" INT NOT NULL DEFAULT 0,
    "is_rare" BOOL NOT NULL DEFAULT False,
    "image_data" BYTEA,
    "image_mime" VARCHAR(64)
);
CREATE INDEX IF NOT EXISTS "idx_species_common__ceec6f" ON "species" ("common_name");
CREATE INDEX IF NOT EXISTS "idx_species_scienti_8a2483" ON "species" ("scientific_name");
CREATE INDEX IF NOT EXISTS "idx_species_family_428da7" ON "species" ("family");
CREATE INDEX IF NOT EXISTS "idx_species_is_rare_eeea44" ON "species" ("is_rare");
COMMENT ON COLUMN "species"."rarity_rank" IS 'Lower = more common';
COMMENT ON COLUMN "species"."image_data" IS 'Raw image bytes (thumbnail)';
COMMENT ON COLUMN "species"."image_mime" IS 'MIME type of image_data, e.g. image/webp';
COMMENT ON TABLE "species" IS 'Bird species reference table.';
CREATE TABLE IF NOT EXISTS "sighting" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "source_id" VARCHAR(255),
    "observed_at" TIMESTAMPTZ NOT NULL,
    "location_lat" DOUBLE PRECISION NOT NULL,
    "location_lon" DOUBLE PRECISION NOT NULL,
    "count" INT NOT NULL DEFAULT 1,
    "notes" TEXT,
    "custom_attrs" JSONB,
    "dedupe_key" VARCHAR(64) NOT NULL UNIQUE,
    "user_id" INT,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "species_id" INT NOT NULL REFERENCES "species" ("id") ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS "idx_sighting_source__8039ab" ON "sighting" ("source_id");
CREATE INDEX IF NOT EXISTS "idx_sighting_observe_b1c95c" ON "sighting" ("observed_at");
CREATE INDEX IF NOT EXISTS "idx_sighting_dedupe__7192f1" ON "sighting" ("dedupe_key");
CREATE INDEX IF NOT EXISTS "idx_sighting_user_id_3186ff" ON "sighting" ("user_id");
CREATE INDEX IF NOT EXISTS "idx_sighting_species_d5bd6d" ON "sighting" ("species_id");
COMMENT ON COLUMN "sighting"."source_id" IS 'Identifier from the upstream data source';
COMMENT ON COLUMN "sighting"."custom_attrs" IS 'Arbitrary extra attributes as JSONB';
COMMENT ON COLUMN "sighting"."dedupe_key" IS 'SHA-256 hex digest for deduplication';
COMMENT ON COLUMN "sighting"."user_id" IS 'Optional: user who reported the sighting';
COMMENT ON TABLE "sighting" IS 'A single bird sighting record.';
CREATE TABLE IF NOT EXISTS "aerich" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "version" VARCHAR(255) NOT NULL,
    "app" VARCHAR(100) NOT NULL,
    "content" JSONB NOT NULL
);"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        """


MODELS_STATE = (
    "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"
)
