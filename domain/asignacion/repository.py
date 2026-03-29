"""
domain/asignacion/repository.py

Patrón Repository + DI para el dominio Asignacion.

Responsabilidad: persistencia de asignaciones únicamente.
NO resuelve conductores ni territorios — eso es tarea del servicio
que coordina múltiples repositorios.

El método crear() recibe IDs ya resueltos (territorio_id, conductor_id),
lo que lo hace atómico y testeable de forma aislada.
"""

from typing import Protocol, runtime_checkable
from sqlalchemy.orm import Session
from datetime import date
from typing import Optional

from domain.asignacion.model import Asignacion


# ─────────────────────────────────────────────
# 1. Protocolo (interfaz para DI)
# ─────────────────────────────────────────────

@runtime_checkable
class AsignacionRepositoryProtocol(Protocol):

    def crear(
        self,
        territorio_id: int,
        conductor_id: int,
        fecha_asignado: date,
        fecha_completado: Optional[date],
        cantidad_abarcado: str,
    ) -> Asignacion:
        """
        Inserta una nueva asignación y la retorna con su id.
        Los IDs de territorio y conductor deben estar ya resueltos.
        """
        ...

    def obtener_por_id(self, asignacion_id: int) -> Asignacion | None:
        """Retorna una asignación por su PK, o None si no existe."""
        ...

    def listar_por_territorio(self, territorio_id: int) -> list[Asignacion]:
        """Retorna todas las asignaciones de un territorio ordenadas por fecha."""
        ...


# ─────────────────────────────────────────────
# 2. Implementación SQLAlchemy
# ─────────────────────────────────────────────

class AsignacionRepository:
    """
    Implementación concreta del repositorio de asignaciones.
    Recibe Session como argumento → sin conexiones propias (DI).

    Nota sobre flush() vs commit():
      flush() escribe en la transacción activa sin confirmarla.
      El commit lo hace el servicio (o la sesión del request en FastAPI).
      Esto permite que múltiples operaciones en una misma request
      sean atómicas: si falla cualquiera, todo el bloque hace rollback.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def crear(
        self,
        territorio_id: int,
        conductor_id: int,
        fecha_asignado: date,
        fecha_completado: Optional[date],
        cantidad_abarcado: str,
    ) -> Asignacion:
        asignacion = Asignacion(
            territorio_id=territorio_id,
            conductor_id=conductor_id,
            fecha_asignado=fecha_asignado,
            fecha_completado=fecha_completado,
            cantidad_abarcado=cantidad_abarcado,
        )
        self.db.add(asignacion)
        self.db.flush()  # popula asignacion.id sin cerrar la transacción
        return asignacion

    def obtener_por_id(self, asignacion_id: int) -> Asignacion | None:
        return self.db.get(Asignacion, asignacion_id)

    def listar_por_territorio(self, territorio_id: int) -> list[Asignacion]:
        return (
            self.db.query(Asignacion)
            .filter(Asignacion.territorio_id == territorio_id)
            .order_by(Asignacion.fecha_asignado.asc().nullslast())
            .all()
        )