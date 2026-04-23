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

router = APIRouter(prefix="/asignaciones", tags=["asignaciones"])


def get_asignacion_service(db: Session = Depends(get_db)) -> AsignacionService:
    return AsignacionService(
        db=db,
        asignacion_repo=AsignacionRepository(db),
        territorio_repo=TerritorioRepository(db),
        conductor_repo=ConductorRepository(db),
        salida_repo=SalidaRepository(db),
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
    service: AsignacionService = Depends(get_asignacion_service),
    _: CurrentUser = Depends(require_admin),
):
    return service.crear_asignacion(data)


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

@router.post(
    "/confirmar-agenda",
    status_code=201,
    summary="Confirmar e impactar la agenda quincenal en la base de datos",
)

@router.post(
    "/confirmar-agenda",
    status_code=201,
    summary="Confirmar e impactar la agenda quincenal en la base de datos",
)
def confirmar_agenda(
    data: AgendaConfirmar,
    service: AsignacionService = Depends(get_asignacion_service),
    _: CurrentUser = Depends(require_admin),
):
    return service.confirmar_agenda_masiva(data)