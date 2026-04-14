"""
domain/asignacion/repository.py
"""

from typing import Protocol, runtime_checkable, Optional
from sqlalchemy.orm import Session
from datetime import date

from domain.asignacion.model import Asignacion


@runtime_checkable
class AsignacionRepositoryProtocol(Protocol):

    def crear(
        self,
        territorio_id: int,
        conductor_id: int,
        fecha_asignado: date,
        fecha_completado: Optional[date],
        cantidad_abarcado: str,
    ) -> Asignacion: ...

    def obtener_por_id(self, asignacion_id: int) -> Asignacion | None: ...

    def listar_por_territorio(self, territorio_id: int) -> list[Asignacion]: ...

    # ── NUEVO ────────────────────────────────────────────────────────────────
    def actualizar(
        self,
        asignacion: Asignacion,
        conductor_id: Optional[int],
        fecha_asignado: Optional[date],
        fecha_completado: Optional[date],
        cantidad_abarcado: Optional[str],
    ) -> Asignacion: ...

    def eliminar(self, asignacion: Asignacion) -> None: ...
    
    def crear_muchos(self, objetos: list[Asignacion]) -> None: ...


class AsignacionRepository:

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
        self.db.flush()
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

    # ── NUEVO ────────────────────────────────────────────────────────────────
    def actualizar(
        self,
        asignacion: Asignacion,
        conductor_id: Optional[int] = None,
        fecha_asignado: Optional[date] = None,
        fecha_completado: Optional[date] = None,
        cantidad_abarcado: Optional[str] = None,
    ) -> Asignacion:
        """
        Actualiza solo los campos que llegaron (patch semántico).
        El objeto ORM se modifica en la sesión activa; el commit
        lo hace el servicio.
        """
        if conductor_id is not None:
            asignacion.conductor_id = conductor_id
        if fecha_asignado is not None:
            asignacion.fecha_asignado = fecha_asignado
        if fecha_completado is not None:
            asignacion.fecha_completado = fecha_completado
        if cantidad_abarcado is not None:
            asignacion.cantidad_abarcado = cantidad_abarcado
        self.db.flush()
        return asignacion

    def crear_muchos(self, objetos: list[Asignacion]) -> None:
        self.db.add_all(objetos)
        self.db.flush()

    def eliminar(self, asignacion: Asignacion) -> None:
        """
        Elimina la asignación. El commit lo hace el servicio.
        """
        self.db.delete(asignacion)
        self.db.flush()