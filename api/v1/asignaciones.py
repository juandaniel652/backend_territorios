"""
api/v1/asignaciones.py
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from core.database import get_db
from api.deps import require_admin, CurrentUser, get_asignacion_service
from domain.asignacion.service import AsignacionService
from domain.asignacion.schema import (
    AsignacionCreate,
    AsignacionUpdate,
    AsignacionUpdatedOut,
    AsignacionDeletedOut,
    AgendaConfirmar,
)
from domain.planilla.repository import PlanillaRepository
from domain.planilla.service import PlanillaService
from domain.territorio.repository import TerritorioRepository
from domain.territorio.service import TerritorioService


router = APIRouter(prefix="/asignaciones", tags=["asignaciones"])


# ── Dependency: PlanillaService ──────────────────────────────────────────────
def get_planilla_service(db: Session = Depends(get_db)) -> PlanillaService:
    territorio_repo = TerritorioRepository(db)
    planilla_repo = PlanillaRepository(db)
    territorio_service = TerritorioService(territorio_repo, planilla_repo)
    
    return PlanillaService(
        planilla_repo=planilla_repo,
        territorio_service=territorio_service
    )


# ── POST /asignaciones ───────────────────────────────────────────────────────
@router.post("", summary="Crear una nueva asignación")
def crear_asignacion(
    data: AsignacionCreate,
    asignacion_service: AsignacionService = Depends(get_asignacion_service),
    planilla_service: PlanillaService = Depends(get_planilla_service)
):
    resultado = asignacion_service.crear_asignacion(data)
    
    # 🎯 Sincronización quirúrgica usando el payload ya calculado por el servicio:
    if "sheets_payload" in resultado:
        planilla_service.sincronizar_registro_bisturi(resultado["sheets_payload"])
        
    return resultado


# ── PUT /asignaciones/{id} ───────────────────────────────────────────────────
@router.put(
    "/{asignacion_id}",
    response_model=AsignacionUpdatedOut,
    summary="Editar una asignación existente",
)
def actualizar_asignacion(
    asignacion_id: int,
    data: AsignacionUpdate,
    service: AsignacionService = Depends(get_asignacion_service),
    _: CurrentUser = Depends(require_admin),
):
    """
    Actualiza los campos enviados en el body.
    Los campos no enviados quedan sin cambios (patch semántico).

    Raises:
        401 / 403: sin token o sin rol admin.
        404: asignación no encontrada.
        422: datos inválidos.
    """
    return service.actualizar_asignacion(asignacion_id, data)


# ── DELETE /asignaciones/{id} ────────────────────────────────────────────────
@router.delete(
    "/{asignacion_id}",
    response_model=AsignacionDeletedOut,
    summary="Eliminar una asignación",
)
def eliminar_asignacion(
    asignacion_id: int,
    service: AsignacionService = Depends(get_asignacion_service),
    _: CurrentUser = Depends(require_admin),
):
    """
    Elimina permanentemente la asignación indicada.

    Raises:
        401 / 403: sin token o sin rol admin.
        404: asignación no encontrada.
    """
    return service.eliminar_asignacion(asignacion_id)


@router.post("/confirmar-agenda")
def confirmar_agenda(
    data: AgendaConfirmar,
    service: AsignacionService = Depends(get_asignacion_service),
    _: CurrentUser = Depends(require_admin),
):
    return service.confirmar_agenda_masiva(data)


@router.post("/preview-agenda")
def preview_agenda(
    data: AgendaConfirmar,
    service: AsignacionService = Depends(get_asignacion_service),
    _: CurrentUser = Depends(require_admin),
):
    return service.preview_agenda(data)


@router.get("/sugerencias", summary="Obtener sugerencias de territorios")
def sugerencias(
    rango: int = 3,
    service: AsignacionService = Depends(get_asignacion_service),
    _: CurrentUser = Depends(require_admin),
):
    return service.obtener_sugerencias(rango)


@router.get("/historial", summary="Obtener historial de asignaciones recientes")
def obtener_historial(
    limit: int = 20,
    service: AsignacionService = Depends(get_asignacion_service),
):
    return service.asignacion_repo.get_recientes(limit=limit)