"""
backend/domain/planilla/service.py
"""
import os
import traceback
from datetime import datetime, date
import gspread

from core.google_sheets import obtener_cliente_sheets
from core.utils import obtener_anio_servicio
import utils.recorrer_filas as archivo

VALORES_FILAS = [15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80, 85, 90, 95, 100, 105, 110]


class PlanillaService:

    def __init__(self, planilla_repo=None, territorio_service=None) -> None:
        self.planilla_repo = planilla_repo
        self.territorio_service = territorio_service
        self.base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    def detectar_zona_por_nombre(self, nombre_planilla: str) -> int:
        nombre_lower = nombre_planilla.lower()
        if "1-20" in nombre_lower:
            return 1
        elif "21-40" in nombre_lower:
            return 2
        elif "41-60" in nombre_lower:
            return 3
        raise ValueError(f"No se pudo determinar la zona para la planilla: {nombre_planilla}")

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

    def sincronizar_registro_bisturi(self, datos_registro: dict):
        """
        Ubica y escribe quirúrgicamente un solo registro directo en Google Sheets.
        """
        print("=" * 60)
        print("🎯 DEBUG BISTURÍ (Escribiendo registro en Sheets):")
        print(f" -> Planilla: {datos_registro.get('nombre_planilla')}")
        print(f" -> Territorio: {datos_registro.get('numero_territorio')}")
        print(f" -> Fila lógica (1-5): {datos_registro.get('fila')}")
        print(f" -> Conductor: {datos_registro.get('conductor')}")
        print("=" * 60)

        try:
            client = obtener_cliente_sheets()

            nombre_planilla = datos_registro["nombre_planilla"]
            numero_territorio = datos_registro["numero_territorio"]
            fila_logica = datos_registro["fila"]  # 1 a 5
            salida_idx = fila_logica - 1

            # 1. Determinar zona e inicio
            zona = self.detectar_zona_por_nombre(nombre_planilla)
            inicio_territorio = 1 if zona == 1 else (21 if zona == 2 else 41)

            if numero_territorio < inicio_territorio or numero_territorio >= inicio_territorio + len(VALORES_FILAS):
                print(f"[SHEETS OMITIDO] Territorio {numero_territorio} fuera de zona {zona}")
                return

            # 2. Fila base directa
            territorio_idx = numero_territorio - inicio_territorio
            fila_base = VALORES_FILAS[territorio_idx]

            # 3. Abrir o crear planilla de un tiro
            try:
                spreadsheet = client.open(nombre_planilla)
            except gspread.exceptions.SpreadsheetNotFound:
                print(f"⚠️ [SHEETS] No se encontró '{nombre_planilla}'. Creándola...")
                try:
                    spreadsheet = client.create(nombre_planilla)
                except Exception as create_err:
                    print(f"❌ [SHEETS ERROR] No se pudo crear: {str(create_err)}")
                    return

            sheet = spreadsheet.sheet1

            # 4. Localización exacta en coordenadas
            celdas_cond = archivo.localizar_celda_conductor(fila_base, 2)
            celdas_asig = archivo.localizar_celda_fecha_asignado(fila_base, 2)
            celdas_comp = archivo.localizar_celda_fecha_completado(fila_base, 2)

            c_cond = celdas_cond[salida_idx]
            c_asig = celdas_asig[salida_idx]
            c_comp = celdas_comp[salida_idx]

            rango_cond = gspread.utils.rowcol_to_a1(c_cond[0], c_cond[1])
            rango_asig = gspread.utils.rowcol_to_a1(c_asig[0], c_asig[1])
            rango_comp = gspread.utils.rowcol_to_a1(c_comp[0], c_comp[1])

            # 5. Formato de datos
            conductor_base = self.preparar_texto_conductor(
                datos_registro.get("conductor", ""), 
                datos_registro.get("cantidad_abarcado", "")
            )
            f_asig = self.formatear_fecha_ar(datos_registro.get("fecha_asignado"))
            f_comp = self.formatear_fecha_ar(datos_registro.get("fecha_completado"))

            if salida_idx == 4:  # Caso especial fila 5
                rango_fechas = f"{f_asig}\n{f_comp}" if f_comp else f_asig
                conductor_texto = f"{conductor_base}\n{rango_fechas}" if conductor_base else ""
                f_asig, f_comp = "", ""
                fuente_cond = 12
            else:
                conductor_texto = conductor_base
                fuente_cond = self.calcular_tamanio_fuente_conductor(conductor_texto) if conductor_texto else 12

            # 6. Escritura directa
            lista_actualizaciones = [
                {'range': rango_cond, 'values': [[conductor_texto]]},
                {'range': rango_asig, 'values': [[f_asig]]},
                {'range': rango_comp, 'values': [[f_comp]]}
            ]

            lista_formatos = [
                {
                    "range": rango_cond,
                    "format": {
                        "textFormat": {"fontFamily": "Arial", "fontSize": fuente_cond},
                        "horizontalAlignment": "CENTER", 
                        "verticalAlignment": "MIDDLE"
                    }
                }
            ]
            for r_fecha in [rango_asig, rango_comp]:
                lista_formatos.append({
                    "range": r_fecha,
                    "format": {
                        "textFormat": {"fontFamily": "Arial", "fontSize": 32},
                        "horizontalAlignment": "CENTER", 
                        "verticalAlignment": "MIDDLE"
                    }
                })

            sheet.batch_update(lista_actualizaciones, value_input_option='USER_ENTERED')
            sheet.batch_format(lista_formatos)

            print(f"🎯 [SHEETS SUCCESS] Ubicado Territorio {numero_territorio} en '{nombre_planilla}'")

        except Exception as e:
            print("[SHEETS ERROR] Falló al sincronizar registro:")
            traceback.print_exc()