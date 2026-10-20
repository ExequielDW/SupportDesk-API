"""Punto de entrada de la aplicación FastAPI."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import ORJSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.middleware.trustedhost import TrustedHostMiddleware

from config import ALLOWED_HOSTS, CORS_ORIGINS, IS_PRODUCTION
from database.client import close_db, get_db, ping_db
from database.indexes import crear_indices
from routers import auth, tickets, users
from services.cache import cache
from utils.middlewares import (
    HeadersSeguridadMiddleware,
    LimiteBodyMiddleware,
    TiempoProcesamientoMiddleware,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("supportdesk")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Arranque y apagado: cache, ping a Mongo e índices."""
    await cache.connect()
    try:
        await ping_db()
        await crear_indices(get_db())
    except Exception as exc:
        if IS_PRODUCTION:
            raise
        logger.warning("MongoDB no disponible al arrancar: %s", exc)

    yield

    await cache.close()
    await close_db()


app = FastAPI(
    title="SupportDesk API",
    version="1.0.0",
    description="API REST de gestión de tickets de soporte técnico.",
    lifespan=lifespan,
    default_response_class=ORJSONResponse,
    # En producción la documentación no se expone.
    docs_url=None if IS_PRODUCTION else "/docs",
    redoc_url=None if IS_PRODUCTION else "/redoc",
    openapi_url=None if IS_PRODUCTION else "/openapi.json",
)

# Rate limiting (SlowAPI)
app.state.limiter = auth.limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Middlewares
app.add_middleware(TiempoProcesamientoMiddleware)
app.add_middleware(HeadersSeguridadMiddleware)
app.add_middleware(LimiteBodyMiddleware)
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=ALLOWED_HOSTS)
if CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ORIGINS,
        allow_credentials=True,  # necesario para la cookie del refresh token
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
        max_age=600,
    )

app.include_router(users.router)
app.include_router(tickets.router)


@app.get("/")
async def root():
    return {"message": "Bienvenidos a SupportDesk Api"}


@app.get("/health")
async def health():
    """Sonda de vida. No expone datos sensibles."""
    return {"estado": "ok"}
