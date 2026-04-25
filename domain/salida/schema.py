from pydantic import BaseModel
from datetime import date
from typing import Optional

class SalidaUpdate(BaseModel):
    territorio_id: Optional[int] = None
    conductor: Optional[str] = None
    fecha: Optional[date] = None
    turno: Optional[str] = None
    punto_encuentro: Optional[str] = None