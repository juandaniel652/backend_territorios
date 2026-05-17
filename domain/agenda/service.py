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
        """
        Genera la propuesta de agenda quincenal basada en la plantilla de 10 bloques fijos,
        consumiendo los territorios de Supabase por orden estricto de atraso (urgencia).
        """
        lunes_semanas = self._obtener_inicios_de_semana()
        propuesta_completa = []

        # Fuente de verdad: unimos territorios con sus asignaciones reales completadas
        sql = text("""
            SELECT 
                t.id, t.numero, t.permite_am, t.permite_pm,
                COALESCE(MAX(a.fecha_completado), '1970-01-01'::date) as ultima_fecha
            FROM territorios t
            LEFT JOIN asignaciones a ON t.id = a.territorio_id
            WHERE t.zona = :zona
            GROUP BY t.id, t.numero, t.permite_am, t.permite_pm
            ORDER BY ultima_fecha ASC, t.numero ASC
        """)
        
        territorios_ordenados = self.db.execute(sql, {"zona": zona}).mappings().all()

        for idx_semana, lunes_inicio in enumerate(lunes_semanas, start=1):
            # La plantilla exacta de 10 salidas fijas (offset mapea los días desde el lunes)
            cronograma_semanal = [
                {"offset": 0, "turno": "PM", "label": "Lunes PM"},
                
                {"offset": 1, "turno": "AM", "label": "Martes AM"},
                {"offset": 1, "turno": "PM", "label": "Martes PM"},
                
                {"offset": 2, "turno": "AM", "label": "Miércoles AM"},
                
                {"offset": 3, "turno": "AM", "label": "Jueves AM"},
                {"offset": 3, "turno": "PM", "label": "Jueves PM"},
                
                {"offset": 4, "turno": "AM", "label": "Viernes AM"},
                {"offset": 4, "turno": "PM", "label": "Viernes PM"},
                
                {"offset": 5, "turno": "AM", "label": "Sábado AM"},
                {"offset": 5, "turno": "PM", "label": "Sábado PM"}
            ]

            salidas_semana = []
            # Copiamos la lista para ir consumiendo territorios sin repetir el mismo en la misma semana
            pool_territorios = list(territorios_ordenados)

            for slot in cronograma_semanal:
                fecha_exacta = lunes_inicio + timedelta(days=slot["offset"])
                
                # El algoritmo busca secuencialmente el territorio más urgente que acepte el turno
                territorio_asignado = None
                for t in pool_territorios:
                    cumple_turno = t["permite_am"] if slot["turno"] == "AM" else t["permite_pm"]
                    if cumple_turno:
                        territorio_asignado = t
                        break
                
                # Si encontramos uno que encaje, lo agendamos y lo removemos del pool de esta semana
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