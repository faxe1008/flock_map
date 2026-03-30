import os

from dotenv import load_dotenv

load_dotenv()

DATABASE_URL: str = os.environ.get(
    "DATABASE_URL",
    "postgres://flockmap:flockmap@localhost:5432/flockmap",
)

TORTOISE_ORM = {
    "connections": {
        "default": DATABASE_URL,
    },
    "apps": {
        "models": {
            "models": ["flockmap.models.species", "flockmap.models.sighting", "aerich.models"],
            "default_connection": "default",
        },
    },
}
