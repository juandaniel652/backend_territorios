from core.utils import obtener_anio_servicio

class PlanillaService:
    @staticmethod
    def generar_nombre_automatico(zona: int, ciclo: int) -> str:
        anio_servicio = obtener_anio_servicio()
        
        # Diccionario de rangos por zona
        rangos = {
            1: "Casas 1-20",
            2: "Casas 21-40",
            3: "Casas 41-60"
        }
        rango = rangos.get(zona, f"Zona {zona}")
        
        # AQUÍ ESTÁ EL TRUCO PARA EL NÚMERO DE PLANILLA:
        # Necesitamos saber cuántas planillas de este mismo 'anio_servicio'
        # existen para esta zona para poner "1°", "2°", etc.
        # Por ahora, una lógica simple basada en el ciclo (mientras no guardemos en DB):
        # (Esto es lo que el Service de Territorio usará como 'Sugerencia')
        
        return f"{rango}; ({anio_servicio})"