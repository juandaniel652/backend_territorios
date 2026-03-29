"""
main.py

Punto de entrada de la aplicación. Responsabilidad única: construir
y configurar la instancia FastAPI.

Regla: main.py no contiene lógica de negocio, SQL, ni imports de dominio.
Solo monta middleware, routers y eventos de ciclo de vida.

Arrancar en desarrollo:
    uvicorn main:app --reload --host 127.0.0.1 --port 8000

Arrancar en producción:
    uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import settings
from core.database import engine, Base
from api.v1.router import router as v1_router


# ── Ciclo de vida ────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Eventos de inicio y cierre de la aplicación.

    startup:  crea tablas si no existen (útil en desarrollo/tests).
              En producción se recomienda usar Alembic en lugar de create_all.
    shutdown: libera recursos del pool de conexiones.
    """
    # startup
    Base.metadata.create_all(bind=engine)
    yield
    # shutdown
    engine.dispose()


# ── Instancia FastAPI ────────────────────────────────────────────────────────

app = FastAPI(
    title="Territorios API",
    description="API para gestión de asignaciones de territorios",
    version="1.0.0",
    lifespan=lifespan,
    # En producción conviene deshabilitar /docs y /redoc:
    # docs_url=None if settings.ENVIRONMENT == "production" else "/docs",
    # redoc_url=None if settings.ENVIRONMENT == "production" else "/redoc",
)


# ── Middleware ───────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,   # centralizado en config.py
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Routers ──────────────────────────────────────────────────────────────────

app.include_router(v1_router)


# ── Rutas utilitarias ────────────────────────────────────────────────────────

@app.get("/health", tags=["health"])
def health():
    """Endpoint de salud para load balancers y monitoreo."""
    return {"status": "ok", "environment": settings.ENVIRONMENT}