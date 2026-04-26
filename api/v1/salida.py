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
        # 1. Procesar Conductor (Buscamos el ID por nombre para ser limpios)
        if "conductor" in datos and datos["conductor"]:
            nombre_buscado = str(datos["conductor"]).strip()
            # Buscamos el objeto conductor en la DB
            conductor_obj = db.query(Conductor).filter(Conductor.nombre == nombre_buscado).first()
            
            if conductor_obj:
                # ASIGNAMOS AL ID (Columna física), NO A LA RELACIÓN
                salida.conductor_id = conductor_obj.id
            else:
                # Si no existe, podemos elegir dejarlo en None o no tocarlo
                salida.conductor_id = None

        # 2. Procesar Punto de Encuentro (Columna de texto directa)
        if "punto_encuentro" in datos:
            salida.punto_encuentro = str(datos["punto_encuentro"])

        # 3. Procesar Fecha (Conversión segura a objeto Date)
        if "fecha" in datos and datos["fecha"]:
            try:
                # Convertimos el string ISO de JS a objeto date de Python
                salida.fecha = datetime.strptime(datos["fecha"], "%Y-%m-%d").date()
            except (ValueError, TypeError):
                pass # Si la fecha está mal formateada, no la actualizamos

        db.commit()
        db.refresh(salida) # Sincronizamos el objeto
        return {"status": "ok", "message": "Actualizado correctamente"}

    except Exception as e:
        db.rollback()
        # Esto imprimirá el error real en los logs de Render antes de morir
        print(f"--- ERROR CRÍTICO EN PATCH ---: {str(e)}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")


@router.delete("/{salida_id}")
def eliminar_salida(salida_id: int, db: Session = Depends(get_db)):
    repo = SalidaRepository(db)
    repo.eliminar(salida_id)
    db.commit()
    return {"status": "ok"}
