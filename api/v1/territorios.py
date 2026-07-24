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
from domain.territorio.schema import TerritorioConAsignacionesOut, SugerenciasOut, AgendaItemIn, PropuestaDiaOut, TerritorioPlanillaInfo, HistorialPosicionadoOut, AsignacionPosicionada, SemanaDisponible, ReporteTerritorioSemanal
from core.database import get_db
from domain.territorio.repository import TerritorioRepository
from domain.territorio.service import TerritorioService

from datetime import date
from typing import List

from api.deps import get_asignacion_service
from domain.asignacion.service import AsignacionService
from domain.asignacion.schema import AgendaConfirmar
from domain.planilla.repository import PlanillaRepository # Nuevo import para el repo de planillas
from domain.planilla.service import PlanillaService


router = APIRouter(prefix="/territorios", tags=["territorios"])


# ── Factory de servicio ──────────────────────────────────────────────────────
# Construye el grafo de dependencias para este router.
# Al estar separado del endpoint, puede ser sobreescrito en tests.

def get_territorio_service(db: Session = Depends(get_db)) -> TerritorioService:
    repo = TerritorioRepository(db)
    planilla_repo = PlanillaRepository(db) # <--- AGREGÁ ESTO
    
    # Pasale el planilla_repo para que pueda calcular los nombres 2026
    return TerritorioService(repo, planilla_repo=planilla_repo)

def get_planilla_service(
    db: Session = Depends(get_db),
    territorio_service: TerritorioService = Depends(get_territorio_service)
) -> PlanillaService:
    planilla_repo = PlanillaRepository(db)
    return PlanillaService(planilla_repo=planilla_repo, territorio_service=territorio_service)


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

@router.get(
    "/{numero}/historial-posicionado",
    response_model=HistorialPosicionadoOut,
    summary="Historial cronológico posicionado en sus respectivas planillas",
)
def obtener_historial_posicionado(
    numero: int,
    service: TerritorioService = Depends(get_territorio_service),
):
    """
    Retorna todo el historial del territorio ordenado por fecha, asignándole
    a cada salida su Ciclo, Fila y Nombre de Planilla correspondiente.
    """
    return service.obtener_historial_posicionado(numero)

# ── Endpoints de Reporte Semanal ─────────────────────────────────────────────

@router.get(
    "/reportes/semanas-disponibles",
    response_model=List[SemanaDisponible],
    summary="Listado de semanas con actividad para selectores",
)
def obtener_semanas_con_actividad(
    service: TerritorioService = Depends(get_territorio_service),
):
    """
    Retorna los rangos de fecha de Lunes a Domingo de las semanas
    que tienen asignaciones registradas, listas para poblar un Dropdown.
    """
    return service.obtener_semanas_disponibles()


@router.get(
    "/reportes/semanal",
    response_model=List[ReporteTerritorioSemanal],
    summary="Reporte detallado de territorios completados en una semana",
)
def obtener_reporte_semanal(
    fecha_inicio: date = Query(..., description="Lunes de la semana (YYYY-MM-DD)"),
    fecha_fin: date = Query(..., description="Domingo de la semana (YYYY-MM-DD)"),
    service: TerritorioService = Depends(get_territorio_service),
):
    """
    Retorna la lista de territorios asignados o completados en el rango de fechas
    indicando el conductor, la zona y la cantidad abarcada.
    """
    return service.obtener_reporte_semanal(fecha_inicio, fecha_fin)


# ── Endpoint Sincronización Drive ─────────────────────────────────────────────

@router.post("/sincronizar-drive/{numero_territorio}")
def sincronizar_drive(
    numero_territorio: int,
    planilla_service: PlanillaService = Depends(get_planilla_service)
):
    planilla_service.sincronizar_territorio_completo_a_drive(numero_territorio)
    return {
        "status": "ok", 
        "mensaje": f"Territorio {numero_territorio} sincronizado correctamente en Drive."
    }