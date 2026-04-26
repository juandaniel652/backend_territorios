from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from domain.salida.model import Salida
from core.database import get_db
from domain.salida.repository import SalidaRepository
from domain.salida.schema import SalidaUpdate
from domain.conductor.repository import ConductorRepository

router = APIRouter(prefix="/salidas", tags=["salidas"])


@router.get("")
def listar_salidas(db: Session = Depends(get_db)):
    repo = SalidaRepository(db)
    return repo.listar()

@router.get("/quincena")
def obtener_agenda_guardada(db: Session = Depends(get_db)):
    # Usamos joinedload para traer los datos del territorio y conductor en una sola consulta
    salidas = db.query(Salida).filter(Salida.activo == True).all()
    
    # Transformamos a un formato que el Frontend entienda fácil
    return [
        {
            "id": s.id,
            "fecha": s.fecha_asignado.isoformat() if hasattr(s.fecha_asignado, 'isoformat') else str(s.fecha_asignado),
            "turno": s.turno,
            "territorio_id": s.territorio_id,
            # SOLUCIÓN AL ERROR: usamos str() o un valor por defecto si falla el objeto
            "conductor": s.conductor.nombre if (s.conductor and hasattr(s.conductor, 'nombre')) else "Varios/Sin asignar",
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
    
    # Actualizamos dinámicamente los campos que vengan (conductor, encuentro, activo, etc.)
    for key, value in datos.items():
        setattr(salida, key, value)
    
    db.commit()
    return {"status": "ok"}

@router.delete("/{salida_id}")
def eliminar_salida(salida_id: int, db: Session = Depends(get_db)):
    repo = SalidaRepository(db)
    repo.eliminar(salida_id)
    db.commit()
    return {"status": "ok"}
