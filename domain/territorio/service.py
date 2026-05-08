"""
domain/territorio/service.py

Capa de servicio del dominio Territorio.

Responsabilidades:
  - Orquestar llamadas al repositorio
  - Aplicar reglas de negocio (severidad, rangos válidos, cache)
  - Lanzar excepciones de dominio (HTTPException vive en el router, no aquí*)
  - Devolver schemas listos para serializar

*Excepción práctica: usamos HTTPException de FastAPI para mantener
 consistencia con el resto del stack sin agregar excepciones custom
 por ahora. En un sistema más grande convendría excepciones de dominio
 propias y un handler en el router.

Reemplaza:
  - Lógica de severidad inline de sugerir_territorios.py
  - Lógica de ordenamiento inline de app.py
  - Cache en-memoria de sugerir_territorios.py (ahora encapsulado aquí)
"""

from datetime import date, timedelta
from .repository import TerritorioRepository
from time import time
from fastapi import HTTPException

from domain.territorio.repository import TerritorioRepositoryProtocol
from domain.territorio.schema import (
    TerritorioConAsignacionesOut,
    SugerenciaTerritorio,
    SugerenciasOut,
)

# ─────────────────────────────────────────────
# Configuración de rangos válidos y cache
# ─────────────────────────────────────────────

RANGOS_VALIDOS: dict[str, tuple[int, int]] = {
    "1-20":  (1,  20),
    "21-40": (21, 40),
    "41-60": (41, 60),
}

_CACHE: dict[str, tuple[SugerenciasOut, float]] = {}
CACHE_TTL = 300  # segundos


# ─────────────────────────────────────────────
# Reglas de negocio puras
# ─────────────────────────────────────────────

def _calcular_severidad(dias: int | None) -> str:
    """
    Regla de negocio: clasifica un territorio según días sin asignación.
    Función pura — sin efectos secundarios, fácil de testear unitariamente.
    """
    if dias is None:
        return "nunca"
    if dias >= 30:
        return "critico"
    if dias >= 15:
        return "alto"
    return "normal"


def _enriquecer_sugerencia(
    sugerencia: SugerenciaTerritorio, hoy: date
) -> SugerenciaTerritorio:
    """Agrega dias_atraso y severidad a una sugerencia cruda del repositorio."""
    dias = (hoy - sugerencia.ultima_fecha).days if sugerencia.ultima_fecha else None
    return sugerencia.model_copy(update={
        "dias_atraso": dias,
        "severidad": _calcular_severidad(dias),
    })


# ─────────────────────────────────────────────
# Servicio
# ─────────────────────────────────────────────

class TerritorioService:
    """
    Orquesta el dominio Territorio.
    Depende del protocolo → no del repositorio concreto (DI).
    """

    def __init__(self, repo: TerritorioRepositoryProtocol) -> None:
        self.repo = repo

    # ── Historial ────────────────────────────

    def obtener_historial(self, numero: int) -> TerritorioConAsignacionesOut:
        """
        Devuelve el historial completo de asignaciones para un territorio.
        Si no existe el territorio o no tiene asignaciones devuelve lista vacía
        con un mensaje informativo (no lanza 404 — el territorio puede existir
        sin asignaciones todavía).
        """
        asignaciones = self.repo.obtener_asignaciones_historial(numero)

        if not asignaciones:
            return TerritorioConAsignacionesOut(
                territorio=numero,
                asignaciones=[],
                mensaje="No hay asignaciones para este territorio",
            )

        return TerritorioConAsignacionesOut(
            territorio=numero,
            asignaciones=asignaciones,
        )

    # ── Sugerencias ──────────────────────────

    def obtener_sugerencias(self, rango: str, limit: int) -> SugerenciasOut:
        """
        Devuelve territorios más atrasados usando la lógica de semáforo de DB.
        """
        if rango not in RANGOS_VALIDOS:
            raise HTTPException(
                status_code=400,
                detail=f"Rango inválido. Opciones: {list(RANGOS_VALIDOS.keys())}",
            )

        # ── Cache hit ──
        cache_key = f"{rango}:{limit}"
        now = time()
        if cache_key in _CACHE:
            data, timestamp = _CACHE[cache_key]
            if now - timestamp < CACHE_TTL:
                return data.model_copy(update={"cache": True})

        # ── Cache miss: llamar al REPO con el método de antigüedad ──
        desde, hasta = RANGOS_VALIDOS[rango]
        
        # IMPORTANTE: Llamamos al método que tiene la query de Supabase
        sugerencias_db = self.repo.obtener_sugerencias_antiguedad(desde=desde, hasta=hasta, limit=limit)

        # Convertimos los dicts de la DB al Schema Pydantic SugerenciaTerritorio
        sugerencias = [
            SugerenciaTerritorio(
                numero=s["numero"],
                # Cambiamos esto para que sea más robusto
                ultima_fecha=date.fromisoformat(s["ultima_visita"]) if (s["ultima_visita"] and s["ultima_visita"] != "Nunca") else None,
                dias_atraso=s["dias_atraso"],
                severidad=s["severidad"]
            ) for s in sugerencias_db
        ]

        resultado = SugerenciasOut(
            rango=rango,
            total=len(sugerencias),
            sugerencias=sugerencias,
            cache=False,
        )

        _CACHE[cache_key] = (resultado, now)
        return resultado
    
    def _get_offset(self, dia_nombre: str) -> int:
        dias = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado"]
        return dias.index(dia_nombre)

    def _valida_restricciones(self, t, dia_nombre: str, turno: str) -> bool:
        # Sábado es "libre" según tu doc
        if dia_nombre == "sabado":
            return True
        
        # Filtro de turno
        if turno == "AM" and not t.permite_am:
            return False
        if turno == "PM" and not t.permite_pm:
            return False
        
        # Filtro de Zona 3 (Solo sábados)
        if t.zona == 3:
            return False
            
        return True

    @staticmethod
    def calcular_score(territorio, fecha_planificada: date) -> float:
        if territorio.ultima_fecha_completado:
            dias_desde = (fecha_planificada - territorio.ultima_fecha_completado).days
        else:
            dias_desde = 999
        
        bono_zona = 15 if territorio.zona == 1 else 0
        return (dias_desde * 1.2) + bono_zona
    
    def generar_propuesta_dia(self, fecha_objetivo: date):
        # 1. Determinar si es sábado (5 es sábado en Python)
        es_sabado = fecha_objetivo.weekday() == 5
        
        # 2. Pedir al repo los territorios según la regla de negocio
        raw_sugerencias = self.repo.obtener_sugerencias_por_dia(es_sabado=es_sabado)
        
        propuesta = []
        for s in raw_sugerencias:
            num = s["numero"]
            
            # Clasificación visual para el frontend
            if 42 <= num <= 60: 
                zona_tag = "Zona 3 (Sábado)"
            elif num in [28, 29, 30, 31]: 
                zona_tag = "Zona 2 (Crítica)"
            else: 
                zona_tag = "Zona Estándar"

            # El retorno debe matchear con PropuestaDiaOut
            propuesta.append({
                "territorio_id": s["id"],
                "numero": num,
                "ultima_fecha": s["ultima_fecha"],
                "zona_descripcion": zona_tag,
                "turno_recomendado": "SÁBADO AM" if es_sabado else "SEMANA / TARDE"
            })
            
        return propuesta