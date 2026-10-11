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
from core.horarios_config import SEMANA_NORMAL, SEMANAS_ESPECIALES
from core.conductores_disponibilidad import DISPONIBILIDAD_CONDUCTORES


class AgendaQuincenalService:

    def __init__(self, db: Session):
        self.db = db
        self.salida_repo = SalidaRepository(db)

    def _obtener_inicios_de_semana(self, fecha_base: date = None) -> list[date]:
        """Calcula el lunes de la semana que viene (Semana 1) y el de la siguiente (Semana 2)."""
        if not fecha_base:
            fecha_base = date.today()
        
        dias_hasta_lunes = (0 - fecha_base.weekday()) % 7
        if dias_hasta_lunes == 0:
            dias_hasta_lunes = 7  

        primer_lunes = fecha_base + timedelta(days=dias_hasta_lunes)
        segundo_lunes = primer_lunes + timedelta(days=7)
        return [primer_lunes, segundo_lunes]

    def _resolver_cronograma_semanal(self, lunes_inicio: date) -> list[dict]:
        domingo_ancla = lunes_inicio - timedelta(days=1)
        
        if domingo_ancla in SEMANAS_ESPECIALES:
            patron_activo = SEMANAS_ESPECIALES[domingo_ancla]["patron"]
            print(f"✨ [SEMANA ESPECIAL] Aplicando {SEMANAS_ESPECIALES[domingo_ancla]['nombre']} para ancla {domingo_ancla}")
        else:
            patron_activo = SEMANA_NORMAL

        sql_plantilla = text("""
            SELECT dia_semana as offset, turno, label, orden
            FROM plantilla_horaria 
            ORDER BY orden ASC
        """)
        slots_totales = self.db.execute(sql_plantilla).mappings().all()

        cronograma_filtrado = []
        for slot in slots_totales:
            key = (slot["offset"], slot["turno"])
            esta_activo = patron_activo.get(key, False)
            
            if esta_activo:
                cronograma_filtrado.append({
                    "offset": slot["offset"],
                    "turno": slot["turno"],
                    "label": slot["label"]
                })

        return cronograma_filtrado

    def generar_propuesta_quincenal_combinada(self) -> dict:
        import random
        lunes_semanas = self._obtener_inicios_de_semana()
        propuesta_completa = []

        mapeo_horarios = {
            "Lunes AM": "Lunes 10:00 hs",
            "Lunes PM": "Lunes 16:00 hs",
            "Martes AM": "Martes 10:00 hs",
            "Martes PM": "Martes 16:00 hs",
            "Miércoles AM": "Miércoles 10:00 hs",
            "Miércoles PM": "Miércoles 16:00 hs",
            "Jueves AM": "Jueves 10:00 hs",
            "Jueves PM": "Jueves 16:00 hs",
            "Viernes AM": "Viernes 10:00 hs",
            "Viernes PM": "Viernes 16:00 hs",
            "Sábado AM": "Sábado 10:00 hs",
            "Sábado PM": "Sábado 16:00 hs",
            "Domingo AM": "Domingo 10:00 hs",
            "Domingo PM": "Domingo 16:00 hs",
        }

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

        # Traemos todos los conductores de la base de datos
        sql_conductores = text("SELECT id, nombre_completo FROM conductores ORDER BY nombre_completo ASC")
        conductores_pool = self.db.execute(sql_conductores).mappings().all()

        # Obtenemos el histórico de asignaciones previas por conductor para balancear la carga
        sql_conteo = text("""
            SELECT conductor_id, COUNT(*) as total 
            FROM salidas 
            WHERE conductor_id IS NOT NULL 
            GROUP BY conductor_id
        """)
        conteo_asignaciones = {row["conductor_id"]: row["total"] for row in self.db.execute(sql_conteo).mappings().all()}

        pool_territorios = list(territorios_ordenados)

        for idx_semana, lunes_inicio in enumerate(lunes_semanas, start=1):
            salidas_semana = []
            cronograma_semanal = self._resolver_cronograma_semanal(lunes_inicio)

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

                    nombre_bloque_original = slot["label"]
                    horario_formateado = mapeo_horarios.get(nombre_bloque_original, f"{nombre_bloque_original} 10:00 hs")

                    # 🌟 FILTRADO Y CÁLCULO ESTRATÉGICO DE CONDUCTORES APTOS
                    offset_dia = slot["offset"]  # 0 a 6
                    turno_slot = slot["turno"]   # "AM" o "PM"

                    conductores_aptos = []
                    for c in conductores_pool:
                        nombre = c["nombre_completo"]
                        config_conductor = DISPONIBILIDAD_CONDUCTORES.get(nombre)

                        if not config_conductor:
                            continue

                        turnos_por_dia = config_conductor["turnos"].get(offset_dia, [])
                        if turno_slot in turnos_por_dia:
                            # Calculamos escasez (cuántos turnos totales puede hacer en toda la semana)
                            escasez_total = sum(len(t_list) for t_list in config_conductor["turnos"].values())
                            
                            conductores_aptos.append({
                                "id": c["id"],
                                "nombre_completo": nombre,
                                "sexo": config_conductor["sexo"],
                                "escasez": escasez_total,
                                "asignaciones_previas": conteo_asignaciones.get(c["id"], 0)
                            })

                    # Ordenamiento estratégico o Aleatorio para Sábados AM
                    if es_sabado_am:
                        random.shuffle(conductores_aptos)
                    else:
                        conductores_aptos.sort(key=lambda x: (
                            x["escasez"],               # 1. Menos disponibilidad general primero (ej. Karolaine)
                            x["asignaciones_previas"],  # 2. Menor cantidad histórica de salidas
                            0 if x["sexo"] == "masculino" else 1 # 3. Prioridad masculina como desempate
                        ))

                    # Seleccionamos estratégicamente al primero de la lista como sugerencia por defecto
                    conductor_default = conductores_aptos[0] if conductores_aptos else None

                    salidas_semana.append({
                        "fecha": fecha_exacta.strftime("%Y-%m-%d"),
                        "horario": horario_formateado,
                        "territorio_id": territorio_assigned["id"],
                        "territorio_numero": territorio_assigned["numero"],
                        "zona": territorio_assigned["zona"],
                        "score": score_final,
                        "punto_encuentro": "A confirmar",
                        "conductor_id": conductor_default["id"] if conductor_default else None,
                        "conductor_nombre": conductor_default["nombre_completo"] if conductor_default else "Sin asignar",
                        "conductores_disponibles": conductores_aptos
                    })

            domingo_fin = lunes_inicio + timedelta(days=6)
            meses = {
                1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
                5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
                9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"
            }
            
            if lunes_inicio.month == domingo_fin.month:
                texto_rango = f"Semana del {lunes_inicio.day} al {domingo_fin.day} de {meses[domingo_fin.month]} {domingo_fin.year}"
            else:
                texto_rango = f"Semana del {lunes_inicio.day} de {meses[lunes_inicio.month]} al {domingo_fin.day} de {meses[domingo_fin.month]} {domingo_fin.year}"

            propuesta_completa.append({
                "semana_numero": idx_semana,
                "rango_fechas": texto_rango,
                "salidas": salidas_semana
            })

        return {
            "propuesta": propuesta_completa
        }

    def confirmar_propuesta(self, items: list[dict]) -> dict:
        try:
            nuevas_salidas = []
            for item in items:
                nueva_salida = Salida(
                    territorio_id=item["territorio_id"],
                    conductor_id=item.get("conductor_id"),  
                    fecha=item["fecha"],
                    turno=item["turno"],
                    punto_encuentro=item.get("punto_encuentro", "Salón del Reino"),
                    activo=True
                )
                nuevas_salidas.append(nueva_salida)

                nueva_sugerencia = Sugerencia(
                    territorio_id=item["territorio_id"],
                    fecha=item["fecha"],
                    score=item["score"],
                    estado="propuesto"
                )
                self.db.add(nueva_sugerencia)

            self.salida_repo.crear_muchos(nuevas_salidas)
            self.db.commit()
            return {"status": "success", "message": f"Se grabaron {len(items)} salidas quincenales listas para ofrecer."}
        
        except Exception as e:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error al guardar la agenda quincenal: {str(e)}"
            )
            
    def generar_propuesta_quincenal_combinada(self) -> dict:
        import random
        lunes_semanas = self._obtener_inicios_de_semana()
        propuesta_completa = []

        mapeo_horarios = {
            "Lunes AM": "Lunes 10:00 hs",
            "Lunes PM": "Lunes 16:00 hs",
            "Martes AM": "Martes 10:00 hs",
            "Martes PM": "Martes 16:00 hs",
            "Miércoles AM": "Miércoles 10:00 hs",
            "Miércoles PM": "Miércoles 16:00 hs",
            "Jueves AM": "Jueves 10:00 hs",
            "Jueves PM": "Jueves 16:00 hs",
            "Viernes AM": "Viernes 10:00 hs",
            "Viernes PM": "Viernes 16:00 hs",
            "Sábado AM": "Sábado 10:00 hs",
            "Sábado PM": "Sábado 16:00 hs",
            "Domingo AM": "Domingo 10:00 hs",
            "Domingo PM": "Domingo 16:00 hs",
        }

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

        # Traemos todos los conductores de la base de datos
        sql_conductores = text("SELECT id, nombre_completo FROM conductores ORDER BY nombre_completo ASC")
        conductores_pool = self.db.execute(sql_conductores).mappings().all()

        # Obtenemos el histórico de asignaciones previas por conductor para balancear la carga
        sql_conteo = text("""
            SELECT conductor_id, COUNT(*) as total 
            FROM salidas 
            WHERE conductor_id IS NOT NULL 
            GROUP BY conductor_id
        """)
        conteo_asignaciones = {row["conductor_id"]: row["total"] for row in self.db.execute(sql_conteo).mappings().all()}

        pool_territorios = list(territorios_ordenados)

        for idx_semana, lunes_inicio in enumerate(lunes_semanas, start=1):
            salidas_semana = []
            cronograma_semanal = self._resolver_cronograma_semanal(lunes_inicio)

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

                    nombre_bloque_original = slot["label"]
                    horario_formateado = mapeo_horarios.get(nombre_bloque_original, f"{nombre_bloque_original} 10:00 hs")

                    # 🌟 FILTRADO Y CÁLCULO ESTRATÉGICO DE CONDUCTORES APTOS
                    offset_dia = slot["offset"]  # 0 a 6
                    turno_slot = slot["turno"]   # "AM" o "PM"

                    conductores_aptos = []
                    for c in conductores_pool:
                        nombre = c["nombre_completo"]
                        config_conductor = DISPONIBILIDAD_CONDUCTORES.get(nombre)

                        if not config_conductor:
                            continue

                        turnos_por_dia = config_conductor["turnos"].get(offset_dia, [])
                        if turno_slot in turnos_por_dia:
                            # Calculamos escasez (cuántos turnos totales puede hacer en toda la semana)
                            escasez_total = sum(len(t_list) for t_list in config_conductor["turnos"].values())
                            
                            conductores_aptos.append({
                                "id": c["id"],
                                "nombre_completo": nombre,
                                "sexo": config_conductor["sexo"],
                                "escasez": escasez_total,
                                "asignaciones_previas": conteo_asignaciones.get(c["id"], 0)
                            })

                    # Ordenamiento estratégico o Aleatorio para Sábados AM
                    if es_sabado_am:
                        random.shuffle(conductores_aptos)
                    else:
                        conductores_aptos.sort(key=lambda x: (
                            x["escasez"],               # 1. Menos disponibilidad general primero (ej. Karolaine)
                            x["asignaciones_previas"],  # 2. Menor cantidad histórica de salidas
                            0 if x["sexo"] == "masculino" else 1 # 3. Prioridad masculina como desempate
                        ))

                    # Seleccionamos estratégicamente al primero de la lista como sugerencia por defecto
                    conductor_default = conductores_aptos[0] if conductores_aptos else None

                    salidas_semana.append({
                        "fecha": fecha_exacta.strftime("%Y-%m-%d"),
                        "horario": horario_formateado,
                        "territorio_id": territorio_assigned["id"],
                        "territorio_numero": territorio_assigned["numero"],
                        "zona": territorio_assigned["zona"],
                        "score": score_final,
                        "punto_encuentro": "A confirmar",
                        "conductor_id": conductor_default["id"] if conductor_default else None,
                        "conductor_nombre": conductor_default["nombre_completo"] if conductor_default else "Sin asignar",
                        "conductores_disponibles": conductores_aptos
                    })

            domingo_fin = lunes_inicio + timedelta(days=6)
            meses = {
                1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
                5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
                9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"
            }
            
            if lunes_inicio.month == domingo_fin.month:
                texto_rango = f"Semana del {lunes_inicio.day} al {domingo_fin.day} de {meses[domingo_fin.month]} {domingo_fin.year}"
            else:
                texto_rango = f"Semana del {lunes_inicio.day} de {meses[lunes_inicio.month]} al {domingo_fin.day} de {meses[domingo_fin.month]} {domingo_fin.year}"

            propuesta_completa.append({
                "semana_numero": idx_semana,
                "rango_fechas": texto_rango,
                "salidas": salidas_semana
            })

        return {
            "propuesta": propuesta_completa
        }