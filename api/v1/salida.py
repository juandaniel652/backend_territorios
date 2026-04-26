from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from domain.salida.model import Salida
from core.database import get_db
from domain.salida.repository import SalidaRepository
from domain.salida.schema import SalidaUpdate
from domain.conductor.repository import ConductorRepository
from datetime import datetime

router = APIRouter(prefix="/salidas", tags=["salidas"])


@router.get("")
def listar_salidas(db: Session = Depends(get_db)):
    repo = SalidaRepository(db)
    return repo.listar()

# api/v1/salida.py

@router.get("/quincena")
def obtener_agenda_guardada(db: Session = Depends(get_db)):
    # Quitamos el .filter(Salida.activo == True) temporalmente
    salidas = db.query(Salida).all() 
    
    return [
        {
            "id": s.id,
            "fecha": s.fecha.isoformat() if hasattr(s.fecha, 'isoformat') else str(s.fecha),
            "turno": s.turno,
            "territorio_id": s.territorio_id,
            # Nota: En el error vi que el campo se llama 'fecha', no 'fecha_asignado'
            "conductor": "Varios", 
            "punto_encuentro": s.punto_encuentro
        }
        for s in salidas
    ]

@router.get("/quincena-actual")
def obtener_quincena(db: Session = Depends(get_db)):
    # Traemos las salidas ordenadas por fecha y turno
    # Puedes filtrar por un rango de fechas si lo prefieres
    return db.query(Salida).order_by(Salida.fecha.asc(), Salida.turno.asc()).all()

@router.patch("/{salida_id}")
def actualizar_salida(salida_id: int, datos: dict, db: Session = Depends(get_db)):
    salida = db.query(Salida).filter(Salida.id == salida_id).first()
    if not salida:
        raise HTTPException(status_code=404, detail="No encontrada")
    
    try:
        # 1. FECHA: Convertir string a objeto Date
        if "fecha" in datos and datos["fecha"]:
            salida.fecha = datetime.strptime(datos["fecha"], "%Y-%m-%d").date()

        # 2. PUNTO DE ENCUENTRO: Texto directo
        if "punto_encuentro" in datos:
            salida.punto_encuentro = datos["punto_encuentro"]

        # 3. CONDUCTOR: El paso limpio
        if "conductor" in datos:
            nombre = datos["conductor"].strip()
            # Buscamos en la tabla de conductores por nombre
            from domain.conductor.model import Conductor # Asegura el import
            cond = db.query(Conductor).filter(Conductor.nombre == nombre).first()
            
            if cond:
                salida.conductor_id = cond.id # Guardamos el ID, no el objeto
            else:
                # Si no existe, podemos poner null o manejarlo
                salida.conductor_id = None 

        db.commit()
        return {"status": "ok"}

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{salida_id}")
def eliminar_salida(salida_id: int, db: Session = Depends(get_db)):
    repo = SalidaRepository(db)
    repo.eliminar(salida_id)
    db.commit()
    return {"status": "ok"}
