from pydantic import BaseModel
from datetime import date
from typing import Optional, List

class ConductorDisponibleSchema(BaseModel):
    id: int
    nombre_completo: str
    sexo: str
    escasez: int
    asignaciones_previas: int

class SalidaPropuestaSchema(BaseModel):
    fecha: str
    horario: str
    territorio_id: int
    territorio_numero: int
    zona: int
    score: int
    punto_encuentro: str
    conductor_id: int
    conductor_nombre: str
    conductores_disponibles: List[ConductorDisponibleSchema] = []

class SemanaPropuestaSchema(BaseModel):
    semana_numero: int
    rango_fechas: str
    salidas: List[SalidaPropuestaSchema]

class SincronizarSheetsRequest(BaseModel):
    spreadsheet_name: str
    propuesta: List[SemanaPropuestaSchema]

class SalidaUpdate(BaseModel):
    territorio_id: Optional[int] = None
    conductor: Optional[str] = None
    fecha: Optional[date] = None
    turno: Optional[str] = None
    punto_encuentro: Optional[str] = None