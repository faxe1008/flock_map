from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from tortoise import Tortoise

from flockmap.config import TORTOISE_ORM
from flockmap.api import species, sightings


class _HealthcheckFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        return '"GET /health ' not in message


logging.getLogger("uvicorn.access").addFilter(_HealthcheckFilter())


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

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routers — order matters: fixed paths before parameterised ones.
app.include_router(sightings.router)
app.include_router(species.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
