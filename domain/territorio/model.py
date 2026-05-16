"""
domain/territorio/model.py

Modelo ORM del dominio Territorio.
Importa Base desde core/database.py — única fuente de verdad para la metadata.

Agrega relationship() hacia Asignaciones para permitir joins ORM cuando sea necesario,
sin romper la independencia del dominio (es una referencia lazy, no carga nada por defecto).
"""

from sqlalchemy import Column, Integer, Boolean, Date
from sqlalchemy.orm import relationship
from core.database import Base


class Territorio(Base):
    __tablename__ = "territorios"

    id = Column(Integer, primary_key=True, index=True)
    numero = Column(Integer, unique=True, nullable=False, index=True)
    
    zona = Column(Integer, nullable=False, default=1) # 1, 2 o 3
    permite_am = Column(Boolean, default=True)
    permite_pm = Column(Boolean, default=True)

    # Relación inversa — no genera query hasta que se acceda explícitamente
    asignaciones = relationship(
        "Asignacion",
        back_populates="territorio",
        lazy="select",        # carga bajo demanda, no en cada query
    )

    def __repr__(self) -> str:
        return f"<Territorio numero={self.numero}>"