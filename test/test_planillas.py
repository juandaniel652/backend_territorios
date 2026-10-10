from domain.planilla.service import detectar_zona_por_nombre
import sys
from pathlib import Path

# Agregar el directorio raíz 'backend' al path de Python
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

def test_lectura_de_nombre():

    # 1. Casos de prueba: nombre de planilla y número de territorio
    casos_prueba = [
        ("1° Planilla, Casas 1-20; (2026)", None, 1),
        ("2° Planilla, Casas 21-40; (2026)", None, 2),
        ("3° Planilla, Casas 41-60; (2026)", None, 3),
        ("Planilla Especial", 15, 1),  # Fallback por número de territorio
        ("Planilla Especial", 35, 2),  # Fallback por número de territorio
        ("Planilla Especial", 50, 3),  # Fallback por número de territorio
    ]

    for nombre_planilla, numero_territorio, zona_esperada in casos_prueba:
        zona_calculada = detectar_zona_por_nombre(nombre_planilla, numero_territorio)
        assert zona_calculada == zona_esperada, f"Fallo en {nombre_planilla} con territorio {numero_territorio}"