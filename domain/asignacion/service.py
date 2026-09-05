from datetime import date
from fastapi import HTTPException, status
from sqlalchemy.orm import Session 
from sqlalchemy import and_, or_

from domain.asignacion.repository import AsignacionRepositoryProtocol
from domain.asignacion.schema import (
    AsignacionCreate,
    AsignacionUpdate,
    AsignacionUpdatedOut,
    AsignacionDeletedOut,
    AgendaConfirmar,
)
from domain.conductor.repository import ConductorRepositoryProtocol
from domain.territorio.repository import TerritorioRepositoryProtocol
from domain.asignacion.model import Asignacion
from domain.salida.repository import SalidaRepository
from domain.salida.model import Salida
from domain.planilla.repository import PlanillaRepository
from domain.planilla.service import PlanillaService
from domain.territorio.service import TerritorioService
from domain.asignacion.response_builder import AgendaResponseBuilder
from domain.planilla.model import NombrePlanilla
from core.utils import obtener_anio_servicio


class AsignacionService:

    def __init__(
        self,
        db: Session,
        planilla_repo: PlanillaRepository,
        territorio_service: TerritorioService,
        asignacion_repo: AsignacionRepositoryProtocol,
        territorio_repo: TerritorioRepositoryProtocol,
        conductor_repo: ConductorRepositoryProtocol,
        salida_repo: SalidaRepository,
        planilla_service: PlanillaService = None,
    ) -> None:
        self.db = db
        self.planilla_repo = planilla_repo
        self.territorio_service = territorio_service
        self.asignacion_repo = asignacion_repo
        self.territorio_repo = territorio_repo
        self.conductor_repo = conductor_repo
        self.salida_repo = salida_repo
        self.planilla_service = planilla_service

    def _resolver_o_crear_planilla(self, zona: str, ciclo: int, fecha_ref: date) -> tuple[int, str]:
        """Obtiene el ID y nombre exacto de la planilla desde la DB según zona y ciclo."""
        planilla_existente = (
            self.db.query(NombrePlanilla)
            .filter(NombrePlanilla.zona == zona, NombrePlanilla.ciclo == ciclo)
            .first()
        )

        if planilla_existente:
            return planilla_existente.id, planilla_existente.nombre_planilla

        nombre_autogenerado = self.territorio_service.obtener_nombre_dinamico(
            zona=zona, 
            ciclo=ciclo
        )
        anio_servicio = obtener_anio_servicio(fecha_ref)

        nueva_planilla = NombrePlanilla(
            zona=zona,
            ciclo=ciclo,
            nombre_planilla=nombre_autogenerado,
            anio=anio_servicio
        )
        self.db.add(nueva_planilla)
        self.db.flush()
        return nueva_planilla.id, nombre_autogenerado

    def crear_asignacion(self, data: AsignacionCreate):
        territorio = self.territorio_repo.obtener_por_numero(data.numero_territorio)
        if not territorio:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"El territorio número {data.numero_territorio} no existe."
            )

        conductor_nombre_clean = data.conductor.strip()
        conductor, conductor_creado = self.conductor_repo.obtener_o_crear(conductor_nombre_clean)

        estado_vista = self.territorio_repo.obtener_estado_detallado(territorio.numero)
        
        if estado_vista:
            if "proximo_ciclo" in estado_vista:
                ciclo_calculado = estado_vista["proximo_ciclo"]
            else:
                actual_c = estado_vista["ciclo_actual"]
                fila_calc = estado_vista["proxima_fila"]
                ciclo_calculado = actual_c + 1 if fila_calc == 1 and estado_vista.get("total_salidas", 0) > 0 else actual_c
            
            fila_calculada = estado_vista["proxima_fila"]
            zona_territorio = estado_vista["zona"]
        else:
            ciclo_calculado = 1
            fila_calculada = 1
            zona_territorio = territorio.zona

        # Garantizamos la entidad de NombrePlanilla
        planilla_id_final, nombre_planilla_final = self._resolver_o_crear_planilla(
            zona=zona_territorio,
            ciclo=ciclo_calculado,
            fecha_ref=data.fecha_asignado
        )

        nueva_asignacion = Asignacion(
            territorio_id=territorio.id,
            conductor_id=conductor.id,
            planilla_id=planilla_id_final,
            planilla_ciclo=ciclo_calculado,
            fila=fila_calculada,
            fecha_asignado=data.fecha_asignado,
            fecha_completado=data.fecha_completado,
            cantidad_abarcado=data.cantidad_abarcado
        )

        self.db.add(nueva_asignacion)
        self.db.commit()

        sheets_payload = {
            "numero_territorio": territorio.numero,
            "conductor": conductor_nombre_clean,
            "fecha_asignado": data.fecha_asignado,
            "fecha_completado": data.fecha_completado,
            "cantidad_abarcado": data.cantidad_abarcado,
            "fila": fila_calculada,
            "nombre_planilla": nombre_planilla_final  # <-- NOMBRE EXACTO DE LA BD
        }

        # SINCRONIZACIÓN BISTURÍ CON GOOGLE SHEETS
        if self.planilla_service:
            try:
                self.planilla_service.sincronizar_registro_bisturi(sheets_payload)
            except Exception as e:
                print(f"[WARN] No se pudo sincronizar en Google Sheets: {e}")

        return {
            "message": "Asignación registrada exitosamente con control dinámico de planillas",
            "asignacion_id": nueva_asignacion.id,
            "conductor_creado": conductor_creado,
            "sheets_payload": sheets_payload
        }

    def resolver_agenda(self, items):
        creables = []
        rechazadas = []

        claves = [(i.territorio_id, i.fecha_asignado, i.turno) for i in items]
        if len(claves) != len(set(claves)):
            raise HTTPException(
                status_code=400,
                detail="Hay duplicados dentro del mismo envío"
            )

        filtros = [
            and_(
                Salida.territorio_id == i.territorio_id,
                Salida.fecha == i.fecha_asignado,
                Salida.turno == i.turno
            )
            for i in items
        ]

        existentes = self.db.query(Salida).filter(or_(*filtros)).all()
        conflictos_set = {(e.territorio_id, e.fecha, e.turno) for e in existentes}

        for item in items:
            key = (item.territorio_id, item.fecha_asignado, item.turno)

            if key in conflictos_set:
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
                    "motivo": "territorio_invalido"
                })
                continue

            conductor, _ = self.conductor_repo.obtener_o_crear(item.conductor)

            # --- CORRECCIÓN DE CÁLCULO DE CICLO Y FILA BASADO EN LA VISTA ---
            estado_vista = self.territorio_repo.obtener_estado_detallado(territorio.numero)
            if estado_vista:
                ciclo_calculado = estado_vista.get("proximo_ciclo", estado_vista.get("ciclo_actual", 1))
                fila_calculada = estado_vista.get("proxima_fila", 1)
                zona_territorio = estado_vista.get("zona", territorio.zona)
            else:
                ciclo_calculado = 1
                fila_calculada = 1
                zona_territorio = territorio.zona

            planilla_id, nombre_planilla = self._resolver_o_crear_planilla(
                zona=zona_territorio,
                ciclo=ciclo_calculado,
                fecha_ref=item.fecha_asignado
            )

            asignacion = Asignacion(
                territorio_id=territorio.id,
                conductor_id=conductor.id,
                planilla_id=planilla_id,
                planilla_ciclo=ciclo_calculado,
                fila=fila_calculada,
                fecha_asignado=item.fecha_asignado,
                cantidad_abarcado=f"Turno: {item.turno} | Punto: {item.encuentro}",
            )

            salida = Salida(
                territorio_id=territorio.id,
                conductor_id=conductor.id,
                fecha=item.fecha_asignado,
                turno=item.turno,
            )

            creables.append({"asignacion": asignacion, "salida": salida})

        return {
            "ok": creables,
            "fail": rechazadas,
            "meta": {
                "total": len(items),
                "ok": len(creables),
                "fail": len(rechazadas)
            }
        }

    # Resto de métodos de la clase (sin cambios...)
    def actualizar_asignacion(self, asignacion_id: int, data: AsignacionUpdate) -> AsignacionUpdatedOut:
        try:
            asignacion = self.asignacion_repo.obtener_por_id(asignacion_id)
            if not asignacion:
                raise HTTPException(status_code=404, detail=f"Asignación {asignacion_id} no encontrada")

            nuevo_conductor_id = None
            if data.conductor is not None:
                conductor, _ = self.conductor_repo.obtener_o_crear(data.conductor)
                nuevo_conductor_id = conductor.id

            ya_estaba_completada = asignacion.fecha_completado is not None

            updated_asignacion = self.asignacion_repo.actualizar(
                asignacion=asignacion,
                conductor_id=nuevo_conductor_id,
                fecha_asignado=data.fecha_asignado,
                fecha_completado=data.fecha_completado,
                cantidad_abarcado=data.cantidad_abarcado,
            )
            
            if not ya_estaba_completada and data.fecha_completado:
                self.db.commit()
                self._verificar_y_crear_proxima_planilla(updated_asignacion.territorio_id)
            else:
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

    def _verificar_y_crear_proxima_planilla(self, territorio_id: int):
        estado = self.territorio_service.obtener_estado_planilla(territorio_id)

        if estado.total_salidas % 5 == 0:
            zona = self.territorio_repo.obtener_zona(territorio_id)
            proximo_ciclo = estado.proximo_ciclo
            nuevo_nombre = self.territorio_service.obtener_nombre_dinamico(zona, proximo_ciclo)
            
            self.planilla_repo.crear_planilla(
                zona=zona,
                ciclo=proximo_ciclo,
                nombre_planilla=nuevo_nombre,
                anio=obtener_anio_servicio()
            )

    def confirmar_agenda_masiva(self, data: AgendaConfirmar) -> dict:
        resultado = self.resolver_agenda(data.items)
        ok = resultado["ok"]

        self.db.add_all([c["asignacion"] for c in ok])
        self.db.add_all([c["salida"] for c in ok])
        self.db.commit()

        return AgendaResponseBuilder.build(
            status="partial_success",
            ok=[
                {
                    "territorio_id": c["asignacion"].territorio_id,
                    "fecha": c["asignacion"].fecha_asignado.isoformat(),
                    "turno": c["salida"].turno,
                }
                for c in ok
            ],
            fail=resultado["fail"],
            meta=resultado["meta"],
        )

    def buscar_alternativa(self, item, territorios_usados, fecha_min, fecha_max):
        candidatos = self.db.query(self.territorio_repo.model).filter(
            self.territorio_repo.model.zona == item.zona,
            ~self.territorio_repo.model.id.in_(territorios_usados)
        ).all()

        candidatos_ordenados = sorted(
            candidatos, 
            key=lambda t: t.ultima_fecha_completado or date.min
        )

        for t in candidatos_ordenados:
            conflicto = self.db.query(Salida).filter(
                Salida.territorio_id == t.id,
                Salida.fecha >= fecha_min,
                Salida.fecha <= fecha_max
            ).first()

            if not conflicto:
                return t

        return None

    def confirmar_agenda_inteligente(self, data: AgendaConfirmar) -> dict:
        try:
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
                        continue

                territorios_usados.add(territorio_final)
                conductor, _ = self.conductor_repo.obtener_o_crear(item.conductor)

                salida = Salida(
                    territorio_id=territorio_final,
                    conductor_id=conductor.id,
                    fecha=item.fecha_asignado,
                    turno=item.turno,
                    punto_encuentro=item.encuentro
                )
                nuevas_salidas.append(salida)

            self.db.add_all(nuevas_salidas)
            self.db.commit()

            return {
                "status": "success",
                "total_programado": len(nuevas_salidas),
                "reemplazos": reemplazos,
                "mensaje": "Cronograma quincenal guardado con éxito"
            }

        except Exception as e:
            self.db.rollback()
            raise HTTPException(500, f"Error al procesar la agenda: {str(e)}")

    def preview_agenda(self, data: AgendaConfirmar) -> dict:
        resultado = self.resolver_agenda(data.items)

        ok = [
            {
                "territorio_id": c["asignacion"].territorio_id,
                "fecha": c["asignacion"].fecha_asignado.isoformat(),
                "turno": c["salida"].turno,
            }
            for c in resultado["ok"]
        ]

        return AgendaResponseBuilder.build(
            status="preview",
            ok=ok,
            fail=resultado["fail"],
            meta=resultado["meta"],
        )

    def eliminar_asignacion(self, asignacion_id: int) -> AsignacionDeletedOut:
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

    def obtener_sugerencias(self, rango: int = 3):
        try:
            territorios = self.territorio_repo.obtener_sugerencias_antiguedad(rango=rango)

            return [
                {
                    "id": t.id,
                    "numero": t.numero,
                    "zona": t.zona,
                    "ultima_visita": t.ultima_fecha_completado.isoformat() if t.ultima_fecha_completado else "Nunca",
                    "estado": "disponible"
                }
                for t in territorios
            ]
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error al obtener sugerencias: {str(e)}")

    def completar_asignacion(self, asignacion_id: int):
        asignacion = self.asignacion_repo.completar(asignacion_id)
        estado = self.territorio_service.obtener_estado_planilla(asignacion.territorio_id)

        if estado.total_salidas % 5 == 0:
            self.automatizar_nueva_planilla(estado)

    def automatizar_nueva_planilla(self, estado):
        proximo_ciclo = estado.proximo_ciclo 
        zona = self.territorio_repo.obtener_zona(estado.numero)

        service_planilla = self.planilla_service or self.territorio_service
        nuevo_nombre = service_planilla.obtener_nombre_dinamico(zona, proximo_ciclo)

        self.planilla_repo.crear_planilla(
            zona=zona,
            ciclo=proximo_ciclo,
            nombre_planilla=nuevo_nombre,
            anio=obtener_anio_servicio()
        )