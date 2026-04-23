"""
domain/asignacion/service.py
"""

from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import tuple_

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
from domain.asignacion.schema import AgendaConfirmar
from domain.asignacion.model import Asignacion
from domain.salida.repository import SalidaRepository
from domain.salida.model import Salida


class AsignacionService:

    def __init__(
        self,
        db: Session,
        asignacion_repo: AsignacionRepositoryProtocol,
        territorio_repo: TerritorioRepositoryProtocol,
        conductor_repo: ConductorRepositoryProtocol,
        salida_repo: SalidaRepository,
    ) -> None:
        self.db = db
        self.asignacion_repo = asignacion_repo
        self.territorio_repo = territorio_repo
        self.conductor_repo  = conductor_repo
        self.salida_repo = salida_repo

    def crear_asignacion(self, data: AsignacionCreate) -> AsignacionCreatedOut:
        try:
            territorio = self.territorio_repo.obtener_por_numero(data.numero_territorio)

            if not territorio:
                raise HTTPException(
                    status_code=404,
                    detail=f"Territorio {data.numero_territorio} no encontrado",
                )

            # ✔️ ahora sí existe territorio
            visitas = self.asignacion_repo.contar_completadas(territorio.id)

            planilla = visitas // 5 + 1
            fila = visitas % 5 + 1

            conductor, conductor_creado = self.conductor_repo.obtener_o_crear(data.conductor)

            asignacion = self.asignacion_repo.crear(
                territorio_id=territorio.id,
                conductor_id=conductor.id,
                fecha_asignado=data.fecha_asignado,
                fecha_completado=data.fecha_completado,
                cantidad_abarcado=data.cantidad_abarcado,
                planilla_ciclo=planilla,
                fila=fila
            )

            self.db.commit()

        except Exception as e:
            self.db.rollback()
            raise HTTPException(500, f"Error al crear la asignación: {str(e)}")

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
        
    # Agregar a AsignacionService

    def confirmar_agenda_masiva(self, data: AgendaConfirmar) -> dict:
        try:
            
            claves = [(i.territorio_id, i.fecha_asignado, i.turno) for i in data.items]

            existentes = self.db.query(Salida).filter(
                tuple_(Salida.territorio_id, Salida.fecha, Salida.turno).in_(claves)
            ).all()

            if existentes:
                raise HTTPException(
                    status_code=400,
                    detail=f"Ya existe salida para territorio {item.territorio_id} en {item.fecha_asignado} {item.turno}"
                )
            nuevas_asignaciones = []
            nuevas_salidas = []

            for item in data.items:
                # 1. Conductor
                conductor, _ = self.conductor_repo.obtener_o_crear(item.conductor)

                # 2. Territorio (importante validar)
                territorio = self.territorio_repo.obtener_por_id(item.territorio_id)
                if not territorio:
                    continue

                # 3. Calcular planilla automáticamente
                visitas = self.asignacion_repo.contar_completadas(territorio.id)
                planilla = visitas // 5 + 1
                fila = visitas % 5 + 1

                # 4. Crear asignación
                asignacion = Asignacion(
                    territorio_id=territorio.id,
                    conductor_id=conductor.id,
                    fecha_asignado=item.fecha_asignado,
                    cantidad_abarcado=f"Turno: {item.turno} | Punto: {item.encuentro}",
                    planilla_ciclo=planilla,
                    fila=fila,
                )
                nuevas_asignaciones.append(asignacion)

                # 5. Crear salida
                salida = Salida(
                    territorio_id=territorio.id,
                    conductor_id=conductor.id,
                    fecha=item.fecha_asignado,
                )
                nuevas_salidas.append(salida)

                # 6. Actualizar territorio (CLAVE para el motor)
                territorio.ultima_fecha_completado = item.fecha_asignado

            # 7. Persistir TODO junto (transacción única)
            self.db.add_all(nuevas_asignaciones)
            self.db.add_all(nuevas_salidas)

            self.db.commit()

            return {
                "status": "success",
                "asignaciones": len(nuevas_asignaciones),
                "salidas": len(nuevas_salidas),
            }

        except Exception as e:
            self.db.rollback()
            raise HTTPException(
                status_code=500,
                detail=f"Error al confirmar agenda: {str(e)}"
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