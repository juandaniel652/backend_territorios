"""
api/v1/territorios.py

Router del dominio Territorio.
Solo responsabilidades HTTP:
  - Parsear parámetros de ruta/query
  - Construir dependencias (repo, service)
  - Llamar al servicio
  - Devolver la respuesta tipada

Cero SQL, cero lógica de negocio aquí.

Reemplaza:
  - El endpoint GET /territorios/{numero} que vivía en app.py con SQL inline
  - El router completo de sugerir_territorios.py con SQL inline y cache acoplado
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from core.database import get_db
from domain.territorio.repository import TerritorioRepository
from domain.territorio.service import TerritorioService
from domain.territorio.schema import TerritorioConAsignacionesOut, SugerenciasOut

router = APIRouter(prefix="/territorios", tags=["territorios"])


# ── Factory de servicio ──────────────────────────────────────────────────────
# Construye el grafo de dependencias para este router.
# Al estar separado del endpoint, puede ser sobreescrito en tests.

def get_territorio_service(db: Session = Depends(get_db)) -> TerritorioService:
    repo = TerritorioRepository(db)
    return TerritorioService(repo)


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.get(
    "/sugerencias",
    response_model=SugerenciasOut,
    summary="Territorios más atrasados por rango",
)
def obtener_sugerencias(
    rango: str = Query(
        ...,
        description="Rango de territorios: '1-20', '21-40' o '41-60'",
        examples=["1-20"],
    ),
    limit: int = Query(
        default=10,
        ge=1,
        le=60,
        description="Cantidad máxima de sugerencias a retornar",
    ),
    service: TerritorioService = Depends(get_territorio_service),
):
    """
    Retorna los territorios del rango indicado ordenados por
    fecha de última asignación ascendente (más atrasados primero).

    Incluye campo `severidad`: nunca / critico / alto / normal.
    Respuestas están cacheadas 5 minutos en memoria.
    """
    return service.obtener_sugerencias(rango=rango, limit=limit)


@router.get(
    "/{numero}",
    response_model=TerritorioConAsignacionesOut,
    summary="Historial de asignaciones de un territorio",
)
def obtener_historial(
    numero: int,
    service: TerritorioService = Depends(get_territorio_service),
):
    """
    Retorna el historial completo de asignaciones de un territorio
    ordenado cronológicamente.

    Si no hay asignaciones, retorna lista vacía con mensaje informativo
    (no es un error — el territorio puede existir sin asignaciones).
    """
    return service.obtener_historial(numero)