# asignaciones.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import date
from database import engine
from sqlalchemy import text

router = APIRouter()

class AsignacionCrear(BaseModel):
    numero_territorio: int
    conductor: str
    fecha_asignado: date
    fecha_completado: date
    total_abarcado: str

@router.post("/asignaciones")
def crear_asignacion(asignacion: AsignacionCrear):
    try:
        # -------------------------
        # Usamos engine.begin() para que todo se haga en una transacción
        # -------------------------
        with engine.begin() as conn:
            # -------------------------
            # Obtener ID del territorio
            # -------------------------
            territorio = conn.execute(
                text("SELECT id FROM Territorios WHERE numero = :numero"),
                {"numero": asignacion.numero_territorio}
            ).fetchone()

            if not territorio:
                raise HTTPException(status_code=400, detail="Territorio no encontrado")
            territorio_id = territorio[0]

            # -------------------------
            # Obtener ID del conductor
            # -------------------------
            conductor = conn.execute(
                text("SELECT id FROM Conductores WHERE nombre_completo = :nombre"),
                {"nombre": asignacion.conductor}
            ).fetchone()

            if conductor:
                conductor_id = conductor[0]
            else:
                # Insertar conductor y obtener ID
                result = conn.execute(
                    text("INSERT INTO Conductores(nombre_completo) VALUES(:nombre) RETURNING id"),
                    {"nombre": asignacion.conductor}
                )
                conductor_id = result.fetchone()[0]

            # -------------------------
            # Insertar la asignación
            # -------------------------
            conn.execute(
                text("""
                    INSERT INTO Asignaciones 
                    (territorio_id, conductor_id, fecha_asignado, fecha_completado, cantidad_abarcado)
                    VALUES (:territorio_id, :conductor_id, :fecha_asignado, :fecha_completado, :cantidad_abarcado)
                """),
                {
                    "territorio_id": territorio_id,
                    "conductor_id": conductor_id,
                    "fecha_asignado": asignacion.fecha_asignado,
                    "fecha_completado": asignacion.fecha_completado,
                    "cantidad_abarcado": asignacion.total_abarcado
                }
            )

        return {"message": "Asignación creada correctamente"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
