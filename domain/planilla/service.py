import os
import traceback
from datetime import datetime, date
from typing import Any, Optional
import gspread

from core.google_sheets import get_sheets
from core.utils import obtener_anio_servicio, calcular_nombre_planilla_desde_salida
import utils.recorrer_filas as archivo

VALORES_FILAS = [15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80, 85, 90, 95, 100, 105, 110]


class PlanillaService:

    def __init__(self, planilla_repo=None, historial_repo=None) -> None:
        self.planilla_repo = planilla_repo
        self.historial_repo = historial_repo
        self.base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    # ============================================
    # Lógica de elección y validación de planilla

    def validar_planilla_en_sheets(self, client: gspread.Client, nombre_planilla: str) -> Optional[gspread.Spreadsheet]:
        """
        Intenta abrir el archivo de Google Sheets. Si no existe exactamente
        con ese nombre, retorna None en lugar de romper la ejecución.
        """
        try:
            spreadsheet = client.open(nombre_planilla.strip())
            return spreadsheet
        except gspread.exceptions.SpreadsheetNotFound:
            print(f"❌ [SHEETS ERROR] La planilla '{nombre_planilla}' no existe en Google Drive.")
            return None
        except Exception as e:
            print(f"⚠️ [SHEETS ERROR] Error al intentar abrir '{nombre_planilla}': {e}")
            return None

    def detectar_zona_por_nombre(self, nombre_planilla: str, numero_territorio: int = None) -> int:
        """
        Determina la zona por el nombre de la planilla. Si no coincide el string,
        usa el número de territorio como fallback seguro.
        """
        nombre_lower = nombre_planilla.lower()
        if "1-20" in nombre_lower or "casas 1" in nombre_lower:
            return 1
        elif "21-40" in nombre_lower or "casas 21" in nombre_lower:
            return 2
        elif "41-60" in nombre_lower or "casas 41" in nombre_lower:
            return 3
        
        # Fallback por número de territorio si la cadena de texto no coincide
        if numero_territorio is not None:
            if 1 <= numero_territorio <= 20:
                return 1
            elif 21 <= numero_territorio <= 40:
                return 2
            elif 41 <= numero_territorio <= 60:
                return 3

        raise ValueError(f"No se pudo determinar la zona para la planilla: {nombre_planilla}")

    def sincronizar_registro_bisturi(self, datos_registro: dict):
        """
        Inyecta una única asignación en tiempo real en las coordenadas físicas 
        exactas de Google Sheets calculadas por 'recorrer_fila_planilla'.
        """
        print("="*60)
        print(f"DEBUG BISTURÍ:")
        print(f" -> Planilla a abrir en Drive: {datos_registro.get('nombre_planilla')}")
        print(f" -> Territorio: {datos_registro.get('numero_territorio')}")
        print(f" -> Fila lógica (1-5): {datos_registro.get('fila')}")
        print(f" -> Conductor: {datos_registro.get('conductor')}")
        print("="*60)
        
        try:
            nombre_planilla = datos_registro.get("nombre_planilla")
            if not nombre_planilla:
                print("❌ [SHEETS OMITIDO] No se proporcionó un nombre de planilla válido.")
                return

            client = get_sheets()
            
            # 1. Validar que la planilla exista en Drive antes de operar
            spreadsheet = self.validar_planilla_en_sheets(client, nombre_planilla)
            if not spreadsheet:
                print(f"❌ [SHEETS CANCELADO] Omitiendo sincronización porque la planilla '{nombre_planilla}' no existe en Drive.")
                return

            numero_territorio = datos_registro["numero_territorio"]
            fila_logica = datos_registro["fila"]  # 1 a 5 (salida_idx + 1)
            salida_idx = fila_logica - 1

            # 2. Resolver Zona mediante el nombre
            zona = self.detectar_zona_por_nombre(nombre_planilla, numero_territorio)
            inicio_territorio = 1 if zona == 1 else (21 if zona == 2 else 41)
            
            if numero_territorio < inicio_territorio or numero_territorio >= inicio_territorio + len(VALORES_FILAS):
                print(f"[SHEETS OMITIDO] El territorio {numero_territorio} está fuera del rango lógico de la zona {zona}")
                return

            territorio_idx = numero_territorio - inicio_territorio
            fila_base = VALORES_FILAS[territorio_idx]
            sheet = spreadsheet.sheet1

            # 3. Localizar coordenadas físicas exactas
            celdas_cond = archivo.localizar_celda_conductor(fila_base, 2)
            celdas_asig = archivo.localizar_celda_fecha_asignado(fila_base, 2)
            celdas_comp = archivo.localizar_celda_fecha_completado(fila_base, 2)

            c_cond = celdas_cond[salida_idx]
            c_asig = celdas_asig[salida_idx]
            c_comp = celdas_comp[salida_idx]

            # Convertir coordenadas numéricas a formato A1 (Ej: "B15")
            rango_cond = gspread.utils.rowcol_to_a1(c_cond[0], c_cond[1])
            rango_asig = gspread.utils.rowcol_to_a1(c_asig[0], c_asig[1])
            rango_comp = gspread.utils.rowcol_to_a1(c_comp[0], c_comp[1])

            # 4. Construir Payload considerando celdas combinadas y salida_idx
            conductor_base = self.preparar_texto_conductor(datos_registro["conductor"], datos_registro["cantidad_abarcado"])
            f_asig = self.formatear_fecha_ar(datos_registro["fecha_asignado"])
            f_comp = self.formatear_fecha_ar(datos_registro["fecha_completado"])

            lista_actualizaciones = []
            lista_formatos = []

            if salida_idx == 4:  # Salida 5 (Quinta fila del bloque)
                rango_fechas = f"{f_asig}\n{f_comp}" if f_comp else f_asig
                conductor_texto = f"{conductor_base}\n{rango_fechas}" if rango_fechas else conductor_base
                
                lista_actualizaciones.append({'range': rango_cond, 'values': [[conductor_texto]]})
                lista_formatos.append({
                    "range": rango_cond,
                    "format": {
                        "textFormat": {"fontFamily": "Arial", "fontSize": 12},
                        "horizontalAlignment": "CENTER", 
                        "verticalAlignment": "MIDDLE"
                    }
                })
            else:  # Salidas 1 a 4
                conductor_texto = conductor_base
                fuente_cond = self.calcular_tamanio_fuente_conductor(conductor_texto)

                lista_actualizaciones.extend([
                    {'range': rango_cond, 'values': [[conductor_texto]]},
                    {'range': rango_asig, 'values': [[f_asig]]},
                    {'range': rango_comp, 'values': [[f_comp]]}
                ])

                lista_formatos.extend([
                    {
                        "range": rango_cond,
                        "format": {
                            "textFormat": {"fontFamily": "Arial", "fontSize": fuente_cond},
                            "horizontalAlignment": "CENTER", 
                            "verticalAlignment": "MIDDLE"
                        }
                    },
                    {
                        "range": rango_asig,
                        "format": {
                            "textFormat": {"fontFamily": "Arial", "fontSize": 32},
                            "horizontalAlignment": "CENTER", 
                            "verticalAlignment": "MIDDLE"
                        }
                    },
                    {
                        "range": rango_comp,
                        "format": {
                            "textFormat": {"fontFamily": "Arial", "fontSize": 32},
                            "horizontalAlignment": "CENTER", 
                            "verticalAlignment": "MIDDLE"
                        }
                    }
                ])

            # 5. Impacto atómico en Google Sheets
            sheet.batch_update(lista_actualizaciones, value_input_option='USER_ENTERED')
            sheet.batch_format(lista_formatos)
            
            print(f"[SHEETS SUCCESS] Sincronizado Territorio {numero_territorio} en Fila Física {fila_base} de la planilla: '{nombre_planilla}'")

        except Exception as e:
            print("[SHEETS ERROR] Falló la sincronización con Google Sheets:")
            traceback.print_exc()

    # ============================================
    # Métodos aplicados a formato y guardado visual en planilla
    
    def formatear_fecha_ar(self, f) -> str:
        if not f: return ""
        if isinstance(f, (date, datetime)): return f.strftime("%d/%m/%Y")
        f_str = str(f).strip()
        try: return datetime.strptime(f_str, "%Y-%m-%d").strftime("%d/%m/%Y")
        except ValueError:
            try: return datetime.strptime(f_str, "%d/%m/%Y").strftime("%d/%m/%Y")
            except ValueError: return f_str

    def calcular_tamanio_fuente_conductor(self, texto: str) -> int:
        largo = len(texto)
        if largo <= 14: return 36
        if largo >= 38: return 10
        tamanio_calculado = 36 - ((largo - 14) * (36 - 10) / (38 - 14))
        return int(round(tamanio_calculado))

    def preparar_texto_conductor(self, conductor: str, cantidad_abarcado: str) -> str:
        if cantidad_abarcado and str(cantidad_abarcado).strip().lower() != "completo":
            return f"{conductor} ({cantidad_abarcado})"
        return conductor