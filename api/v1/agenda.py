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

@router.get("/sugerir-quincenal", summary="Genera la propuesta de agenda filtrada por una sola zona")
def sugerir_quincenal(
    zona: int = Query(..., description="Zona de la planilla a filtrar"),
    db: Session = Depends(get_db)
):
    service = AgendaQuincenalService(db)
    return service.generar_propuesta_quincenal(zona=zona)


@router.get("/sugerir-combinada", summary="Genera la propuesta de agenda unificada intercalando las 3 zonas con restricciones")
def sugerir_combinada(
    db: Session = Depends(get_db)
):
    """
    Este endpoint junta las zonas 1, 2 y 3. 
    Aplica la restricción de que Zona 3 y los territorios 28-31 de Zona 2 
    solo puedan caer los Sábados AM.
    """
    service = AgendaQuincenalService(db)
    return service.generar_propuesta_quincenal_combinada()


@router.post("/confirmar-quincenal", summary="Confirma la propuesta y la inserta en salidas (vacias) y sugerencias")
def confirmar_quincenal(
    data: ConfirmarAgendaIn,
    db: Session = Depends(get_db)
):
    service = AgendaQuincenalService(db)
    # Convertimos los objetos Pydantic a diccionarios planos para el servicio domain
    items_dict = [item.model_dump() for item in data.items]
    return service.confirmar_propuesta(items_dict)