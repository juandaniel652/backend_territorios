from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from core.database import get_db
from domain.planilla.repository import PlanillaRepository
from domain.planilla.service import PlanillaService
from domain.planilla.schema import PlanillaOut
from typing import List

router = APIRouter(prefix="/planillas", tags=["planillas"])

def get_planilla_service(db: Session = Depends(get_db)):
    repo = PlanillaRepository(db)
    return PlanillaService(repo)

@router.get("/", response_model=List[PlanillaOut], summary="Listado de todas las planillas")
def obtener_planillas(service: PlanillaService = Depends(get_planilla_service)):
    return service.listar_planillas()

@router.get("/total", summary="Total de planillas")
def obtener_total_planillas(service: PlanillaService = Depends(get_planilla_service)):
    return service.obtener_planillas_totales()

@router.get("/total-completas", summary="Total de planillas completas")
def obtener_total_planillas_completas(service: PlanillaService = Depends(get_planilla_service)):
    return service.obtener_solo_planillas_completas()

