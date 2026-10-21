from sqlalchemy import text
from sqlalchemy.orm import Session

class PlanillaRepository:
    def __init__(self, db: Session):
        self.db = db
        
    def obtener_o_crear_planilla(self, zona: int, ciclo: int, nombre_planilla: str, anio: int) -> int:
        """
        Inserta el nombre exacto calculado por territorioService.
        Si ya existe el par (zona, ciclo), actualiza el nombre_planilla y anio con la versión limpia.
        """
        query = text("""
            INSERT INTO nombres_planillas (zona, ciclo, nombre_planilla, anio)
            VALUES (:zona, :ciclo, :nombre, :anio)
            ON CONFLICT (zona, ciclo) 
            DO UPDATE SET nombre_planilla = EXCLUDED.nombre_planilla, anio = EXCLUDED.anio
            RETURNING id;
        """)
        
        result = self.db.execute(query, {
            "zona": zona, 
            "ciclo": ciclo, 
            "nombre": nombre_planilla, 
            "anio": anio
        })
        self.db.commit()
        return result.scalar()  # Devuelve la tupla/Row con el atributo .nombre_planilla o None
        
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

    def obtener_todas(self) -> list[dict]:
        sql = text("""
            SELECT id, zona, ciclo, nombre_planilla, anio, codigo, spreadsheet_id
            FROM nombres_planillas
            ORDER BY codigo ASC
        """)
        rows = self.db.execute(sql).mappings().all()
        return [dict(row) for row in rows]

    def obtener_total_de_planillas (self) -> int:
        sql = text("SELECT count(*) from nombres_planillas;")
        total = self.db.execute(sql).scalar_one()

        return total
        
    def obtener_total_de_planillas_completadas (self) -> int:
        sql = text("""SELECT COUNT(*) AS total_planillas_cumplidoras
                    FROM (
                        SELECT planilla_id
                        FROM asignaciones 
                        WHERE planilla_id BETWEEN 1 AND 17
                        GROUP BY planilla_id
                        HAVING COUNT(*) = 100
                    ) AS subconsulta;""")
        total = self.db.execute(sql).scalar_one() 

        return total