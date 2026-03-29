"""
api/v1/asignaciones.py

Router del dominio Asignacion.
Solo responsabilidades HTTP: parseo, dependencias, delegación al servicio.

Reemplaza asignaciones.py original que tenía:
  - Schema definido inline (AsignacionCrear)
  - SQL directo con engine.begin()
  - Lógica de negocio (obtener/crear conductor) en el mismo bloque
  - Verificación de rol inline (if user["rol"] != "admin")
  - except Exception genérico

Ahora el router tiene 3 líneas de lógica real: construir servicio,
llamar a crear_asignacion, retornar resultado.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from core.database import get_db
from api.deps import require_admin, CurrentUser
from domain.asignacion.repository import AsignacionRepository
from domain.asignacion.service import AsignacionService
from domain.asignacion.schema import AsignacionCreate, AsignacionCreatedOut
from domain.conductor.repository import ConductorRepository
from domain.territorio.repository import TerritorioRepository

router = APIRouter(prefix="/asignaciones", tags=["asignaciones"])


# ── Factory de servicio ──────────────────────────────────────────────────────

def get_asignacion_service(db: Session = Depends(get_db)) -> AsignacionService:
    """
    Construye AsignacionService con los tres repositorios que necesita.
    La Session es la misma para los tres → misma transacción.
    """
    return AsignacionService(
        db=db,
        asignacion_repo=AsignacionRepository(db),
        territorio_repo=TerritorioRepository(db),
        conductor_repo=ConductorRepository(db),
    )


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.post(
    "",
    response_model=AsignacionCreatedOut,
    status_code=201,
    summary="Registrar nueva asignación de territorio",
)
def crear_asignacion(
    data: AsignacionCreate,
    service: AsignacionService = Depends(get_asignacion_service),
    _: CurrentUser = Depends(require_admin),   # solo admin puede crear
):
    """
    Registra una nueva asignación de territorio a un conductor.

    - Si el conductor no existe en la DB, se crea automáticamente.
    - El campo `conductor_creado` en la respuesta indica si fue insertado.
    - Requiere token JWT con rol `admin`.

    Raises:
        401: token ausente o inválido.
        403: usuario autenticado sin rol admin.
        404: el territorio indicado no existe.
        422: datos de entrada inválidos (fechas, campos vacíos).
    """
    return service.crear_asignacion(data)