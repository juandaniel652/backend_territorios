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
    salidas = db.query(Salida)\
        .options(joinedload(Salida.territorio), joinedload(Salida.conductor))\
        .order_by(Salida.fecha.asc(), Salida.turno.asc())\
        .all()
    
    # Transformamos a un formato que el Frontend entienda fácil
    return [{
        "id": s.id,
        "fecha": s.fecha.strftime("%Y-%m-%d"),
        "turno": s.turno,
        "territorio_id": s.territorio_id,
        "conductor": s.conductor.nombre if s.conductor else "Sin asignar",
        "punto_encuentro": s.punto_encuentro
    } for s in salidas]

@router.get("/quincena-actual")
def obtener_quincena(db: Session = Depends(get_db)):
    # Traemos las salidas ordenadas por fecha y turno
    # Puedes filtrar por un rango de fechas si lo prefieres
    return db.query(Salida).order_by(Salida.fecha.asc(), Salida.turno.asc()).all()

@router.patch("/{salida_id}")
def actualizar_salida(
    salida_id: int, 
    obj_in: SalidaUpdate, 
    db: Session = Depends(get_db)
):
    # 1. Buscar la salida existente
    salida = db.query(Salida).filter(Salida.id == salida_id).first()
    if not salida:
        raise HTTPException(status_code=404, detail="Salida no encontrada")

    # 2. Si viene un nombre de conductor, resolver su ID
    if obj_in.conductor is not None:
        repo_cond = ConductorRepository(db)
        conductor, _ = repo_cond.obtener_o_crear(obj_in.conductor)
        salida.conductor_id = conductor.id

    # 3. Actualizar el resto de campos (punto_encuentro, fecha, etc.)
    update_data = obj_in.dict(exclude_unset=True, exclude={'conductor'})
    for field, value in update_data.items():
        setattr(salida, field, value)

    db.commit()
    db.refresh(salida)
    return {"status": "success", "mensaje": "Registro actualizado correctamente"}

@router.delete("/{salida_id}")
def eliminar_salida(salida_id: int, db: Session = Depends(get_db)):
    repo = SalidaRepository(db)
    repo.eliminar(salida_id)
    db.commit()
    return {"status": "ok"}
