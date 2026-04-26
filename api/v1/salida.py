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
        # 1. Actualizamos el conductor (Texto simple)
        if "conductor" in datos:
            salida.conductor = str(datos["conductor"])
            
        # 2. Actualizamos punto de encuentro (Texto simple)
        if "punto_encuentro" in datos:
            salida.punto_encuentro = str(datos["punto_encuentro"])
            
        # 3. TRATAMIENTO ESPECIAL PARA LA FECHA (Aquí es donde suele fallar)
        if "fecha" in datos and datos["fecha"]:
            # Convertimos el string "YYYY-MM-DD" en un objeto date real de Python
            try:
                fecha_obj = datetime.strptime(datos["fecha"], "%Y-%m-%d").date()
                salida.fecha = fecha_obj
            except ValueError:
                # Si la fecha viene en otro formato o mal, podrías ignorarla o lanzar error
                pass

        db.commit()
        return {"status": "ok"}

    except Exception as e:
        db.rollback()
        print(f"ERROR CRÍTICO: {str(e)}") # Esto lo verás en los logs de Render
        raise HTTPException(status_code=500, detail="Error interno al actualizar")

@router.delete("/{salida_id}")
def eliminar_salida(salida_id: int, db: Session = Depends(get_db)):
    repo = SalidaRepository(db)
    repo.eliminar(salida_id)
    db.commit()
    return {"status": "ok"}
