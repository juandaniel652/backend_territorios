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
from typing import List

from domain.territorio.repository import TerritorioRepositoryProtocol
from domain.territorio.schema import (
    TerritorioConAsignacionesOut,
    SugerenciaTerritorio,
    SugerenciasOut,
    TerritorioPlanillaInfo,
    HistorialPosicionadoOut,
    AsignacionPosicionada
)


from core.utils import extraer_info_planilla, obtener_anio_servicio
from domain.planilla.repository import PlanillaRepository
from domain.territorio.schema import SemanaDisponible, ReporteTerritorioSemanal

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

# Diccionario para nombres de meses cortos en español
MESES_ES = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril", 5: "Mayo", 6: "Junio",
    7: "Julio", 8: "Agosto", 9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"
}

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

    def __init__(self, repo: TerritorioRepositoryProtocol, planilla_repo: PlanillaRepository = None) -> None:
        self.repo = repo
        self.planilla_repo = planilla_repo

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

        asignaciones.reverse()

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
        # 'territorio.ultima_fecha_completado' ahora dispara la @hybrid_property y busca en el historial
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
            elif num in [28, 29, 30, 31, 39, 40, 41]: 
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
        zona = info_db.get("zona")

        # --- DETERMINAR EL NOMBRE ---
        nombre_db = info_db.get("nombre_planilla")
        
        # Corregimos la condición: Si la base de datos YA tiene un nombre real asignado
        # para este ciclo, lo respetamos a muerte. No calculamos nada nuevo.
        if nombre_db and not nombre_db.startswith("Planilla "): 
            nombre_planilla = nombre_db
        else:
            # Si está vacío o es un nombre genérico de plantilla nueva, ahí sí calculamos
            nombre_planilla = self.obtener_nombre_dinamico(zona, actual_ciclo)

        if actual_fila == 5:
            sig_ciclo = actual_ciclo + 1
            sig_fila = 1
        else:
            sig_ciclo = actual_ciclo
            sig_fila = actual_fila + 1

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

        # ¡PRIMERO REVISAR EL DICCIONARIO HISTÓRICO!
        # Si el ciclo actual está en el diccionario, devolvemos ese string exacto.
        nombre_mapeado = nombres_fijos.get(zona, {}).get(ciclo)
        if nombre_mapeado:
            return nombre_mapeado

        # 2. Lógica de lectura y suma (Para ciclos futuros que no estén en el diccionario)
        anio_servicio = obtener_anio_servicio()
        
        # Pasamos el ciclo actual a la consulta para buscar solo ciclos anteriores reales
        ultima_planilla_db = self.planilla_repo.obtener_ultima_planilla_creada(zona, ciclo)
        
        if ultima_planilla_db and ultima_planilla_db.nombre_planilla:
            # Ejecutamos tu extractor
            num_anterior, anio_anterior = extraer_info_planilla(ultima_planilla_db.nombre_planilla)
            
            # --- PRETESTING / VALIDACIÓN DE SEGURIDAD ---
            if num_anterior is None or anio_anterior is None:
                # Si el string de la DB estaba corrupto o no se pudo leer,
                # asumimos que no hay un historial confiable y empezamos en 1
                proximo_numero = 1
            else:
                # Si la tupla es válida, seguimos con la lógica normal
                if anio_anterior == anio_servicio:
                    proximo_numero = num_anterior + 1
                else:
                    proximo_numero = 1
        else:
            # Caso base si es la primera planilla absoluta en la DB para esa zona
            proximo_numero = 1

        rangos = {1: "1-20", 2: "21-40", 3: "41-60"}
        rango_txt = rangos.get(zona, f"Zona {zona}")

        return f"{proximo_numero}° Planilla, Casas {rango_txt}; ({anio_servicio})"
    
    def obtener_historial_posicionado(self, numero: int) -> HistorialPosicionadoOut:
        """
        Cruza el historial con la posición matemática que tuvo cada salida en las planillas,
        ordenado estrictamente de manera cronológica (desempatando por ID).
        """
        # 1. Obtener la zona para el cálculo del nombre dinámico de planilla
        zona = self.repo.obtener_zona_de_territorio(numero) or 1

        # 2. Traer asignaciones existentes
        asignaciones_crudas = self.repo.obtener_asignaciones_historial(numero)

        if not asignaciones_crudas:
            return HistorialPosicionadoOut(
                territorio=numero,
                historial_posicionado=[],
                mensaje="No hay asignaciones para este territorio",
            )

        # 3. Ordenar cronológicamente (Fecha, ID) para resolver empates sin sobreingeniería
        asignaciones_ordenadas = sorted(
            asignaciones_crudas,
            key=lambda x: (x.fecha_asignado if x.fecha_asignado else date.min, x.id)
        )

        historial_posicionado = []

        # 4. Mapeo incremental base 1
        for i, asig in enumerate(asignaciones_ordenadas, start=1):
            ciclo_asig = ((i - 1) // 5) + 1
            fila_asig = ((i - 1) % 5) + 1

            # Reutiliza tu lógica dinámica actual que lee el diccionario fijos o base de datos
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
        """
        Agrupa las semanas utilizando las fechas en las que se COMPLETARON territorios.
        """
        # 💡 Cambiado para buscar fechas de finalización reales
        fechas = self.repo.obtener_todas_las_fechas_completadas()
        if not fechas:
            return []

        semanas_registradas = set()
        resultado: List[SemanaDisponible] = []

        for f in fechas:
            # Calculamos de Domingo a Sábado para la semana de corte
            dias_desde_domingo = (f.weekday() + 1) % 7
            domingo = f - timedelta(days=dias_desde_domingo)
            sabado = domingo + timedelta(days=6)

            rango = (domingo, sabado)
            if rango not in semanas_registradas:
                semanas_registradas.add(rango)

                mes_domingo = MESES_ES[domingo.month]
                mes_sabado = MESES_ES[sabado.month]

                if domingo.month == sabado.month:
                    label = f"Del Dom {domingo.day} al Sab {sabado.day} de {mes_domingo} {domingo.year}"
                else:
                    label = f"Del Dom {domingo.day} de {mes_domingo} al Sab {sabado.day} de {mes_sabado} {domingo.year}"

                resultado.append(SemanaDisponible(
                    label=label,
                    fecha_inicio=domingo,
                    fecha_fin=sabado
                ))

        resultado.sort(key=lambda x: x.fecha_inicio, reverse=True)
        return resultado

    def obtener_reporte_semanal(self, fecha_inicio: date, fecha_fin: date) -> List[ReporteTerritorioSemanal]:
        """Obtiene y mapea los territorios trabajados en la semana dada."""
        datos = self.repo.obtener_reporte_por_rango(fecha_inicio, fecha_fin)
        return [ReporteTerritorioSemanal(**item) for item in datos]
    
    