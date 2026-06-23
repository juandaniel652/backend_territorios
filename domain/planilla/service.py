from core.utils import obtener_anio_servicio
import os
from core.google_sheets import obtener_cliente_sheets


class PlanillaService:

    def __init__(self, planilla_repo=None) -> None:
        self.planilla_repo = planilla_repo
        # Obtenemos la ruta base para leer las coordenadas asignadas a los txt si los seguís usando
        self.base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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


    def sincronizar_registro_bisturi(self, datos_registro: dict):
        """
        Toma una asignación enriquecida recién creada o confirmada y la inyecta 
        exactamente en su posición calculada en Google Sheets.
        """
        try:
            client = obtener_cliente_sheets()
            
            # 1. Abrir la hoja usando el nombre de la planilla autocalculado
            # (Asegúrate de que el documento en tu Drive se llame exactamente igual que 'nombre_planilla')
            spreadsheet = client.open(datos_registro["nombre_planilla"])
            sheet = spreadsheet.sheet1  # O la pestaña correspondiente

            numero_territorio = datos_registro["numero_territorio"]
            fila_calculada = datos_registro["fila"]  # 1 a 5

            # 2. Tu lógica del Bisturí para mapear columnas. 
            # Aquí acoplás la matriz exacta que tenías en 'recorrer_fila_planilla.py'
            # Ejemplo simplificado si mapeás dinámicamente según el número del territorio:
            columna_inicio = self._calcular_columna_base(numero_territorio)
            
            # Calculamos la fila real de Google Sheets sumando el offset de las cabeceras
            fila_real_sheets = self._calcular_fila_sheets(numero_territorio, fila_calculada)

            # 3. Preparar el lote de celdas a actualizar para realizar una sola llamada de red (Batch Update)
            # Mapeo típico: Conductor, Fecha Asignado, Fecha Completado, Cantidad Abarcado.
            valores = [
                datos_registro["conductor"],
                datos_registro["fecha_asignado"].strftime("%Y-%m-%d") if hasattr(datos_registro["fecha_asignado"], "strftime") else datos_registro["fecha_asignado"],
                datos_registro["fecha_completado"].strftime("%Y-%m-%d") if datos_registro.get("fecha_completado") and hasattr(datos_registro["fecha_completado"], "strftime") else (datos_registro.get("fecha_completado") or ""),
                datos_registro["cantidad_abarcado"] or ""
            ]

            # Determinamos el rango de la celda (Ej: B5:E5)
            rango = f"{self._numero_a_letra_columna(columna_inicio)}{fila_real_sheets}:{self._numero_a_letra_columna(columna_inicio + len(valores) - 1)}{fila_real_sheets}"
            
            # Actualización directa
            sheet.update(range_name=rango, values=[valores])
            print(f"[SHEETS SUCCESS] Territorio {numero_territorio} (Fila Lógica {fila_calculada}) sincronizado en {datos_registro['nombre_planilla']} (Rango {rango})")

        except Exception as e:
            # Capturamos el error para que un fallo de red o credenciales en Sheets NO rompa la BD del Backend

            pass
    
    
    def _calcular_columna_base(self, numero_territorio: int) -> int:
        """Traduce el número de territorio a su columna de inicio en la plantilla (antiguo buscar_coordenadas)"""
        # Tu lógica matemática actual va aquí (Ej: si va en bloques de 4 columnas por territorio)
        # Por ejemplo, si el territorio 1 arranca en columna B (2), el 2 en columna F (6), etc:
        return 2 + ((numero_territorio - 1) % 20) * 5  # Ajustalo a tu diseño de sábana real

    def _calcular_fila_sheets(self, numero_territorio: int, fila_calculada: int) -> int:
        """Ajusta las filas en base al diseño físico de tu planilla de Sheets"""
        # Si cada bloque de territorio empieza por ejemplo en la fila 3, la fila lógica 1 será la 4, etc.
        offset_cabecera = 3
        return offset_cabecera + fila_calculada

    def _numero_a_letra_columna(self, n: int) -> str:
        """Convierte un índice numérico de columna (1=A, 2=B) a letra de Excel/Sheets"""
        string = ""
        while n > 0:
            n, remainder = divmod(n - 1, 26)
            string = chr(65 + remainder) + string
        return string