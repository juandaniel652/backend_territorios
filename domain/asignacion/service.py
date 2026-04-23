"""
domain/asignacion/service.py
"""

from fastapi import HTTPException
from sqlalchemy.orm import Session 
from sqlalchemy.exc import IntegrityError
from sqlalchemy import and_, or_, tuple_


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
            # ── 1. Duplicados internos ──
            claves = [(i.territorio_id, i.fecha_asignado, i.turno) for i in data.items]

            if len(claves) != len(set(claves)):
                raise HTTPException(
                    status_code=400,
                    detail="Hay duplicados dentro del mismo envío"
                )

            # ── 2. Precargar conflictos DB (optimizado) ──
            filtros = [
                and_(
                    Salida.territorio_id == i.territorio_id,
                    Salida.fecha == i.fecha_asignado,
                    Salida.turno == i.turno
                )
                for i in data.items
            ]

            existentes = self.db.query(Salida).filter(or_(*filtros)).all()

            conflict_map = {
                (e.territorio_id, e.fecha, e.turno)
                for e in existentes
            }

            nuevas_asignaciones = []
            nuevas_salidas = []
            rechazadas = []
            creadas = []

            # ── 3. Procesamiento item por item ──
            for item in data.items:

                key = (item.territorio_id, item.fecha_asignado, item.turno)

                # conflicto DB
                if key in conflict_map:
                    rechazadas.append({
                        "territorio_id": item.territorio_id,
                        "fecha": item.fecha_asignado.isoformat(),
                        "turno": item.turno,
                        "motivo": "duplicado_en_db"
                    })
                    continue

                conductor, _ = self.conductor_repo.obtener_o_crear(item.conductor)
                territorio = self.territorio_repo.obtener_por_id(item.territorio_id)

                if not territorio:
                    rechazadas.append({
                        "territorio_id": item.territorio_id,
                        "motivo": "territorio_no_existe"
                    })
                    continue

                visitas = self.asignacion_repo.contar_completadas(territorio.id)
                planilla = visitas // 5 + 1
                fila = visitas % 5 + 1

                asignacion = Asignacion(
                    territorio_id=territorio.id,
                    conductor_id=conductor.id,
                    fecha_asignado=item.fecha_asignado,
                    cantidad_abarcado=f"Turno: {item.turno} | Punto: {item.encuentro}",
                    planilla_ciclo=planilla,
                    fila=fila,
                )

                salida = Salida(
                    territorio_id=territorio.id,
                    conductor_id=conductor.id,
                    fecha=item.fecha_asignado,
                    turno=item.turno,
                )

                nuevas_asignaciones.append(asignacion)
                nuevas_salidas.append(salida)

                territorio.ultima_fecha_completado = item.fecha_asignado

                creadas.append({
                    "territorio_id": item.territorio_id,
                    "fecha": item.fecha_asignado.isoformat(),
                    "turno": item.turno
                })

            # ── 4. Persistencia única ──
            self.db.add_all(nuevas_asignaciones)
            self.db.add_all(nuevas_salidas)
            self.db.commit()

            return {
                "status": "partial_success" if rechazadas else "success",
                "creadas": creadas,
                "rechazadas": rechazadas
            }

        except HTTPException:
            self.db.rollback()
            raise

        except Exception as e:
            self.db.rollback()
            raise HTTPException(
                status_code=500,
                detail=f"Error al confirmar agenda: {str(e)}"
        )
    
    # ── Agenda ofrece inteligentemente horario ─────────────────────────────────────────────────────
    
    def buscar_alternativa(self, item, territorios_usados, fecha_min, fecha_max):
        
        candidatos = self.db.query(self.territorio_repo.model).filter(
            self.territorio_repo.model.zona == item.zona,
            ~self.territorio_repo.model.id.in_(territorios_usados)
        ).order_by(
            self.territorio_repo.model.ultima_fecha_completado.asc()
        ).all()

        for t in candidatos:

            conflicto = self.db.query(Salida).filter(
                Salida.territorio_id == t.id,
                Salida.fecha >= fecha_min,
                Salida.fecha <= fecha_max
            ).first()

            if not conflicto:
                return t

        return None
    
    #Uso de gestor inteligente
    
    def confirmar_agenda_inteligente(self, data: AgendaConfirmar) -> dict:
        try:
            nuevas_asignaciones = []
            nuevas_salidas = []
            reemplazos = []

            territorios_usados = set()

            fechas = [i.fecha_asignado for i in data.items]
            fecha_min = min(fechas)
            fecha_max = max(fechas)

            for item in data.items:

                conflicto = self.db.query(Salida).filter(
                    Salida.territorio_id == item.territorio_id,
                    Salida.fecha == item.fecha_asignado,
                    Salida.turno == item.turno
                ).first()

                territorio_final = item.territorio_id

                if conflicto:
                    alternativa = self.buscar_alternativa(
                        item,
                        territorios_usados,
                        fecha_min,
                        fecha_max
                    )

                    if alternativa:
                        reemplazos.append({
                            "territorio_original": item.territorio_id,
                            "territorio_nuevo": alternativa.id,
                            "fecha": item.fecha_asignado.isoformat(),
                            "turno": item.turno
                        })

                        territorio_final = alternativa.id
                    else:
                        continue  # o lo marcás como conflicto

                territorios_usados.add(territorio_final)

                # conductor
                conductor, _ = self.conductor_repo.obtener_o_crear(item.conductor)

                # territorio
                territorio = self.territorio_repo.obtener_por_id(territorio_final)

                visitas = self.asignacion_repo.contar_completadas(territorio.id)
                planilla = visitas // 5 + 1
                fila = visitas % 5 + 1

                asignacion = Asignacion(
                    territorio_id=territorio.id,
                    conductor_id=conductor.id,
                    fecha_asignado=item.fecha_asignado,
                    cantidad_abarcado=f"Turno: {item.turno} | Punto: {item.encuentro}",
                    planilla_ciclo=planilla,
                    fila=fila,
                )

                salida = Salida(
                    territorio_id=territorio.id,
                    conductor_id=conductor.id,
                    fecha=item.fecha_asignado,
                    turno=item.turno,
                )

                nuevas_asignaciones.append(asignacion)
                nuevas_salidas.append(salida)

                territorio.ultima_fecha_completado = item.fecha_asignado

            self.db.add_all(nuevas_asignaciones)
            self.db.add_all(nuevas_salidas)
            self.db.commit()

            return {
                "status": "success",
                "asignaciones": len(nuevas_asignaciones),
                "salidas": len(nuevas_salidas),
                "reemplazos": reemplazos
            }

        except Exception as e:
            self.db.rollback()
            raise HTTPException(500, str(e))

    # ── Muestra Preview Agenda para su vista en backend─────────────────────────────────────────────────────

    def preview_agenda(self, data: AgendaConfirmar) -> dict:
        creadas = []
        rechazadas = []

        claves = [(i.territorio_id, i.fecha_asignado, i.turno) for i in data.items]

        existentes = self.db.query(Salida).filter(
            tuple_(Salida.territorio_id, Salida.fecha, Salida.turno).in_(claves)
        ).all()

        conflict_map = {
            (e.territorio_id, e.fecha, e.turno)
            for e in existentes
        }

        for item in data.items:

            key = (item.territorio_id, item.fecha_asignado, item.turno)

            if key in conflict_map:
                rechazadas.append({
                    "territorio_id": item.territorio_id,
                    "fecha": item.fecha_asignado.isoformat(),
                    "turno": item.turno,
                    "motivo": "ocupado_en_db"
                })
                continue

            territorio = self.territorio_repo.obtener_por_id(item.territorio_id)

            if not territorio:
                rechazadas.append({
                    "territorio_id": item.territorio_id,
                    "motivo": "no_existe"
                })
                continue

            creadas.append({
                "territorio_id": item.territorio_id,
                "fecha": item.fecha_asignado.isoformat(),
                "turno": item.turno,
                "estado": "disponible"
            })

        return {
            "status": "preview",
            "creadas": creadas,
            "rechazadas": rechazadas,
            "resumen": {
                "total": len(data.items),
                "disponibles": len(creadas),
                "ocupadas": len(rechazadas)
            }
        }

    # ── Eliminar ──────────────────────────────────────────────────────
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
        
        