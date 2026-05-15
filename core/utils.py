from datetime import date
import re

def obtener_anio_servicio(fecha: date = None) -> int:
    """Retorna el año de servicio (Septiembre n a Agosto m)."""
    if fecha is None:
        fecha = date.today()
    # Si estamos en Septiembre (9) o más, ya es el año siguiente
    return fecha.year + 1 if fecha.month >= 9 else fecha.year

def extraer_info_planilla(nombre_str: str):
    """
    Extrae el número de planilla y el año de un string como:
    '2° Planilla, Casas 21-40; (2026)' -> devuelve (2, 2026)
    """
    try:
        # Busca el primer número al inicio
        numero = int(re.search(r'^(\d+)', nombre_str).group(1))
        # Busca el año entre paréntesis
        anio = int(re.search(r'\((\d{4})\)', nombre_str).group(1))
        return numero, anio
    except:
        return None, None