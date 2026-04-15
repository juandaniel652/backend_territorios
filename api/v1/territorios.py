"""
api/v1/territorios.py

Router del dominio Territorio.
Solo responsabilidades HTTP:
  - Parsear parámetros de ruta/query
  - Construir dependencias (repo, service)
  - Llamar al servicio
  - Devolver la respuesta tipada

Cero SQL, cero lógica de negocio aquí.

Reemplaza:
  - El endpoint GET /territorios/{numero} que vivía en app.py con SQL inline
  - El router completo de sugerir_territorios.py con SQL inline y cache acoplado
"""

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from domain.territorio.model import Territorio
from domain.asignacion.model import Asignacion

from domain.territorio.schema import TerritorioConAsignacionesOut, SugerenciasOut, AgendaItemIn
from core.database import get_db
from domain.territorio.repository import TerritorioRepository
from domain.territorio.service import TerritorioService
from domain.territorio.schema import TerritorioConAsignacionesOut, SugerenciasOut
from datetime import date
from typing import List


router = APIRouter(prefix="/territorios", tags=["territorios"])


# ── Factory de servicio ──────────────────────────────────────────────────────
# Construye el grafo de dependencias para este router.
# Al estar separado del endpoint, puede ser sobreescrito en tests.

def get_territorio_service(db: Session = Depends(get_db)) -> TerritorioService:
    repo = TerritorioRepository(db)
    return TerritorioService(repo)


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.get(
    "/sugerencias",
    response_model=SugerenciasOut,
    summary="Territorios más atrasados por rango",
)
def obtener_sugerencias(
    rango: str = Query(..., description="Rango de territorios: '1-20', '21-40' o '41-60'"),
    limit: int = Query(default=10, ge=1, le=60),
    service: TerritorioService = Depends(get_territorio_service),
):
    return service.obtener_sugerencias(rango=rango, limit=limit)

# --- NUEVO ENDPOINT: Debe ir antes de /{numero} ---
@router.get(
    "/generar-plan",
    summary="Genera una propuesta de agenda quincenal",
)
def generar_plan(
    fecha_inicio: date = Query(..., description="Fecha lunes de inicio YYYY-MM-DD"), 
    service: TerritorioService = Depends(get_territorio_service),
):
    """
    Llama al servicio para calcular qué territorios 
    deben asignarse en la quincena.
    """
    # Si aún no creaste el método en el service, podés retornar un [] para testear
    return service.generar_plan_quincenal(fecha_inicio)


@router.get(
    "/{numero}",
    response_model=TerritorioConAsignacionesOut,
    summary="Historial de asignaciones de un territorio",
)
def obtener_historial(
    numero: int,
    service: TerritorioService = Depends(get_territorio_service),
):
    return service.obtener_historial(numero)

@router.post("/confirmar-agenda", status_code=201)
def confirmar_agenda(
    plan: List[AgendaItemIn], # <-- Cambiamos dict por el Schema
    db: Session = Depends(get_db)
):
    try:
        for item in plan:
            # 1. Buscar el territorio por número (el que viene del input editable)
            territorio = db.query(Territorio).filter(Territorio.numero == item.numero_territorio).first()
            
            if territorio:
                # 2. Crear la asignación 
                # OJO: Verificá si en tu modelo Asignacion el campo es 'conductor_id' o 'conductor_nombre'
                nueva_asig = Asignacion(
                    territorio_id=territorio.id,
                    conductor_id=None, # Si guardas por nombre, podés dejarlo en None o buscar el ID
                    # Aquí asumo que agregaste un campo o usas el nombre directamente:
                    fecha_asignado=item.fecha_asignado,
                    turno=item.turno,
                    lugar_encuentro=item.encuentro,
                    # Si tu tabla asignaciones tiene un campo para el nombre del conductor temporal:
                    observaciones=f"Conductor: {item.conductor}" 
                )
                db.add(nueva_asig)
        
        db.commit()
        return {"status": "success", "message": "Agenda archivada correctamente"}
    except Exception as e:
        db.rollback()
        print(f"❌ Error en confirmar_agenda: {str(e)}") # Log para Render
        raise HTTPException(status_code=500, detail=str(e))