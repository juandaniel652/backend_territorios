from sqlalchemy import text
from sqlalchemy.orm import Session

class PlanillaRepository:
    def __init__(self, db: Session):
        self.db = db

    def contar_planillas_por_anio(self, zona: int, anio_actual: int) -> int:
        return self.db.query(PlanillaNombre).filter(
            PlanillaNombre.zona == zona, # <--- ESTE FILTRO ES LA CLAVE
            PlanillaNombre.anio == anio_actual
        ).count()

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