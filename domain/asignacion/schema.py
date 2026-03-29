"""
domain/asignacion/schema.py

Contratos de datos del dominio Asignacion.

Problemas del código original:
  1. schemas.py definía AsignacionCreate con campo "total_abaracado" (typo)
  2. asignaciones.py definía su propio AsignacionCrear con "total_abarcado"
  3. Los dos coexistían sin que ninguno se usara consistentemente

Aquí hay un único schema por operación, con nombres correctos y tipado estricto.

Separación Input / Output:
  - AsignacionCreate : lo que recibe el endpoint POST /asignaciones
  - AsignacionOut    : lo que devuelve cualquier endpoint que retorne una asignación
  - AsignacionCreatedOut : respuesta de confirmación tras crear una asignación
"""

from pydantic import BaseModel, ConfigDict, field_validator
from datetime import date
from typing import Optional


class AsignacionCreate(BaseModel):
    """
    Input para POST /asignaciones.

    Reemplaza y unifica:
      - AsignacionCreate de schemas.py (tenía typo en total_abaracado)
      - AsignacionCrear de asignaciones.py
    """
    numero_territorio: int
    conductor: str
    fecha_asignado: date
    fecha_completado: Optional[date] = None
    total_abarcado: str

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


class AsignacionOut(BaseModel):
    """Representación completa de una asignación para respuestas de la API."""
    id: int
    territorio_id: int
    conductor_id: int
    fecha_asignado: Optional[date] = None
    fecha_completado: Optional[date] = None
    cantidad_abarcado: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class AsignacionCreatedOut(BaseModel):
    """Respuesta de confirmación tras POST /asignaciones."""
    message: str
    asignacion_id: int
    conductor_creado: bool  # True si el conductor fue insertado en esta operación