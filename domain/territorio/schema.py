"""
domain/territorio/schema.py
CAMBIO: AsignacionDeTerritorioOut ahora incluye `id` para que el
frontend pueda editar/eliminar asignaciones por su PK.
"""

from pydantic import BaseModel, ConfigDict
from datetime import date
from typing import Optional


class TerritorioOut(BaseModel):
    """Representación pública de un territorio."""
    id: int
    numero: int
    model_config = ConfigDict(from_attributes=True)


class AsignacionDeTerritorioOut(BaseModel):
    """Shape de cada fila del historial de asignaciones de un territorio."""
    id: int                                # ← NUEVO: PK para editar/eliminar
    conductor: str
    fecha_asignado: Optional[date] = None
    fecha_completado: Optional[date] = None
    cantidad_abarcado: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


class TerritorioConAsignacionesOut(BaseModel):
    """Respuesta completa para GET /territorios/{numero}."""
    territorio: int
    asignaciones: list[AsignacionDeTerritorioOut]
    mensaje: Optional[str] = None


class SugerenciaTerritorio(BaseModel):
    """Shape de cada ítem en la respuesta de sugerencias."""
    numero: int
    ultima_fecha: Optional[date] = None
    dias_atraso: Optional[int] = None
    severidad: str  # "nunca" | "critico" | "alto" | "normal"


class SugerenciasOut(BaseModel):
    """Respuesta completa para GET /territorios/sugerencias."""
    rango: str
    total: int
    sugerencias: list[SugerenciaTerritorio]
    cache: bool = False