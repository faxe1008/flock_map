from contextlib import asynccontextmanager

from fastapi import FastAPI
from tortoise import Tortoise

from flockmap.config import TORTOISE_ORM
from flockmap.api import species, sightings


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: initialise Tortoise ORM (does NOT run migrations).
    await Tortoise.init(config=TORTOISE_ORM)
    yield
    # Shutdown: close DB connections.
    await Tortoise.close_connections()


app = FastAPI(
    title="FlockMap API",
    description="Bird-sighting tracking with PostGIS spatial queries.",
    version="0.1.0",
    lifespan=lifespan,
)

# Mount routers — order matters: fixed paths before parameterised ones.
app.include_router(sightings.router)
app.include_router(species.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
