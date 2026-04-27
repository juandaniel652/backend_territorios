from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from domain.salida.model import Salida
from core.database import get_db
from domain.salida.repository import SalidaRepository
from domain.salida.schema import SalidaUpdate
from domain.conductor.repository import ConductorRepository
from datetime import datetime
from domain.conductor.model import Conductor

router = APIRouter(prefix="/salidas", tags=["salidas"])


@router.get("")
def listar_salidas(db: Session = Depends(get_db)):
    repo = SalidaRepository(db)
    return repo.listar()

# ─── GET: AGENDA QUINCENAL ──────────────────────────────────────────────────
@router.get("/quincena")
def obtener_agenda_guardada(db: Session = Depends(get_db)):
    # AGREGAMOS .order_by para que la lógica de tiempo se respete
    salidas = db.query(Salida)\
        .options(joinedload(Salida.conductor))\
        .order_by(Salida.fecha.asc(), Salida.turno.asc())\
        .all() 
    
    return [
        {
            "id": s.id,
            "fecha": s.fecha.isoformat() if hasattr(s.fecha, 'isoformat') else str(s.fecha),
            "turno": s.turno,
            "territorio_id": s.territorio_id,
            # Cambiamos "conductor" por "conductor_nombre" para que UI.js lo lea bien
            "conductor_nombre": s.conductor.nombre_completo if s.conductor else "Sin asignar", 
            "punto_encuentro": s.punto_encuentro or "A confirmar"
        }
        for s in salidas
    ]

# ─── PATCH: ACTUALIZAR SALIDA ───────────────────────────────────────────────
@router.patch("/{salida_id}")
def actualizar_salida(salida_id: int, datos: dict, db: Session = Depends(get_db)):
    salida = db.query(Salida).filter(Salida.id == salida_id).first()
    if not salida:
        raise HTTPException(status_code=404, detail="No encontrada")
    
    try:
        # 1. Procesar Conductor con lógica ILIKE (No distingue mayúsculas/minúsculas)
        if "conductor" in datos and datos["conductor"]:
            nombre_recibido = str(datos["conductor"]).strip()
            
            conductor_obj = db.query(Conductor).filter(
                Conductor.nombre_completo.ilike(nombre_recibido)
            ).first()
            
            if conductor_obj:
                salida.conductor_id = conductor_obj.id
                print(f"DEBUG: Vinculado a conductor_id {conductor_obj.id} ({conductor_obj.nombre_completo})")
            else:
                # Si no lo encuentra, lo dejamos en None o podrías optar por no tocarlo
                salida.conductor_id = None
                print(f"DEBUG: No se encontró el conductor '{nombre_recibido}'")
                
        # 2. Procesar Punto de Encuentro
        if "punto_encuentro" in datos:
            salida.punto_encuentro = str(datos["punto_encuentro"])

        # 3. Procesar Fecha
        if "fecha" in datos and datos["fecha"]:
            try:
                salida.fecha = datetime.strptime(datos["fecha"], "%Y-%m-%d").date()
            except (ValueError, TypeError):
                pass

        db.commit()
        db.refresh(salida)
        return {"status": "ok", "message": "Actualizado correctamente"}

    except Exception as e:
        db.rollback()
        print(f"--- ERROR CRÍTICO EN PATCH ---: {str(e)}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")

# ─── DELETE: ELIMINAR SALIDA ───────────────────────────────────────────────
@router.delete("/{salida_id}")
def eliminar_salida(salida_id: int, db: Session = Depends(get_db)):
    repo = SalidaRepository(db)
    repo.eliminar(salida_id)
    db.commit()
    return {"status": "ok"}