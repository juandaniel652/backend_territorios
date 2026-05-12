from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from core.database import Base

class NombrePlanilla(Base):
    __tablename__ = "nombres_planillas"

    id = Column(Integer, primary_key=True, index=True)
    zona = Column(Integer, nullable=False)
    ciclo = Column(Integer, nullable=False)
    nombre_planilla = Column(String, nullable=False)
    anio = Column(Integer, nullable=False)

    # Opcional: relación inversa para ver qué asignaciones tiene esta planilla
    asignaciones = relationship("Asignacion", back_populates="planilla")

    def __repr__(self) -> str:
        return f"<NombrePlanilla {self.nombre_planilla} Ciclo={self.ciclo}>"