"""
domain/asignacion/service.py
"""

from fastapi import HTTPException, status
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
from domain.planilla.repository import PlanillaRepository
from domain.territorio.service import TerritorioService
from domain.asignacion.response_builder import AgendaResponseBuilder
from core.utils import obtener_anio_servicio

from domain.asignacion.schema import AsignacionCreate
from domain.planilla.model import NombrePlanilla


class AsignacionService:

    def __init__(
        self,
        db: Session,
        planilla_repo: PlanillaRepository,
        territorio_service: TerritorioService,
        asignacion_repo: TerritorioRepositoryProtocol, 
        territorio_repo: TerritorioRepositoryProtocol,
        conductor_repo: ConductorRepositoryProtocol,
        salida_repo: SalidaRepository,
    ) -> None:
        self.db = db
        self.planilla_repo = planilla_repo
        self.territorio_service = territorio_service
        self.asignacion_repo = asignacion_repo
        self.territorio_repo = territorio_repo
        self.conductor_repo  = conductor_repo
        self.salida_repo = salida_repo
        
    def crear_asignacion(self, data: AsignacionCreate):
        # 1. Validar que exista el territorio por su número natural
        territorio = self.territorio_repo.obtener_por_numero(data.numero_territorio)
        if not territorio:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"El territorio número {data.numero_territorio} no existe."
            )

        # 2. Resolver Conductor usando tu método semántico 'obtener_o_crear'
        conductor_nombre_clean = data.conductor.strip()
        conductor, conductor_creado = self.conductor_repo.obtener_o_crear(conductor_nombre_clean)

        # 3. Leer el estado exacto desde la vista mediante el repositorio
        estado_vista = self.territorio_repo.obtener_estado_detallado(territorio.numero)
        
        if estado_vista:
            # La vista nos dice exactamente a dónde tiene que apuntar la nueva asignación
            ciclo_calculado = estado_vista["ciclo_actual"]
            fila_calculada = estado_vista["proxima_fila"]
            zona_territorio = estado_vista["zona"]
        else:
            # Fallback seguro por si el territorio no figura todavía en la vista
            ciclo_calculado = 1
            fila_calculada = 1
            zona_territorio = territorio.zona

        # 4. Verificar si ya existe la cabecera de la planilla en nombres_planillas
        planilla_existente = (
            self.db.query(NombrePlanilla)
            .filter(NombrePlanilla.zona == zona_territorio, NombrePlanilla.ciclo == ciclo_calculado)
            .first()
        )

        if planilla_existente:
            planilla_id_final = planilla_existente.id
        else:
            # Si no existe, calculamos el nombre dinámico usando el territorio_service
            nombre_autogenerado = self.territorio_service.obtener_nombre_dinamico(
                zona=zona_territorio, 
                ciclo=ciclo_calculado
            )
            
            # Calculamos el año de servicio basándonos en la fecha de asignación
            anio_servicio = obtener_anio_servicio(data.fecha_asignado)

            # Insertamos la nueva cabecera de la planilla
            nueva_planilla = NombrePlanilla(
                zona=zona_territorio,
                ciclo=ciclo_calculado,
                nombre_planilla=nombre_autogenerado,
                anio=anio_servicio
            )
            self.db.add(nueva_planilla)
            self.db.flush()  # Sincroniza para obtener el ID generado sin cerrar la transacción
            planilla_id_final = nueva_planilla.id

        # 5. Instanciar el objeto de la Asignación
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

        # 6. Persistir en la base de datos de manera atómica
        self.db.add(nueva_asignacion)
        self.db.commit()

        # 7. Retornar la respuesta estructurada que espera AsignacionCreatedOut
        return {
            "message": "Asignación registrada exitosamente con control dinámico de planillas",
            "asignacion_id": nueva_asignacion.id,
            "conductor_creado": conductor_creado
        }
    
    # ── NUEVO: Actualizar ────────────────────────────────────────────────────
    def actualizar_asignacion(self, asignacion_id: int, data: AsignacionUpdate) -> AsignacionUpdatedOut:
        try:
            asignacion = self.asignacion_repo.obtener_por_id(asignacion_id)
            if not asignacion:
                raise HTTPException(status_code=404, detail=f"Asignación {asignacion_id} no encontrada")

            # Resolver conductor solo si cambió
            nuevo_conductor_id = None
            if data.conductor is not None:
                conductor, _ = self.conductor_repo.obtener_o_crear(data.conductor)
                nuevo_conductor_id = conductor.id

            # Guardamos el estado anterior para saber si ya estaba completada
            ya_estaba_completada = asignacion.fecha_completado is not None

            updated_asignacion = self.asignacion_repo.actualizar(
                asignacion=asignacion,
                conductor_id=nuevo_conductor_id,
                fecha_asignado=data.fecha_asignado,
                fecha_completado=data.fecha_completado,
                cantidad_abarcado=data.cantidad_abarcado,
            )
            
            # ¡AUTOMATIZACIÓN! 
            # Si NO estaba completada y AHORA sí tiene fecha_completado
            if not ya_estaba_completada and data.fecha_completado:
                self.db.commit() # Confirmamos para que el conteo de salidas sea correcto
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
        
    # Agregar a AsignacionService
    
    def _verificar_y_crear_proxima_planilla(self, territorio_id: int):
        # Usamos el service que ya perfeccionamos para ver los números reales
        estado = self.territorio_service.obtener_estado_planilla(territorio_id)

        # SI EL TOTAL ES MÚLTIPLO DE 5 (ej: 20), significa que acabamos de terminar la última fila
        if estado.total_salidas % 5 == 0:
            # Buscamos la zona del territorio
            zona = self.territorio_repo.obtener_zona(territorio_id)
            
            # Generamos el nombre dinámico para el PRÓXIMO ciclo
            proximo_ciclo = estado.proximo_ciclo
            nuevo_nombre = self.territorio_service.obtener_nombre_dinamico(zona, proximo_ciclo)
            
            # Guardamos en nombres_planillas para que ya quede "firme" en la DB
            from core.utils import obtener_anio_servicio
            self.planilla_repo.crear_planilla(
                zona=zona,
                ciclo=proximo_ciclo,
                nombre_planilla=nuevo_nombre,
                anio=obtener_anio_servicio()
            )
            print(f"DEBUG: Se creó automáticamente la planilla {nuevo_nombre} para el ciclo {proximo_ciclo}")

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
            nuevas_salidas = []
            reemplazos = []
            territorios_usados = set()

            fechas = [i.fecha_asignado for i in data.items]
            fecha_min = min(fechas)
            fecha_max = max(fechas)

            for item in data.items:
                # Verificar si ya existe una salida programada para ese lugar/fecha/turno
                conflicto = self.db.query(Salida).filter(
                    Salida.territorio_id == item.territorio_id,
                    Salida.fecha == item.fecha_asignado,
                    Salida.turno == item.turno
                ).first()

                territorio_final = item.territorio_id

                # Si hay conflicto, el gestor inteligente busca otro territorio libre
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
                        continue  # Saltear si no hay alternativa disponible

                territorios_usados.add(territorio_final)

                # Resolver conductor por nombre
                conductor, _ = self.conductor_repo.obtener_o_crear(item.conductor)

                # GUARDAR SOLO EN SALIDAS (Este es tu cronograma)
                salida = Salida(
                    territorio_id=territorio_final,
                    conductor_id=conductor.id,
                    fecha=item.fecha_asignado,
                    turno=item.turno,
                    punto_encuentro=item.encuentro
                )
                
                nuevas_salidas.append(salida)

            # Persistir solo las salidas programadas
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
    # ── Muestra Preview Agenda para su vista en backend─────────────────────────────────────────────────────

    def preview_agenda(self, data: AgendaConfirmar) -> dict:
        creadas = []
        rechazadas = []

        #claves = [(i.territorio_id, i.fecha_asignado, i.turno) for i in data.items]

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


    def resolver_agenda(self, items):

        creables = []
        rechazadas = []

        # ── 1. duplicados internos ──
        claves = [
            (i.territorio_id, i.fecha_asignado, i.turno)
            for i in items
        ]

        if len(claves) != len(set(claves)):
            raise HTTPException(
                status_code=400,
                detail="Hay duplicados dentro del mismo envío"
            )

        # ── 2. conflictos en DB ──
        filtros = [
            and_(
                Salida.territorio_id == i.territorio_id,
                Salida.fecha == i.fecha_asignado,
                Salida.turno == i.turno
            )
            for i in items
        ]

        existentes = self.db.query(Salida).filter(or_(*filtros)).all()

        conflictos_set = {
            (e.territorio_id, e.fecha, e.turno)
            for e in existentes
        }

        # ── 3. procesar items ──
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

            creables.append({
                "asignacion": asignacion,
                "salida": salida
            })

        return {
            "ok": creables,
            "fail": rechazadas,
            "meta": {
                "total": len(items),
                "ok": len(creables),
                "fail": len(rechazadas)
            }
        }


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

        fail = resultado["fail"]

        return AgendaResponseBuilder.build(
            status="preview",
            ok=ok,
            fail=fail,
            meta=resultado["meta"],
        )
        
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
        

    def obtener_sugerencias(self, rango: int = 3):
        try:
            # Llamamos al nuevo método del repo
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
        
    
    #____ Planilla ____________________________________________________________

    def completar_asignacion(self, asignacion_id: int):
        # 1. Marcamos la asignación como completada en la DB
        asignacion = self.repo.completar(asignacion_id)

        # 2. Obtenemos el estado actual del territorio para ver si cerró ciclo
        # (Usamos el service de territorio que ya calcula el total_salidas)
        estado = self.territorio_service.obtener_estado_planilla(asignacion.territorio_id)

        # 3. SI EL TOTAL ES MÚLTIPLO DE 5, ¡CERRAMOS PLANILLA!
        if estado.total_salidas % 5 == 0:
            self.automatizar_nueva_planilla(estado)

    def automatizar_nueva_planilla(self, estado):
        # Calculamos los datos de la PRÓXIMA planilla
        proximo_ciclo = estado.proximo_ciclo 
        zona = self.territorio_repo.obtener_zona(estado.numero)

        # Generamos el nombre con el service de planilla
        nuevo_nombre = self.planilla_service.obtener_nombre_dinamico(zona, proximo_ciclo)

        # Guardamos en la tabla 'nombres_planillas'
        self.planilla_repo.crear_planilla(
            zona=zona,
            ciclo=proximo_ciclo,
            nombre_planilla=nuevo_nombre,
            anio=obtener_anio_servicio()
        )