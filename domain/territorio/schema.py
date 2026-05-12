"""
domain/territorio/schema.py

Contratos de datos para el dominio Territorio.

Separamos Input / Output explícitamente:
  - TerritorioOut: lo que la API devuelve (nunca expone el id interno directo en listas)
  - AsignacionDeTerritorioOut: shape de cada asignación dentro de GET /territorios/{numero}
  - TerritorioConAsignacionesOut: respuesta completa del endpoint de historial

Esto reemplaza el dict crudo que se armaba directamente en app.py y querys_territorios.py.
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
    """
    Shape de cada fila del historial de asignaciones de un territorio.
    Equivale a lo que antes se construía como dict crudo en app.py.
    """
    id: int
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
    """
    Shape de cada ítem en la respuesta de sugerencias.
    Reemplaza el dict crudo en sugerir_territorios.py.
    """
    numero: int
    ultima_fecha: Optional[date] = None
    dias_atraso: Optional[int] = None
    severidad: str   # "nunca" | "critico" | "alto" | "normal"

class SugerenciasOut(BaseModel):
    """Respuesta completa para GET /territorios/sugerencias."""
    rango: str
    total: int
    sugerencias: list[SugerenciaTerritorio]
    cache: bool = False
    
class AgendaItemIn(BaseModel):
    numero_territorio: int
    fecha_asignado: date
    turno: str
    conductor: str
    encuentro: str

class PropuestaDiaOut(BaseModel):
    """Representa un territorio sugerido para una fecha específica."""
    territorio_id: int
    numero: int
    ultima_fecha: Optional[date] = None
    zona_descripcion: str
    turno_recomendado: str

    model_config = ConfigDict(from_attributes=True)

class PlanQuincenalOut(BaseModel):
    """
    Si decidís mantener la vista quincenal en el futuro, 
    este es el formato que evita errores.
    """
    fecha: date
    turno: str
    territorio_id: int
    numero: int
    zona: int

class TerritorioPlanillaInfo(BaseModel):
    numero: int
    total_salidas: int
    ciclo_actual: int
    fila_actual: int
    proximo_ciclo: int = 1  # Valor por defecto por seguridad
    proxima_fila: int = 1   # Valor por defecto por seguridad
    nombre_planilla: str
    anio: int
    mensaje_estado: str
    
    @classmethod
    def desde_db(cls, datos_db):
        # Aquí 'datos_db' sería lo que devuelva tu nueva query
        return cls(**datos_db)