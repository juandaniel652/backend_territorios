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

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from domain.territorio.model import Territorio
from domain.asignacion.model import Asignacion
from domain.conductor.model import Conductor
from domain.territorio.schema import TerritorioConAsignacionesOut, SugerenciasOut, AgendaItemIn, PropuestaDiaOut, TerritorioPlanillaInfo
from core.database import get_db
from domain.territorio.repository import TerritorioRepository
from domain.territorio.service import TerritorioService
from domain.territorio.schema import TerritorioConAsignacionesOut, SugerenciasOut
from datetime import date
from typing import List

from api.deps import get_asignacion_service
from domain.asignacion.service import AsignacionService
from domain.asignacion.schema import AgendaConfirmar
from domain.planilla.repository import PlanillaRepository # Nuevo import para el repo de planillas



router = APIRouter(prefix="/territorios", tags=["territorios"])


# ── Factory de servicio ──────────────────────────────────────────────────────
# Construye el grafo de dependencias para este router.
# Al estar separado del endpoint, puede ser sobreescrito en tests.

def get_territorio_service(db: Session = Depends(get_db)) -> TerritorioService:
    repo = TerritorioRepository(db)
    planilla_repo = PlanillaRepository(db) # <--- AGREGÁ ESTO
    
    # Pasale el planilla_repo para que pueda calcular los nombres 2026
    return TerritorioService(repo, planilla_repo=planilla_repo)


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.get(
    "/sugerencias",
    response_model=SugerenciasOut,
    summary="Territorios más atrasados por rango",
)
def obtener_sugerencias(
    rango: str = Query(..., description="Rango de territorios: '1-20', '21-40' o '41-60'"),
    limit: int = Query(default=10, ge=1, le=60),
    service: TerritorioService = Depends(get_territorio_service),
):
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
    return service.obtener_historial(numero)

@router.post("/confirmar-agenda", summary="Guarda la propuesta aceptada en la DB")
def confirmar_agenda(
    data: AgendaConfirmar,
    service: AsignacionService = Depends(get_asignacion_service)
):
    """
    Toma la lista de territorios, conductores y turnos 
    y los persiste en las tablas 'asignaciones' y 'salidas'.
    """
    return service.confirmar_agenda_masiva(data)

@router.get(
    "/propuesta-agenda",
    response_model=List[PropuestaDiaOut],  # <--- Usamos el nuevo esquema
    summary="Genera una propuesta basada en el día (Sábado vs Semana)",
)
def obtener_propuesta_agenda(
    fecha: date = Query(..., description="Fecha para la que se planea la salida"),
    service: TerritorioService = Depends(get_territorio_service),
):
    """
    Lógica de negocio aplicada:
    - Si es Sábado: Filtra Zona 3 y Zona 2 crítica.
    - Si es otro día: Filtra el resto.
    """
    return service.generar_propuesta_dia(fecha)

@router.get("/{numero}/planilla-status", response_model=TerritorioPlanillaInfo)
def get_territorio_planilla_status(
    numero: int, 
    service: TerritorioService = Depends(get_territorio_service)
):
    return service.obtener_estado_planilla(numero)