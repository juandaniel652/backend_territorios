from datetime import datetime
from core.utils import calcular_nombre_planilla_desde_salida

def test_confrontar_formato_nombre_real_vs_esperado():
    # 1. Datos de entrada según la firma real
    numero_territorio = 25  # Cae en el rango "Casas 21-40"
    indice_salida_global = 5  # Representa la salida para calcular el ciclo
    fecha_asignado = datetime(2026, 3, 15)

    # 2. Ejecución de la función real
    resultado_dict = calcular_nombre_planilla_desde_salida(
        numero_territorio=numero_territorio,
        indice_salida_global=indice_salida_global,
        fecha_asignado=fecha_asignado
    )

    print(f"\n[DICCIONARIO DEVUELTO POR LA FUNCIÓN REAL]:\n{resultado_dict}")

    # 3. LO QUE DEBERÍA DAR (Regla de negocio esperada)
    nombre_esperado = "2° Planilla, Casas 21-40; (2026)"
    
    # Extraemos la clave donde la función guarda el nombre
    nombre_calculado_real = resultado_dict.get("nombre_planilla")

    print(f"\n[ESPERADO]: {repr(nombre_esperado)}")
    print(f"[OBTENIDO]: {repr(nombre_calculado_real)}")

    assert nombre_calculado_real == nombre_esperado