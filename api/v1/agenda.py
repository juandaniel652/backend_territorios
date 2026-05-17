"""
api/v1/agenda.py
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List
from pydantic import BaseModel
from datetime import date

from core.database import get_db
from domain.agenda.service import AgendaQuincenalService

router = APIRouter(prefix="/agenda", tags=["agenda"])

# ── Schemas Pydantic Rápidos para el endpoint ──────────────────────────────
class ItemSugerenciaIn(BaseModel):
    territorio_id: int
    fecha: date
    turno: str
    score: int
    punto_encuentro: str | None = "Salón del Reino"

class ConfirmarAgendaIn(BaseModel):
    items: List[ItemSugerenciaIn]


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/sugerir-quincenal", summary="Genera la propuesta de agenda para los próximos 2 domingos")
def sugerir_quincenal(
    zona: int = Query(..., description="Zona de la planilla a filtrar"),
    db: Session = Depends(get_db)
):
    service = AgendaQuincenalService(db)
    return service.generar_propuesta_quincenal(zona=zona)


@router.post("/confirmar-quincenal", summary="Confirma la propuesta y la inserta en salidas (vacias) y sugerencias")
def confirmar_quincenal(
    data: ConfirmarAgendaIn,
    db: Session = Depends(get_db)
):
    service = AgendaQuincenalService(db)
    # Convertimos los objetos Pydantic a diccionarios planos para el servicio domain
    items_dict = [item.model_dump() for item in data.items]
    return service.confirmar_propuesta(items_dict)