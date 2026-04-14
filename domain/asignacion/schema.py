"""
domain/asignacion/schema.py
"""

from pydantic import BaseModel, ConfigDict, field_validator
from datetime import date
from typing import Optional


class AsignacionCreate(BaseModel):
    numero_territorio: int
    conductor: str
    fecha_asignado: date
    fecha_completado: Optional[date] = None
    cantidad_abarcado: str

    @field_validator("conductor")
    @classmethod
    def conductor_no_vacio(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("El nombre del conductor no puede estar vacío")
        return v

    @field_validator("fecha_completado")
    @classmethod
    def completado_posterior_a_asignado(
        cls, v: Optional[date], info
    ) -> Optional[date]:
        if v and "fecha_asignado" in info.data:
            if v < info.data["fecha_asignado"]:
                raise ValueError(
                    "fecha_completado no puede ser anterior a fecha_asignado"
                )
        return v


# ── NUEVO ────────────────────────────────────────────────────────────────────
class AsignacionUpdate(BaseModel):
    """
    Input para PUT /asignaciones/{id}.
    Todos los campos son opcionales — solo se actualizan los que llegan.
    El conductor se resuelve por nombre igual que en Create.
    """
    conductor: Optional[str] = None
    fecha_asignado: Optional[date] = None
    fecha_completado: Optional[date] = None
    cantidad_abarcado: Optional[str] = None

    @field_validator("conductor")
    @classmethod
    def conductor_no_vacio(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip()
            if not v:
                raise ValueError("El nombre del conductor no puede estar vacío")
        return v

    @field_validator("fecha_completado")
    @classmethod
    def completado_posterior_a_asignado(
        cls, v: Optional[date], info
    ) -> Optional[date]:
        if v and "fecha_asignado" in info.data and info.data["fecha_asignado"]:
            if v < info.data["fecha_asignado"]:
                raise ValueError(
                    "fecha_completado no puede ser anterior a fecha_asignado"
                )
        return v


class AsignacionOut(BaseModel):
    """Representación completa de una asignación para respuestas de la API."""
    id: int
    territorio_id: int
    conductor_id: int
    conductor_nombre: Optional[str] = None   # enriquecido en service
    fecha_asignado: Optional[date] = None
    fecha_completado: Optional[date] = None
    cantidad_abarcado: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class AsignacionCreatedOut(BaseModel):
    """Respuesta de confirmación tras POST /asignaciones."""
    message: str
    asignacion_id: int
    conductor_creado: bool


class AsignacionUpdatedOut(BaseModel):
    """Respuesta de confirmación tras PUT /asignaciones/{id}."""
    message: str
    asignacion_id: int


class AsignacionDeletedOut(BaseModel):
    """Respuesta de confirmación tras DELETE /asignaciones/{id}."""
    message: str
    asignacion_id: int


class ItemAgendaConfirmar(BaseModel):
    territorio_id: int
    fecha_asignado: date
    turno: str  # "AM" o "PM"
    conductor: str  
    encuentro: str


class AgendaConfirmar(BaseModel):
    items: list[ItemAgendaConfirmar]
    conductor_default: str = "Sin Asignar" # Por si el usuario no eligió conductores todavía