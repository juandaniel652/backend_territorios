"""
Capa de servicio del dominio Territorio.

Responsabilidades:
  - Orquestar llamadas al repositorio
  - Aplicar reglas de negocio (severidad, rangos válidos, cache)
  - Lanzar excepciones de dominio (HTTPException vive en el router, no aquí*)
  - Devolver schemas listos para serializar
"""

from datetime import date, timedelta
from time import time
from typing import List
from fastapi import HTTPException

from domain.territorio.repository import TerritorioRepositoryProtocol
from domain.territorio.schema import (
    TerritorioConAsignacionesOut,
    SugerenciaTerritorio,
    SugerenciasOut,
    TerritorioPlanillaInfo,
    HistorialPosicionadoOut,
    AsignacionPosicionada,
    SemanaDisponible,
    ReporteTerritorioSemanal
)

from core.utils import extraer_info_planilla, obtener_anio_servicio
from domain.planilla.repository import PlanillaRepository

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

MESES_ES = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril", 5: "Mayo", 6: "Junio",
    7: "Julio", 8: "Agosto", 9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"
}


# ─────────────────────────────────────────────
# Reglas de negocio puras
# ─────────────────────────────────────────────

def _calcular_severidad(dias: int | None) -> str:
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
    dias = (hoy - sugerencia.ultima_fecha).days if sugerencia.ultima_fecha else None
    return sugerencia.model_copy(update={
        "dias_atraso": dias,
        "severidad": _calcular_severidad(dias),
    })


# ─────────────────────────────────────────────
# Servicio
# ─────────────────────────────────────────────

class TerritorioService:

    def __init__(self, repo: TerritorioRepositoryProtocol, planilla_repo: PlanillaRepository = None) -> None:
        self.repo = repo
        self.planilla_repo = planilla_repo

    # ── Historial ────────────────────────────

    def obtener_historial(self, numero: int) -> TerritorioConAsignacionesOut:
        asignaciones = self.repo.obtener_asignaciones_historial(numero)

        if not asignaciones:
            return TerritorioConAsignacionesOut(
                territorio=numero,
                asignaciones=[],
                mensaje="No hay asignaciones para este territorio",
            )

        asignaciones.reverse()

        return TerritorioConAsignacionesOut(
            territorio=numero,
            asignaciones=asignaciones,
        )

    # ── Sugerencias ──────────────────────────

    def obtener_sugerencias(self, rango: str, limit: int) -> SugerenciasOut:
        if rango not in RANGOS_VALIDOS:
            raise HTTPException(
                status_code=400,
                detail=f"Rango inválido. Opciones: {list(RANGOS_VALIDOS.keys())}",
            )

        cache_key = f"{rango}:{limit}"
        now = time()
        if cache_key in _CACHE:
            data, timestamp = _CACHE[cache_key]
            if now - timestamp < CACHE_TTL:
                return data.model_copy(update={"cache": True})

        desde, hasta = RANGOS_VALIDOS[rango]
        sugerencias_db = self.repo.obtener_sugerencias_antiguedad(desde=desde, hasta=hasta, limit=limit)

        sugerencias = [
            SugerenciaTerritorio(
                numero=s["numero"],
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
        if dia_nombre == "sabado":
            return True
        
        if turno == "AM" and not t.permite_am:
            return False
        if turno == "PM" and not t.permite_pm:
            return False
        
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
        es_sabado = fecha_objetivo.weekday() == 5
        raw_sugerencias = self.repo.obtener_sugerencias_por_dia(es_sabado=es_sabado)
        
        propuesta = []
        for s in raw_sugerencias:
            num = s["numero"]
            
            if 42 <= num <= 60: 
                zona_tag = "Zona 3 (Sábado)"
            elif num in [28, 29, 30, 31, 39, 40, 41]: 
                zona_tag = "Zona 2 (Crítica)"
            else: 
                zona_tag = "Zona Estándar"

            propuesta.append({
                "territorio_id": s["id"],
                "numero": num,
                "ultima_fecha": s["ultima_fecha"],
                "zona_descripcion": zona_tag,
                "turno_recomendado": "SÁBADO AM" if es_sabado else "SEMANA / TARDE"
            })
            
        return propuesta
    
    # ── Planillas ──────────────────────────

    def obtener_estado_planilla(self, numero: int) -> TerritorioPlanillaInfo:
        info_db = self.repo.obtener_estado_detallado(numero)
        hoy = date.today()
        anio_actual = obtener_anio_servicio(hoy)

        if not info_db or info_db.get("total_salidas", 0) == 0:
            if info_db:
                zona = info_db.get("zona", 1)
            else:
                zona = self.repo.obtener_zona_de_territorio(numero) or 1
            
            nombre_ini = self.obtener_nombre_dinamico(zona, 1)
            
            return TerritorioPlanillaInfo(
                numero=numero, total_salidas=0,
                ciclo_actual=1, fila_actual=0, 
                proximo_ciclo=1, proxima_fila=1,
                nombre_planilla=nombre_ini,
                anio=anio_actual, mensaje_estado="Sin salidas"
            )

        total = info_db["total_salidas"]
        actual_ciclo = ((total - 1) // 5) + 1
        actual_fila = ((total - 1) % 5) + 1
        zona = info_db.get("zona") or 1

        if actual_fila == 5:
            sig_ciclo = actual_ciclo + 1
            sig_fila = 1
        else:
            sig_ciclo = actual_ciclo
            sig_fila = actual_fila + 1

        nombre_planilla = self.obtener_nombre_dinamico(zona, sig_ciclo)

        return TerritorioPlanillaInfo(
            numero=numero,
            total_salidas=total,
            ciclo_actual=actual_ciclo,
            fila_actual=actual_fila,
            proximo_ciclo=sig_ciclo,
            proxima_fila=sig_fila,
            nombre_planilla=nombre_planilla,
            anio=info_db.get("anio") or anio_actual,
            mensaje_estado=f"Ciclo {actual_ciclo} - Fila {actual_fila}/5"
        )
        
    def obtener_nombre_dinamico(self, zona: int, ciclo: int):
        nombres_fijos = {
            1: {
                1: '1° Planilla, Casas 1-20; (2025)',
                2: '2° Planilla, Casas 1-20; (2025)',
                3: '3° Planilla, Casas 1-20; (2025)',
                4: '1° Planilla, Casas 1-20; (2026)'
            },
            2: {
                1: '2° Planilla, Casas 21-40; (2024)',
                2: '3° Planilla, Casas 21-40; (2024)',
                3: '4° Planilla, Casas 21-40; (2024)',
                4: '1° Planilla, Casas 21-40; (2025)',
                5: '1° Planilla, Casas 21-40; (2026)',
                6: '2° Planilla, Casas 21-40; (2026)'
            },
            3: {
                1: '1° Planilla, Casas 41-60; (2024)',
                2: '2° Planilla, Casas 41-60; (2024)',
                3: '1⁰ Planilla, Casas 41-60; (2025)',
                4: '1ª Planilla, Casas 41-60; (2026)'
            }
        }

        nombre_mapeado = nombres_fijos.get(zona, {}).get(ciclo)
        if nombre_mapeado:
            return nombre_mapeado

        anio_servicio = obtener_anio_servicio()
        ultima_planilla_db = self.planilla_repo.obtener_ultima_planilla_creada(zona, ciclo)
        
        if ultima_planilla_db and ultima_planilla_db.nombre_planilla:
            num_anterior, anio_anterior = extraer_info_planilla(ultima_planilla_db.nombre_planilla)
            
            if num_anterior is None or anio_anterior is None:
                proximo_numero = 1
            else:
                if anio_anterior == anio_servicio:
                    proximo_numero = num_anterior + 1
                else:
                    proximo_numero = 1
        else:
            proximo_numero = 1

        rangos = {1: "1-20", 2: "21-40", 3: "41-60"}
        rango_txt = rangos.get(zona, f"Zona {zona}")

        return f"{proximo_numero}° Planilla, Casas {rango_txt}; ({anio_servicio})"
    
    def obtener_historial_posicionado(self, numero: int) -> HistorialPosicionadoOut:
        zona = self.repo.obtener_zona_de_territorio(numero) or 1
        asignaciones_crudas = self.repo.obtener_asignaciones_historial(numero)

        if not asignaciones_crudas:
            return HistorialPosicionadoOut(
                territorio=numero,
                historial_posicionado=[],
                mensaje="No hay asignaciones para este territorio",
            )

        asignaciones_ordenadas = sorted(
            asignaciones_crudas,
            key=lambda x: (x.fecha_asignado if x.fecha_asignado else date.min, x.id)
        )

        historial_posicionado = []

        for i, asig in enumerate(asignaciones_ordenadas, start=1):
            ciclo_asig = ((i - 1) // 5) + 1
            fila_asig = ((i - 1) % 5) + 1
            nombre_planilla = self.obtener_nombre_dinamico(zona, ciclo_asig)

            historial_posicionado.append(
                AsignacionPosicionada(
                    id=asig.id,
                    conductor=asig.conductor,
                    fecha_asignado=asig.fecha_asignado,
                    fecha_completado=asig.fecha_completado,
                    cantidad_abarcado=asig.cantidad_abarcado,
                    ciclo=ciclo_asig,
                    fila=fila_asig,
                    nombre_planilla=nombre_planilla
                )
            )

        return HistorialPosicionadoOut(
            territorio=numero,
            historial_posicionado=historial_posicionado
        )

    def obtener_semanas_disponibles(self) -> List[SemanaDisponible]:
        fechas = self.repo.obtener_todas_las_fechas_asignadas()
        if not fechas:
            return []

        semanas_registradas = set()
        resultado: List[SemanaDisponible] = []

        for f in fechas:
            lunes = f - timedelta(days=f.weekday())
            domingo = lunes + timedelta(days=6)

            rango = (lunes, domingo)
            if rango not in semanas_registradas:
                semanas_registradas.add(rango)

                mes_lunes = MESES_ES[lunes.month]
                mes_domingo = MESES_ES[domingo.month]

                if lunes.month == domingo.month:
                    label = f"Del {lunes.day} al {domingo.day} de {mes_lunes} {lunes.year}"
                else:
                    label = f"Del {lunes.day} de {mes_lunes} al {domingo.day} de {mes_domingo} {lunes.year}"

                resultado.append(SemanaDisponible(
                    label=label,
                    fecha_inicio=lunes,
                    fecha_fin=domingo
                ))

        resultado.sort(key=lambda x: x.fecha_inicio, reverse=True)
        return resultado

    def obtener_reporte_semanal(self, fecha_inicio: date, fecha_fin: date) -> List[ReporteTerritorioSemanal]:
        datos = self.repo.obtener_reporte_por_rango(fecha_inicio, fecha_fin)
        return [ReporteTerritorioSemanal(**item) for item in datos]