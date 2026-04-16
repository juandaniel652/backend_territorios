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
            # 1. Buscar el territorio
            territorio = db.query(Territorio).filter(Territorio.numero == item.numero_territorio).first()
            if not territorio:
                continue

            # 2. Lógica del Conductor (Relación Dinámica)
            # Buscamos si el nombre ya existe en la tabla conductores
            nombre_conductor = item.conductor.strip()
            conductor = db.query(Conductor).filter(Conductor.nombre_completo == nombre_conductor).first()
            
            if not conductor:
                # Si no existe, lo creamos para tener un ID válido
                conductor = Conductor(nombre_completo=nombre_conductor)
                db.add(conductor)
                db.flush() # Para obtener el ID antes del commit final

            # 3. Crear la asignación
            nueva_asig = Asignacion(
                territorio_id=territorio.id,
                conductor_id=conductor.id, # Ahora tenemos un ID real
                fecha_asignado=item.fecha_asignado,
                # lugar_encuentro e item.encuentro: 
                # OJO: Tu tabla 'asignaciones' NO tiene columna 'lugar_encuentro' ni 'turno'.
                # Vamos a guardarlo en 'cantidad_abarcado' o 'observaciones' temporalmente 
                # para no romper la DB, o deberías agregar esas columnas a la tabla.
                cantidad_abarcado=f"Turno: {item.turno} | Encuentro: {item.encuentro}"
            )
            db.add(nueva_asig)

            # 4. ACTUALIZACIÓN CLAVE: Sincronizar con la tabla territorios
            # Esto hace que el T-13 desaparezca de las sugerencias la próxima vez
            territorio.ultima_fecha_completado = item.fecha_asignado 
        
        db.commit()
        return {"status": "success", "message": "Agenda guardada y territorios actualizados"}
    except Exception as e:
        db.rollback()
        print(f"❌ Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))