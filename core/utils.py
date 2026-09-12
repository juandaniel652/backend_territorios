# core/utils.py
from datetime import date, datetime
import re

def obtener_anio_servicio(fecha: date = None) -> int:
    """Retorna el año de servicio teocrático (Septiembre n a Agosto m)."""
    if fecha is None:
        fecha = date.today()
    return fecha.year + 1 if fecha.month >= 9 else fecha.year

def extraer_info_planilla(nombre_str: str):
    """
    Extrae el número de planilla y el año de un string como:
    '2° Planilla, Casas 21-40; (2026)' -> devuelve (2, 2026)
    """
    try:
        numero = int(re.search(r'^(\d+)', nombre_str).group(1))
        anio = int(re.search(r'\((\d{4})\)', nombre_str).group(1))
        return numero, anio
    except Exception:
        return None, None

def calcular_nombre_planilla_desde_salida(
    numero_territorio: int, 
    indice_salida_global: int, 
    fecha_asignado,
    historial_existente: list = None
) -> dict:
    """
    Dada una salida absoluta (0-indexed) y su fecha:
    - Asigna el ciclo global (1 ciclo = 5 salidas)
    - Asigna la fila dentro de la planilla (1 a 5)
    - Genera el nombre de planilla relativo al año del servicio teocrático.
    """
    if 1 <= numero_territorio <= 20:
        rango_txt = "Casas 1-20"
    elif 21 <= numero_territorio <= 40:
        rango_txt = "Casas 21-40"
    elif 41 <= numero_territorio <= 60:
        rango_txt = "Casas 41-60"
    else:
        rango_txt = f"Territorio {numero_territorio}"

    fila = (indice_salida_global % 5) + 1
    ciclo_global = (indice_salida_global // 5) + 1

    if isinstance(fecha_asignado, str):
        fecha_dt = datetime.strptime(fecha_asignado.split("T")[0], "%Y-%m-%d").date()
    elif isinstance(fecha_asignado, datetime):
        fecha_dt = fecha_asignado.date()
    else:
        fecha_dt = fecha_asignado
        
    anio_servicio = obtener_anio_servicio(fecha_dt)

    num_planilla_anio = 1

    if historial_existente:
        ciclos_del_anio = set()
        for reg in historial_existente:
            f_val = reg.get("fecha_asignado") if isinstance(reg, dict) else getattr(reg, "fecha_asignado", None)
            if not f_val:
                continue
            
            if isinstance(f_val, str):
                reg_dt = datetime.strptime(f_val.split("T")[0], "%Y-%m-%d").date()
            elif isinstance(f_val, datetime):
                reg_dt = f_val.date()
            else:
                reg_dt = f_val
                
            reg_anio_servicio = obtener_anio_servicio(reg_dt)
            reg_ciclo = reg.get("ciclo") if isinstance(reg, dict) else getattr(reg, "ciclo", None)
            
            if reg_anio_servicio == anio_servicio and reg_ciclo is not None and reg_ciclo < ciclo_global:
                ciclos_del_anio.add(reg_ciclo)
        
        num_planilla_anio = len(ciclos_del_anio) + 1

    nombre_planilla = f"{num_planilla_anio}° Planilla, {rango_txt}; ({anio_servicio})"

    return {
        "ciclo": ciclo_global,
        "fila": fila,
        "rango_txt": rango_txt,
        "anio": anio_servicio,
        "num_planilla_anio": num_planilla_anio,
        "nombre_planilla": nombre_planilla
    }