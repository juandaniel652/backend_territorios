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

        # 1. Traemos TODOS los territorios de las zonas 1, 2 y 3 juntos ordenados por atraso
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

        # 2. Leemos los bloques de horarios activos desde tu tabla de configuración
        sql_plantilla = text("""
            SELECT dia_semana as offset, turno, label 
            FROM plantilla_horaria 
            WHERE activo = TRUE 
            ORDER BY orden ASC
        """)
        cronograma_semanal = self.db.execute(sql_plantilla).mappings().all()

        # Creamos el pool global unificado
        pool_territorios = list(territorios_ordenados)

        for idx_semana, lunes_inicio in enumerate(lunes_semanas, start=1):
            salidas_semana = []

            for slot in cronograma_semanal:
                fecha_exacta = lunes_inicio + timedelta(days=slot["offset"])
                
                # 🌟 REGLA DE ORO: Identificamos si el bloque actual evaluado es Sábado AM
                # dia_semana = 5 representa al Sábado según el estándar que cargamos
                es_sabado_am = (slot["offset"] == 5 and slot["turno"] == "AM")
                
                territorio_asignado = None
                
                for t in pool_territorios:
                    # A) Validación básica de turno habilitado por el territorio
                    cumple_turno = t["permite_am"] if slot["turno"] == "AM" else t["permite_pm"]
                    
                    # B) Filtro estricto de exclusión de zonas:
                    # Evaluamos si el territorio pertenece al grupo de Sábado AM Estricto
                    es_restringido = (t["zona"] == 3) or (t["zona"] == 2 and 28 <= t["numero"] <= 31)
                    
                    # Si el territorio es restringido pero NO estamos parados en un Sábado AM, pasamos de largo
                    if es_restringido and not es_sabado_am:
                        continue
                    
                    # Si pasó los filtros y el turno coincide, lo elegimos
                    if cumple_turno:
                        territorio_asignado = t
                        break
                
                # Si encontramos un territorio que encaje en el bloque, lo removemos y lo guardamos
                if territorio_asignado:
                    pool_territorios.remove(territorio_asignado)
                    
                    dias_atraso = (fecha_exacta - territorio_asignado["ultima_fecha"]).days
                    score_final = 999 if territorio_asignado["ultima_fecha"] == date(1970, 1, 1) else dias_atraso

                    salidas_semana.append({
                        "territorio_id": territorio_asignado["id"],
                        "numero": territorio_asignado["numero"],
                        "zona": territorio_asignado["zona"], # Agregamos la zona para que React pueda pintarla
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
    