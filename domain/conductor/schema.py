"""
domain/conductor/schema.py

Contratos de datos del dominio Conductor.

Por ahora el dominio es simple: Conductor se crea implícitamente
cuando se registra una asignación (si no existe, se inserta).
No hay endpoint CRUD de conductores todavía, pero los schemas
están listos para cuando se agregue.
"""

from pydantic import BaseModel, ConfigDict


class ConductorOut(BaseModel):
    """Representación pública de un conductor."""
    id: int
    nombre_completo: str

    model_config = ConfigDict(from_attributes=True)


class ConductorCreate(BaseModel):
    """Input para crear un conductor explícitamente (futuro endpoint)."""
    nombre_completo: str