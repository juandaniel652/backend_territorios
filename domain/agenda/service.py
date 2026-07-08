"""
domain/agenda/service.py
"""
from datetime import date, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import text
from fastapi import HTTPException, status

from domain.salida.model import Salida
from domain.agenda.model import Sugerencia  # Tu modelo de auditoría
from domain.salida.repository import SalidaRepository

class AgendaQuincenalService:
    def __init__(self, db: Session):
        self.db = db
        # Reutilizamos tu repositorio de salidas existente
        self.salida_repo = SalidaRepository(db)

    def _obtener_inicios_de_semana(self, fecha_base: date = None) -> list[date]:
        """Calcula el lunes de la semana que viene (Semana 1) y el de la siguiente (Semana 2)."""
        if not fecha_base:
            fecha_base = date.today()
        
        # weekday() en Python: 0=Lunes, 1=Martes, ..., 6=Domingo
        dias_hasta_lunes = (0 - fecha_base.weekday()) % 7
        if dias_hasta_lunes == 0:
            dias_hasta_lunes = 7  # Si hoy ya es lunes, saltamos al próximo lunes del calendario

        primer_lunes = fecha_base + timedelta(days=dias_hasta_lunes)
        segundo_lunes = primer_lunes + timedelta(days=7)
        return [primer_lunes, segundo_lunes]

    def generar_propuesta_quincenal(self, zona: int) -> list[dict]:
        lunes_semanas = self._obtener_inicios_de_semana()
        propuesta_completa = []

        # 1. Traemos los territorios ordenados por urgencia
        sql_territorios = text("""
            SELECT t.id, t.numero, t.permite_am, t.permite_pm,
                   COALESCE(MAX(a.fecha_completado), '1970-01-01'::date) as ultima_fecha
            FROM territorios t
            LEFT JOIN asignaciones a ON t.id = a.territorio_id
            WHERE t.zona = :zona
            GROUP BY t.id, t.numero, t.permite_am, t.permite_pm
            ORDER BY ultima_fecha ASC, t.numero ASC
        """)
        territorios_ordenados = self.db.execute(sql_territorios, {"zona": zona}).mappings().all()

        # 2. 🌟 ¡NUEVO! Traemos la plantilla horaria viva de Supabase
        sql_plantilla = text("""
            SELECT dia_semana as offset, turno, label 
            FROM plantilla_horaria 
            WHERE activo = TRUE 
            ORDER BY orden ASC
        """)
        cronograma_semanal = self.db.execute(sql_plantilla).mappings().all()

        pool_territorios = list(territorios_ordenados)

        for idx_semana, lunes_inicio in enumerate(lunes_semanas, start=1):
            salidas_semana = []

            for slot in cronograma_semanal:
                # slot["offset"] ahora viene directo de la columna dia_semana de la DB!
                fecha_exacta = lunes_inicio + timedelta(days=slot["offset"])
                
                territorio_asignado = None
                for t in pool_territorios:
                    cumple_turno = t["permite_am"] if slot["turno"] == "AM" else t["permite_pm"]
                    if cumple_turno:
                        territorio_asignado = t
                        break
                
                if territorio_asignado:
                    pool_territorios.remove(territorio_asignado)
                    
                    dias_atraso = (fecha_exacta - territorio_asignado["ultima_fecha"]).days
                    score_final = 999 if territorio_asignado["ultima_fecha"] == date(1970, 1, 1) else dias_atraso

                    salidas_semana.append({
                        "territorio_id": territorio_asignado["id"],
                        "numero": territorio_asignado["numero"],
                        "fecha": fecha_exacta,
                        "turno": slot["turno"],
                        "bloque_nombre": slot["label"],
                        "score": score_final
                    })

            propuesta_completa.append({
                "semana_numero": idx_semana,
                "rango_fechas": f"Del {lunes_inicio.strftime('%d/%m')} al {(lunes_inicio + timedelta(days=5)).strftime('%d/%m')}",
                "salidas": salidas_semana
            })

        return propuesta_completa

    def confirmar_propuesta(self, items: list[dict]) -> dict:
        try:
            nuevas_salidas = []

            for item in items:
                # 1. Instanciamos las Salidas mapeando tu modelo ORM exacto
                nueva_salida = Salida(
                    territorio_id=item["territorio_id"],
                    conductor_id=None,  
                    fecha=item["fecha"],
                    turno=item["turno"],
                    punto_encuentro=item.get("punto_encuentro", "Salón del Reino"),
                    activo=True
                )
                nuevas_salidas.append(nueva_salida)

                # 2. Guardamos registro histórico del algoritmo en sugerencias
                nueva_sugerencia = Sugerencia(
                    territorio_id=item["territorio_id"],
                    fecha=item["fecha"],
                    score=item["score"],
                    estado="propuesto"
                )
                self.db.add(nueva_sugerencia)

            # 3. Mandamos la lista completa a tu método batch del repositorio de salidas
            self.salida_repo.crear_muchos(nuevas_salidas)

            # Confirmamos de forma atómica en la transacción de la DB
            self.db.commit()
            return {"status": "success", "message": f"Se grabaron {len(items)} salidas quincenales listas para ofrecer."}
        
        except Exception as e:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error al guardar la agenda quincenal: {str(e)}"
            )
            
    def generar_propuesta_quincenal_combinada(self) -> list[dict]:
        lunes_semanas = self._obtener_inicios_de_semana()
        propuesta_completa = []

        # Diccionario interno de negocio para formatear los horarios reales de la congregación
        mapeo_horarios = {
            "Lunes PM": "Lunes 16:00 hs",
            "Martes AM": "Martes 10:00 hs",
            "Martes PM": "Martes 16:00 hs", # Si llega a haber otro turno, se puede mapear acá
            "Miércoles AM": "Miércoles 10:00 hs",
            "Jueves AM": "Jueves 10:00 hs",
            "Jueves PM": "Jueves 16:00 hs",
            "Viernes AM": "Viernes 10:00 hs",
            "Viernes PM": "Viernes 16:00 hs",
            "Sábado AM": "Sábado 10:00 hs",
            "Sábado PM": "Sábado 16:00 hs"
        }

        # 1. Traemos TODOS los territorios ordenados por su atraso real (score)
        sql_territorios = text("""
            SELECT t.id, t.numero, t.zona, t.permite_am, t.permite_pm,
                   COALESCE(MAX(a.fecha_completado), '1970-01-01'::date) as ultima_fecha
            FROM territorios t
            LEFT JOIN asignaciones a ON t.id = a.territorio_id
            WHERE t.zona IN (1, 2, 3)
            GROUP BY t.id, t.numero, t.zona, t.permite_am, t.permite_pm
            ORDER BY ultima_fecha ASC, t.numero ASC
        """)
        territorios_ordenados = self.db.execute(sql_territorios).mappings().all()

        # 2. Traemos las configuraciones activas de los bloques horarios
        sql_plantilla = text("""
            SELECT dia_semana as offset, turno, label 
            FROM plantilla_horaria 
            WHERE activo = TRUE 
            ORDER BY orden ASC
        """)
        cronograma_semanal = self.db.execute(sql_plantilla).mappings().all()

        # Traemos también una lista de conductores para que el frontend pueda armar un combobox/select si lo necesita
        sql_conductores = text("SELECT id, nombre_completo FROM conductores ORDER BY nombre_completo ASC")
        conductores_pool = self.db.execute(sql_conductores).mappings().all()
        listado_conductores = [{"id": c["id"], "nombre_completo": c["nombre_completo"]} for c in conductores_pool]

        pool_territorios = list(territorios_ordenados)

        for idx_semana, lunes_inicio in enumerate(lunes_semanas, start=1):
            salidas_semana = []

            for slot in cronograma_semanal:
                fecha_exacta = lunes_inicio + timedelta(days=slot["offset"])
                es_sabado_am = (slot["offset"] == 5 and slot["turno"] == "AM")
                
                territorio_assigned = None
                
                for t in pool_territorios:
                    cumple_turno = t["permite_am"] if slot["turno"] == "AM" else t["permite_pm"]
                    es_restringido = (
                        (t["zona"] == 3) or
                        (t["zona"] == 2 and (28 <= t["numero"] <= 31 or 39 <= t["numero"] <= 41))
                    )
                    
                    if es_restringido and not es_sabado_am:
                        continue
                    
                    if cumple_turno:
                        territorio_assigned = t
                        break
                
                if territorio_assigned:
                    pool_territorios.remove(territorio_assigned)
                    
                    dias_atraso = (fecha_exacta - territorio_assigned["ultima_fecha"]).days
                    score_final = 999 if territorio_assigned["ultima_fecha"] == date(1970, 1, 1) else dias_atraso

                    # Formateamos el string del horario estético usando nuestro mapeo seguro
                    nombre_bloque_original = slot["label"]
                    horario_formateado = mapeo_horarios.get(nombre_bloque_original, f"{nombre_bloque_original} 10:00 hs")

                    salidas_semana.append({
                        "fecha": fecha_exacta.strftime("%Y-%m-%d"),
                        "horario": horario_formateado, # 📌 Ej: "Lunes 16:00 hs"
                        "territorio_id": territorio_assigned["id"],
                        "territorio_numero": territorio_assigned["numero"],
                        "zona": territorio_assigned["zona"],
                        "score": score_final,
                        "punto_encuentro": "A confirmar", # Default para que Maxi o el usuario editen en el Front
                        "conductor_id": None,             # Vacío para asignar en el Front
                        "conductor_nombre": "Sin asignar" # Etiqueta inicial clara
                    })

            domingo_fin = lunes_inicio + timedelta(days=6)
            
            # Diccionario para traducir meses a español de forma sencilla
            meses = {
                1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
                5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
                9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"
            }
            
            # Verificamos si el lunes y el domingo caen en el mismo mes
            if lunes_inicio.month == domingo_fin.month:
                texto_rango = f"Semana del {lunes_inicio.day} al {domingo_fin.day} de {meses[domingo_fin.month]} {domingo_fin.year}"
            else:
                texto_rango = f"Semana del {lunes_inicio.day} de {meses[lunes_inicio.month]} al {domingo_fin.day} de {meses[domingo_fin.month]} {domingo_fin.year}"

            propuesta_completa.append({
                "semana_numero": idx_semana, # Lo mantengo por si el backend lo usa, pero en el front usás rango_fechas
                "rango_fechas": texto_rango,
                "salidas": salidas_semana
            })

        # Retornamos la propuesta enriquecida y el listado de conductores útil para los select del frontend
        return {
            "propuesta": propuesta_completa,
            "conductores_disponibles": listado_conductores
        }