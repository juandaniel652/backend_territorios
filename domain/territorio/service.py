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

from datetime import date
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
        Devuelve territorios más atrasados dentro del rango dado.
        Aplica cache en memoria con TTL configurable.

        Raises:
            HTTPException 400: si el rango no es uno de los valores válidos.
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

        # ── Cache miss: calcular ──
        desde, hasta = RANGOS_VALIDOS[rango]
        hoy = date.today()

        sugerencias_raw = self.repo.obtener_sugerencias(desde, hasta, limit)
        sugerencias = [_enriquecer_sugerencia(s, hoy) for s in sugerencias_raw]

        resultado = SugerenciasOut(
            rango=rango,
            total=len(sugerencias),
            sugerencias=sugerencias,
            cache=False,
        )

        _CACHE[cache_key] = (resultado, now)
        return resultado