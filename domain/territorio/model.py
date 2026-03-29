"""
domain/territorio/model.py

Modelo ORM del dominio Territorio.
Importa Base desde core/database.py — única fuente de verdad para la metadata.

Agrega relationship() hacia Asignaciones para permitir joins ORM cuando sea necesario,
sin romper la independencia del dominio (es una referencia lazy, no carga nada por defecto).
"""

from sqlalchemy import Column, Integer
from sqlalchemy.orm import relationship
from core.database import Base


class Territorio(Base):
    __tablename__ = "territorios"

    id = Column(Integer, primary_key=True, index=True)
    numero = Column(Integer, unique=True, nullable=False, index=True)

    # Relación inversa — no genera query hasta que se acceda explícitamente
    asignaciones = relationship(
        "Asignacion",
        back_populates="territorio",
        lazy="select",        # carga bajo demanda, no en cada query
    )

    def __repr__(self) -> str:
        return f"<Territorio numero={self.numero}>"