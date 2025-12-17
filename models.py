from sqlalchemy import Column, Integer, String, Date, ForeignKey
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class Conductores(Base):
    __tablename__ = "conductores"

    id = Column(Integer, primary_key=True)
    nombre_completo = Column(String, nullable=False)

class Territorios(Base):
    __tablename__ = "territorios"

    id = Column(Integer, primary_key=True)
    numero = Column(Integer, unique=True, nullable=False)

class Asignaciones(Base):
    __tablename__ = "asignaciones"

    id = Column(Integer, primary_key=True)
    territorio_id = Column(Integer, ForeignKey("territorios.id"), nullable=False)
    conductor_id = Column(Integer, ForeignKey("conductores.id"), nullable=False)
    fecha_asignado = Column(Date)
    fecha_completado = Column(Date)
    cantidad_abarcado = Column(String)
