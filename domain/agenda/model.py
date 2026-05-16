"""
domain/agenda/model.py
"""
from sqlalchemy import Column, Integer, Date, String, DateTime, ForeignKey
from sqlalchemy.sql import func
from core.database import Base

class Sugerencia(Base):
    __tablename__ = "sugerencias"

    id = Column(Integer, primary_key=True, index=True)
    territorio_id = Column(Integer, ForeignKey("territorios.id"), nullable=False)
    fecha = Column(Date, nullable=True)
    score = Column(Integer, nullable=True)
    estado = Column(String, nullable=True)  # Ej: "propuesto", "aceptado"
    created_at = Column(DateTime, server_default=func.now())