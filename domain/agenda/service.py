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

    def _obtener_proximos_domingos(self, fecha_base: date = None) -> list[date]:
        if not fecha_base:
            fecha_base = date.today()
        
        dias_hasta_domingo = (6 - fecha_base.weekday()) % 7
        if dias_hasta_domingo == 0:
            dias_hasta_domingo = 7

        primer_domingo = fecha_base + timedelta(days=dias_hasta_domingo)
        segundo_domingo = primer_domingo + timedelta(days=7)
        return [primer_domingo, segundo_domingo]

    def generar_propuesta_quincenal(self, zona: int, limite_por_domingo: int = 3) -> list[dict]:
        domingos = self._obtener_proximos_domingos()
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

        for domingo in domingos:
            salidas_domingo = []
            cupos_am = 0
            cupos_pm = 0

            for t in territorios_ordenados:
                dias_atraso = (domingo - t["ultima_fecha"]).days
                score_final = 999 if t["ultima_fecha"] == date(1970, 1, 1) else dias_atraso

                if cupos_am < limite_por_domingo and t["permite_am"]:
                    salidas_domingo.append({
                        "territorio_id": t["id"],
                        "numero": t["numero"],
                        "fecha": domingo,
                        "turno": "AM",
                        "score": score_final
                    })
                    cupos_am += 1
                    continue

                if cupos_pm < limite_por_domingo and t["permite_pm"]:
                    salidas_domingo.append({
                        "territorio_id": t["id"],
                        "numero": t["numero"],
                        "fecha": domingo,
                        "turno": "PM",
                        "score": score_final
                    })
                    cupos_pm += 1

                if cupos_am >= limite_por_domingo and cupos_pm >= limite_por_domingo:
                    break

            propuesta_completa.append({
                "fecha_domingo": domingo,
                "salidas": salidas_domingo
            })

        return propuesta_completa

    def confirmar_propuesta(self, items: list[dict]) -> dict:
        try:
            nuevas_salidas = []

            for item in items:
                # 1. Instanciamos las Salidas mapeando tu modelo ORM exacto
                # Dejamos conductor_id en None por defecto tal cual permite tu modelo nullable
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