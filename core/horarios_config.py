"""
core/horarios_config.py
Configuración de la semana normal y diccionarios de semanas especiales (ancladas por domingo).
"""
from datetime import date

# 🌟 1. PATRÓN NORMAL DE LA CONGREGACIÓN (14 SLOTS TOTALES)
SEMANA_NORMAL = {
    (0, "AM"): False, # Lunes AM
    (0, "PM"): True,  # Lunes PM
    (1, "AM"): True,  # Martes AM
    (1, "PM"): True,  # Martes PM
    (2, "AM"): True,  # Miércoles AM
    (2, "PM"): False, # Miércoles PM
    (3, "AM"): True,  # Jueves AM
    (3, "PM"): True,  # Jueves PM
    (4, "AM"): True,  # Viernes AM
    (4, "PM"): True,  # Viernes PM
    (5, "AM"): True,  # Sábado AM
    (5, "PM"): True,  # Sábado PM
    (6, "AM"): False, # Domingo AM
    (6, "PM"): False, # Domingo PM
}

# 🌟 2. REGISTRO DE SEMANAS ESPECIALES (SEMANA_ESPECIAL_N)
# Cada una se ancla al DOMINGO que marca la transición/referencia de esa semana.
# Nacen por defecto con todo en False y solo prendes en True las que operan.
SEMANAS_ESPECIALES = {
    # SEMANA_ESPECIAL_1 (Ej: Asamblea de Circuito / Visita)
    date(2026, 10, 11): {
        "nombre": "SEMANA_ESPECIAL_1",
        "patron": {
            (0, "AM"): False,
            (0, "PM"): False, 
            (1, "AM"): True,
            (1, "PM"): True,
            (2, "AM"): True,
            (2, "PM"): True,
            (3, "AM"): False,
            (3, "PM"): False,
            (4, "AM"): False,
            (4, "PM"): False,
            (5, "AM"): False,  
            (5, "PM"): False,
            (6, "AM"): False,
            (6, "PM"): False,
        }
    },
    
    # Aquí puedes seguir añadiendo futuras semanas especiales fácilmente:
    # date(2026, 12, 20): {
    #     "nombre": "SEMANA_ESPECIAL_2",
    #     "patron": { ... }
    # }
}