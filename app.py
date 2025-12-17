from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from datetime import datetime
from .database import engine

app = FastAPI()

# Permitir solicitudes desde cualquier origen (para desarrollo)
app.add_middlewareapp.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://territorios-front-end.vercel.app",
        "http://127.0.0.1:5501",
        "http://localhost:5501"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/territorios/{numero}")
def obtener_asignaciones(numero: int):
    sql = """
    SELECT 
        c.nombre_completo AS conductor,
        a.fecha_asignado,
        a.fecha_completado,
        a.cantidad_abarcado
    FROM Asignaciones a
    JOIN Territorios t ON a.territorio_id = t.id
    JOIN Conductores c ON a.conductor_id = c.id
    WHERE t.numero = :numero;
    """

    try:
        with engine.connect() as conn:
            result = conn.execute(text(sql), {"numero": numero})
            filas = [dict(row._mapping) for row in result.fetchall()]

        if not filas:
            return {"territorio": numero, "asignaciones": [], "mensaje": "No hay asignaciones"}

        # Orden cronológico
        filas.sort(
            key=lambda f: datetime.strptime(str(f["fecha_asignado"]), "%Y-%m-%d") if f["fecha_asignado"] else datetime.max
        )

        return {"territorio": numero, "asignaciones": filas}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))




#Backend:
#
#uvicorn backend.main:app --reload
#
#
#Frontend:
#cd frontend python -m http.server 5501
#
#
#Abrí navegador:
#
#http://127.0.0.1:5501