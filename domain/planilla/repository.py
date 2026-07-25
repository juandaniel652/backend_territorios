from sqlalchemy import text
from sqlalchemy.orm import Session

class PlanillaRepository:
    def __init__(self, db: Session):
        self.db = db
        
    def obtener_ultima_planilla_creada(self, zona: int, ciclo_actual: int = None):
        """
        Busca la última planilla registrada para una zona.
        Si se pasa ciclo_actual, busca estrictamente las anteriores a ese ciclo.
        Si no se pasa, trae la más reciente registrada en la DB.
        """
        if ciclo_actual is not None:
            query = text("""
                SELECT nombre_planilla FROM nombres_planillas 
                WHERE zona = :zona AND ciclo < :ciclo_actual
                ORDER BY ciclo DESC LIMIT 1
            """)
            params = {"zona": zona, "ciclo_actual": ciclo_actual}
        else:
            query = text("""
                SELECT nombre_planilla FROM nombres_planillas 
                WHERE zona = :zona
                ORDER BY ciclo DESC LIMIT 1
            """)
            params = {"zona": zona}

        result = self.db.execute(query, params).fetchone()
        return result  # Devuelve la tupla/Row con el atributo .nombre_planilla o None
        
    def obtener_primer_ciclo_del_anio(self, zona: int, anio: int) -> int:
        query = text("""
            SELECT MIN(ciclo) FROM nombres_planillas 
            WHERE zona = :zona AND anio = :anio
        """)
        result = self.db.execute(query, {"zona": zona, "anio": anio}).scalar()
        return result # Devuelve el número de ciclo más bajo o None

    def contar_planillas_por_anio(self, zona: int, anio: int) -> int:
        query = text("""
            SELECT COUNT(*) FROM nombres_planillas 
            WHERE zona = :zona AND anio = :anio
        """)
        result = self.db.execute(query, {"zona": zona, "anio": anio}).scalar()
        return result or 0

    def crear_planilla(self, zona: int, ciclo: int, nombre_planilla: str, anio: int):
        query = text("""
            INSERT INTO nombres_planillas (zona, ciclo, nombre_planilla, anio)
            VALUES (:zona, :ciclo, :nombre, :anio)
            ON CONFLICT (zona, ciclo) DO NOTHING
        """)
        self.db.execute(query, {
            "zona": zona, 
            "ciclo": ciclo, 
            "nombre": nombre_planilla, 
            "anio": anio
        })
        self.db.commit()