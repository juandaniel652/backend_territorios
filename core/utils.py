from datetime import date

def obtener_anio_servicio(fecha: date = None) -> int:
    """Retorna el año de servicio (Septiembre n a Agosto m)."""
    if fecha is None:
        fecha = date.today()
    # Si estamos en Septiembre (9) o más, ya es el año siguiente
    return fecha.year + 1 if fecha.month >= 9 else fecha.year