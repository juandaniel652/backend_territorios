#Iniciar db en local con: 
#uvicorn backend.app:app --reload

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from datetime import datetime
from backend.database import engine
from settings import settings
from sugerir_territorios import router as sugerencias_router


app = FastAPI()

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5500",
        "http://localhost:5500",
        "http://127.0.0.1:5501",
        "http://localhost:5501",
        "https://territorios-front-end.vercel.app",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 👇 PRIMERO rutas fijas
app.include_router(sugerencias_router)

# 👇 DESPUÉS rutas dinámicas
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
    WHERE t.numero = :numero
    ORDER BY a.fecha_asignado;
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
        
        print(">>> BACKEND.APP CARGADO <<<")


        return {"territorio": numero, "asignaciones": filas}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    

@app.get("/health")
def health():
    return {"status": "ok"}




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