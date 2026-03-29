"""
domain/conductor/model.py

Modelo ORM del dominio Conductor.
Simple pero con relationship hacia Asignaciones para permitir
joins ORM cuando el dominio de asignaciones lo necesite.
"""

from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from core.database import Base


class Conductor(Base):
    __tablename__ = "conductores"

    id = Column(Integer, primary_key=True, index=True)
    nombre_completo = Column(String, nullable=False, index=True)

    # Relación inversa — lazy para no cargar en cada query
    asignaciones = relationship(
        "Asignacion",
        back_populates="conductor",
        lazy="select",
    )

    def __repr__(self) -> str:
        return f"<Conductor id={self.id} nombre='{self.nombre_completo}'>"