"""
domain/asignacion/model.py

Modelo ORM del dominio Asignacion.
Es el centro del esquema relacional: referencia a Territorio y Conductor.

Agrega relationships bidireccionales para permitir joins ORM
y navegación desde cualquier lado del grafo de objetos.

Nota sobre los ForeignKey: apuntan a los __tablename__ reales de la DB
("territorios", "conductores"), no a las clases Python. Esto es correcto
y desacopla el modelo de los nombres de clase.
"""

from sqlalchemy import Column, Integer, String, Date, ForeignKey
from sqlalchemy.orm import relationship
from core.database import Base


class Asignacion(Base):
    __tablename__ = "asignaciones"

    id            = Column(Integer, primary_key=True, index=True)
    territorio_id = Column(Integer, ForeignKey("territorios.id"), nullable=False, index=True)
    conductor_id  = Column(Integer, ForeignKey("conductores.id"), nullable=False, index=True)
    fecha_asignado   = Column(Date, nullable=True)
    fecha_completado = Column(Date, nullable=True)
    cantidad_abarcado = Column(String, nullable=True)

    # ── Relationships ────────────────────────────────────────────────────────
    # Permiten acceder a obj.territorio y obj.conductor sin queries adicionales
    # cuando ya están cargados en la sesión activa.
    territorio = relationship(
        "Territorio",
        back_populates="asignaciones",
        lazy="select",
    )
    conductor = relationship(
        "Conductor",
        back_populates="asignaciones",
        lazy="select",
    )

    def __repr__(self) -> str:
        return (
            f"<Asignacion id={self.id} "
            f"territorio_id={self.territorio_id} "
            f"conductor_id={self.conductor_id}>"
        )