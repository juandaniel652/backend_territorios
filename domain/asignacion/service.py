"""
domain/asignacion/service.py
"""

from fastapi import HTTPException
from sqlalchemy.orm import Session

from domain.asignacion.repository import AsignacionRepositoryProtocol
from domain.asignacion.schema import (
    AsignacionCreate,
    AsignacionUpdate,
    AsignacionCreatedOut,
    AsignacionUpdatedOut,
    AsignacionDeletedOut,
)
from domain.conductor.repository import ConductorRepositoryProtocol
from domain.territorio.repository import TerritorioRepositoryProtocol


class AsignacionService:

    def __init__(
        self,
        db: Session,
        asignacion_repo: AsignacionRepositoryProtocol,
        territorio_repo: TerritorioRepositoryProtocol,
        conductor_repo: ConductorRepositoryProtocol,
    ) -> None:
        self.db = db
        self.asignacion_repo = asignacion_repo
        self.territorio_repo = territorio_repo
        self.conductor_repo  = conductor_repo

    # ── Crear (sin cambios) ──────────────────────────────────────────────────
    def crear_asignacion(self, data: AsignacionCreate) -> AsignacionCreatedOut:
        try:
            territorio = self.territorio_repo.obtener_por_numero(data.numero_territorio)
            if not territorio:
                raise HTTPException(
                    status_code=404,
                    detail=f"Territorio {data.numero_territorio} no encontrado",
                )

            conductor, conductor_creado = self.conductor_repo.obtener_o_crear(data.conductor)

            asignacion = self.asignacion_repo.crear(
                territorio_id=territorio.id,
                conductor_id=conductor.id,
                fecha_asignado=data.fecha_asignado,
                fecha_completado=data.fecha_completado,
                cantidad_abarcado=data.cantidad_abarcado,
            )
            self.db.commit()

        except HTTPException:
            self.db.rollback()
            raise
        except Exception as e:
            self.db.rollback()
            raise HTTPException(status_code=500, detail=f"Error al crear la asignación: {str(e)}") from e

        return AsignacionCreatedOut(
            message="Asignación creada correctamente",
            asignacion_id=asignacion.id,
            conductor_creado=conductor_creado,
        )

    # ── NUEVO: Actualizar ────────────────────────────────────────────────────
    def actualizar_asignacion(
        self, asignacion_id: int, data: AsignacionUpdate
    ) -> AsignacionUpdatedOut:
        """
        Actualiza solo los campos presentes en el payload.
        Si el conductor cambia, se resuelve por nombre (obtener_o_crear).

        Raises:
            404: asignación no encontrada.
            500: error de transacción.
        """
        try:
            asignacion = self.asignacion_repo.obtener_por_id(asignacion_id)
            if not asignacion:
                raise HTTPException(
                    status_code=404,
                    detail=f"Asignación {asignacion_id} no encontrada",
                )

            # Resolver conductor solo si cambió
            nuevo_conductor_id = None
            if data.conductor is not None:
                conductor, _ = self.conductor_repo.obtener_o_crear(data.conductor)
                nuevo_conductor_id = conductor.id

            self.asignacion_repo.actualizar(
                asignacion=asignacion,
                conductor_id=nuevo_conductor_id,
                fecha_asignado=data.fecha_asignado,
                fecha_completado=data.fecha_completado,
                cantidad_abarcado=data.cantidad_abarcado,
            )
            self.db.commit()

        except HTTPException:
            self.db.rollback()
            raise
        except Exception as e:
            self.db.rollback()
            raise HTTPException(status_code=500, detail=f"Error al actualizar: {str(e)}") from e

        return AsignacionUpdatedOut(
            message="Asignación actualizada correctamente",
            asignacion_id=asignacion_id,
        )

    # ── NUEVO: Eliminar ──────────────────────────────────────────────────────
    def eliminar_asignacion(self, asignacion_id: int) -> AsignacionDeletedOut:
        """
        Elimina permanentemente una asignación.

        Raises:
            404: asignación no encontrada.
            500: error de transacción.
        """
        try:
            asignacion = self.asignacion_repo.obtener_por_id(asignacion_id)
            if not asignacion:
                raise HTTPException(
                    status_code=404,
                    detail=f"Asignación {asignacion_id} no encontrada",
                )

            self.asignacion_repo.eliminar(asignacion)
            self.db.commit()

        except HTTPException:
            self.db.rollback()
            raise
        except Exception as e:
            self.db.rollback()
            raise HTTPException(status_code=500, detail=f"Error al eliminar: {str(e)}") from e

        return AsignacionDeletedOut(
            message="Asignación eliminada correctamente",
            asignacion_id=asignacion_id,
        )