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
from domain.conductor.model import Conductor
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
    plan: List[AgendaItemIn], 
    db: Session = Depends(get_db)
):
    try:
        for item in plan:
            # 1. GESTIÓN DE CONDUCTOR: Buscar o crear por nombre único
            nombre_limpio = item.conductor.strip()
            if not nombre_limpio:
                nombre_limpio = "Sin Asignar"
            
            conductor = db.query(Conductor).filter(Conductor.nombre_completo == nombre_limpio).first()
            
            if not conductor:
                conductor = Conductor(nombre_completo=nombre_limpio)
                db.add(conductor)
                db.flush() # Obtenemos el ID para la relación

            # 2. BÚSQUEDA DE TERRITORIO
            territorio = db.query(Territorio).filter(Territorio.numero == item.numero_territorio).first()
            if not territorio:
                print(f"⚠️ Territorio {item.numero_territorio} no existe. Saltando...")
                continue

            # 3. CREAR ASIGNACIÓN (Usando las nuevas columnas de la DB)
            nueva_asig = Asignacion(
                territorio_id=territorio.id,
                conductor_id=conductor.id,
                fecha_asignado=item.fecha_asignado,
                turno=item.turno,
                lugar_encuentro=item.encuentro,
                cantidad_abarcado=None # Se llenará cuando se complete
            )
            db.add(nueva_asig)

            # 4. 🔥 SINCRONIZACIÓN CLAVE: Actualizar la 'Verdad' del territorio
            # Esto hará que el T-13 tenga fecha de HOY y pierda prioridad en el Score
            territorio.ultima_fecha_completado = item.fecha_asignado
        
        db.commit()
        return {"status": "success", "message": "Agenda archivada y territorios actualizados"}
    
    except Exception as e:
        db.rollback()
        print(f"❌ Error crítico: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al procesar: {str(e)}")