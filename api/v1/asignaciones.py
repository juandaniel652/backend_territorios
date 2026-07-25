"""
api/v1/asignaciones.py
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from core.database import get_db
from api.deps import require_admin, CurrentUser
from domain.asignacion.repository import AsignacionRepository
from domain.asignacion.service import AsignacionService
from domain.asignacion.schema import (
    AsignacionCreate,
    AsignacionUpdate,
    AsignacionCreatedOut,
    AsignacionUpdatedOut,
    AsignacionDeletedOut,
)
from domain.conductor.repository import ConductorRepository
from domain.territorio.repository import TerritorioRepository
from domain.asignacion.schema import AgendaConfirmar
from domain.salida.repository import SalidaRepository
from domain.asignacion.schema import AgendaConfirmar
from domain.territorio.service import TerritorioService
from domain.planilla.repository import PlanillaRepository

from fastapi import APIRouter, Depends, BackgroundTasks
from domain.planilla.service import PlanillaService


router = APIRouter(prefix="/asignaciones", tags=["asignaciones"])


def get_asignacion_service(db: Session = Depends(get_db)) -> AsignacionService:
    # Necesitamos estos para la automatización
    territorio_repo = TerritorioRepository(db)
    planilla_repo = PlanillaRepository(db)
    
    # El territorio_service nos ayuda a calcular el estado actual
    territorio_service = TerritorioService(territorio_repo, planilla_repo)

    return AsignacionService(
        db=db,
        asignacion_repo=AsignacionRepository(db),
        territorio_repo=territorio_repo,
        conductor_repo=ConductorRepository(db),
        salida_repo=SalidaRepository(db),
        # --- AGREGADOS ---
        planilla_repo=planilla_repo,
        territorio_service=territorio_service
    )


# ── POST /asignaciones ───────────────────────────────────────────────────────
@router.post(
    "",
    response_model=AsignacionCreatedOut,
    status_code=201,
    summary="Registrar nueva asignación de territorio",
)
def crear_asignacion(
    data: AsignacionCreate,
    background_tasks: BackgroundTasks, # <-- INYECTAMOS AQUÍ
    service: AsignacionService = Depends(get_asignacion_service),
    _: CurrentUser = Depends(require_admin),
):
    # 1. El servicio realiza el guardado atómico en DB y devuelve la metadata calculada
    res = service.crear_asignacion(data)
    
    # 2. Si el servicio generó los datos para Google Sheets, disparamos la tarea de fondo
    if "sheets_payload" in res:
        planilla_service = PlanillaService()
        background_tasks.add_task(
            planilla_service.sincronizar_registro_bisturi, 
            res["sheets_payload"]
        )
    
    return res


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
    # _: CurrentUser = Depends(require_admin), # Descomenta si queres seguridad
):
    # Asegurate de que el service tenga un método para listar asignaciones
    # Si no lo tiene, podés usar directamente el repo aquí para probar
    return service.asignacion_repo.get_recientes(limit=limit)