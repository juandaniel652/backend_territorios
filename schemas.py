from pydantic import BaseModel
from datetime import date
from typing import Optional

class AsignacionCreate(BaseModel):
    territorio_id: int
    conductor: str
    fecha_asignado: date
    fecha_completado: Optional[date] = None
    total_abaracado: str
