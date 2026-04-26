from sqlalchemy import Column, Integer, Date, ForeignKey, String, Boolean
from sqlalchemy.orm import relationship
from core.database import Base

class Salida(Base):
    __tablename__ = "salidas"

    id = Column(Integer, primary_key=True, index=True)
    territorio_id = Column(Integer, ForeignKey("territorios.id"))
    conductor_id = Column(Integer, ForeignKey("conductores.id"), nullable=True)
    fecha = Column(Date, nullable=False)
    turno = Column(String, nullable=False)
    
    activo = Column(Boolean, default=True)
    
    # AGREGAMOS ESTO:
    punto_encuentro = Column(String, nullable=True) 

    territorio = relationship("Territorio")
    conductor = relationship("Conductor")