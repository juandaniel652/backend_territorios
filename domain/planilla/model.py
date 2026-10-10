from sqlalchemy import Column, Integer, String
from core.database import Base

class NombrePlanilla(Base):
    __tablename__ = "nombres_planillas"

    id = Column(Integer, primary_key=True, index=True)
    zona = Column(Integer, nullable=False)
    ciclo = Column(Integer, nullable=False)
    nombre_planilla = Column(String, nullable=True)
    anio = Column(Integer, nullable=True)
    codigo = Column(Integer, unique=True, nullable=False)
    spreadsheet_id = Column(String, nullable=False)