from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from core.database import get_db
from domain.salida.service import sincronizar_automatico_sin_params

router = APIRouter(prefix="/salida", tags=["salida"])

@router.post("/sincronizar-sheets-automatico")
def sincronizar_sheets_automatico(db: Session = Depends(get_db)):
    """
    Botón de un solo clic: sin parámetros, genera y sube a Google Sheets al instante.
    """
    return sincronizar_automatico_sin_params(db)