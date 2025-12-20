from fastapi import APIRouter, HTTPException
from sqlalchemy import text
from datetime import date
from database import engine
from time import time

CACHE = {}
CACHE_TTL = 300  # 5 minutos


router = APIRouter(
    prefix="/territorios",
    tags=["Sugerencias"]
)
@router.get("/sugerencias")
def sugerir_territorios(rango: str, limit: int = 10):
    
    cache_key = f"{rango}:{limit}"
    now = time()

    if cache_key in CACHE:
        data, timestamp = CACHE[cache_key]
        if now - timestamp < CACHE_TTL:
            return {**data, "cache": True}


    rangos = {
        "1-20": (1, 20),
        "21-40": (21, 40),
        "41-60": (41, 60),
    }

    if rango not in rangos:
        raise HTTPException(status_code=400, detail="Rango inválido")

    desde, hasta = rangos[rango]

    sql = """
    SELECT 
        t.numero,
        MAX(a.fecha_completado) AS ultima_fecha
    FROM Territorios t
    LEFT JOIN Asignaciones a ON a.territorio_id = t.id
    WHERE t.numero BETWEEN :desde AND :hasta
    GROUP BY t.numero
    ORDER BY 
        MAX(a.fecha_completado) IS NOT NULL,
        MAX(a.fecha_completado) ASC
    LIMIT :limit;
    """

    hoy = date.today()

    with engine.connect() as conn:
        result = conn.execute(
            text(sql),
            {"desde": desde, "hasta": hasta, "limit": limit}
        )

        sugerencias = []
        for row in result:
            ultima = row.ultima_fecha
            dias = (hoy - ultima).days if ultima else None

            if dias is None:
                severidad = "nunca"
            elif dias >= 30:
                severidad = "critico"
            elif dias >= 15:
                severidad = "alto"
            else:
                severidad = "normal"

            sugerencias.append({
                "numero": row.numero,
                "ultima_fecha": ultima,
                "dias_atraso": dias,
                "severidad": severidad
            })


    return {
        "rango": rango,
        "total": len(sugerencias),
        "sugerencias": sugerencias
    }
