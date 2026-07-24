import os
import traceback
from datetime import datetime, date
import time
from collections import defaultdict
import gspread
from gspread.exceptions import SpreadsheetNotFound, APIError

from core.google_sheets import obtener_cliente_sheets
from core.utils import obtener_anio_servicio
import utils.recorrer_filas as archivo

# Filas físicas fijas por territorio
VALORES_FILAS = [15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80, 85, 90, 95, 100, 105, 110]


class PlanillaService:

    def __init__(self, planilla_repo=None, territorio_service=None) -> None:
        self.planilla_repo = planilla_repo
        self.territorio_service = territorio_service
        self.base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    @staticmethod
    def generar_nombre_automatico(zona: int, ciclo: int, planilla_repo=None) -> str:
        nombres_fijos = {
            1: {
                1: '1° Planilla, Casas 1-20; (2025)',
                2: '2° Planilla, Casas 1-20; (2025)',
                3: '3° Planilla, Casas 1-20; (2025)',
                4: '1° Planilla, Casas 1-20; (2026)'
            },
            2: {
                1: '2° Planilla, Casas 21-40; (2024)',
                2: '3° Planilla, Casas 21-40; (2024)',
                3: '4° Planilla, Casas 21-40; (2024)',
                4: '1° Planilla, Casas 21-40; (2025)',
                5: '1° Planilla, Casas 21-40; (2026)',
                6: '2° Planilla, Casas 21-40; (2026)'
            },
            3: {
                1: '1° Planilla, Casas 41-60; (2024)',
                2: '2° Planilla, Casas 41-60; (2024)',
                3: '1⁰ Planilla, Casas 41-60; (2025)',
                4: '1ª Planilla, Casas 41-60; (2026)'
            }
        }

        nombre_mapeado = nombres_fijos.get(zona, {}).get(ciclo)
        if nombre_mapeado:
            return nombre_mapeado

        anio_servicio = obtener_anio_servicio()
        proximo_numero = 1

        if planilla_repo:
            try:
                ultima_planilla_db = planilla_repo.obtener_ultima_planilla_creada(zona, ciclo)
                if ultima_planilla_db and ultima_planilla_db.nombre_planilla:
                    from utils.recorrer_filas import extraer_info_planilla
                    num_anterior, anio_anterior = extraer_info_planilla(ultima_planilla_db.nombre_planilla)
                    
                    if num_anterior is not None and anio_anterior is not None:
                        if anio_anterior == anio_servicio:
                            proximo_numero = num_anterior + 1
            except Exception:
                proximo_numero = ciclo
        else:
            proximo_numero = ciclo

        rangos = {1: "1-20", 2: "21-40", 3: "41-60"}
        rango_txt = rangos.get(zona, f"Zona {zona}")

        return f"{proximo_numero}° Planilla, Casas {rango_txt}; ({anio_servicio})"

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

    @staticmethod
    def abrir_o_buscar_planilla(client: gspread.Client, nombre_esperado: str, max_retries: int = 3):
        """Abre una planilla por nombre con reintentos y fallback flexible."""
        for intento in range(max_retries):
            try:
                return client.open(nombre_esperado)
            except SpreadsheetNotFound:
                break
            except APIError as api_err:
                if api_err.response.status_code in [500, 502, 503, 504, 429]:
                    print(f"⚠️ [SHEETS RETRY] Error {api_err.response.status_code}. Reintentando ({intento + 1}/{max_retries})...")
                    time.sleep(2 ** intento)
                else:
                    raise api_err

        print(f"⚠️ [SHEETS ADVERTENCIA] No se encontró la planilla exacta: '{nombre_esperado}'. Buscando similares...")
        try:
            todas_las_planillas = client.openall()
            nombre_normalizado = " ".join(nombre_esperado.strip().lower().split())
            for sheet in todas_las_planillas:
                sheet_normalizado = " ".join(sheet.title.strip().lower().split())
                if sheet_normalizado == nombre_normalizado:
                    print(f"💡 [SHEETS COINCIDENCIA] Usando '{sheet.title}'")
                    return sheet

            print(f"❌ [SHEETS NOMBRE INCORRECTO] Debes crear o renombrar en Drive a: '{nombre_esperado}'")
            return None
        except Exception as err:
            print(f"❌ [SHEETS ERROR] Error buscando planillas: {str(err)}")
            return None

    def calcular_payload_celda(self, asig) -> tuple:
        """
        Calcula los rangos A1 y los formatos de celda para sincronizar con Google Drive.
        1. Reinicia las filas físicas (15 a 110) cada 20 territorios (1-20, 21-40, etc.).
        2. Usa las funciones del módulo 'archivo' para localizar celdas por ciclo (1 a 5).
        """
        # 1. Obtener fila física base en Google Sheets (ej: Territorio 21 -> Fila 15)
        numero_territorio = asig.fila
        indice_fila = (numero_territorio - 1) % len(VALORES_FILAS)
        fila_base_sheets = VALORES_FILAS[indice_fila]

        # 2. Invocación a tus funciones originales de archivo (Columna Base B = 2)
        COLUMNA_BASE_B = 2

        celdas_cond = archivo.localizar_celda_conductor(fila_base_sheets, COLUMNA_BASE_B)
        celdas_asig = archivo.localizar_celda_fecha_asignado(fila_base_sheets, COLUMNA_BASE_B)
        celdas_comp = archivo.localizar_celda_fecha_completado(fila_base_sheets, COLUMNA_BASE_B)

        # 3. Selección de la columna horizontal según el ciclo (1 a 5 -> índice 0 a 4)
        salida_idx = max(0, min(asig.ciclo - 1, 4))

        c_cond = celdas_cond[salida_idx]
        c_asig = celdas_asig[salida_idx]
        c_comp = celdas_comp[salida_idx]

        # 4. Conversión de coordenadas (fila, columna) a notación A1 (ej: "D15", "D17")
        rango_cond = gspread.utils.rowcol_to_a1(c_cond[0], c_cond[1])
        rango_asig = gspread.utils.rowcol_to_a1(c_asig[0], c_asig[1])
        rango_comp = gspread.utils.rowcol_to_a1(c_comp[0], c_comp[1])

        # 5. Formateo de valores de texto
        conductor_base = self.preparar_texto_conductor(asig.conductor, asig.cantidad_abarcado)
        f_asig = self.formatear_fecha_ar(asig.fecha_asignado)
        f_comp = self.formatear_fecha_ar(asig.fecha_completado)

        if salida_idx == 4:  # Salida 5 (columna lateral)
            rango_fechas = f"{f_asig}\n{f_comp}" if f_comp else f_asig
            conductor_texto = f"{conductor_base}\n{rango_fechas}"
            f_asig, f_comp = "", ""
            fuente_cond = 12
        else:
            conductor_texto = conductor_base
            fuente_cond = self.calcular_tamanio_fuente_conductor(conductor_texto)

        actualizaciones = [
            {'range': rango_cond, 'values': [[conductor_texto]]},
            {'range': rango_asig, 'values': [[f_asig]]},
            {'range': rango_comp, 'values': [[f_comp]]}
        ]

        formatos = [
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
        ]

        return actualizaciones, formatos

    def sincronizar_territorio_completo_a_drive(self, numero_territorio: int):
        """Orquesta la sincronización en lote agrupada por planilla."""
        if not self.territorio_service:
            raise ValueError("Se requiere territorio_service para obtener el historial posicionado.")

        historial_out = self.territorio_service.obtener_historial_posicionado(numero_territorio)

        if not historial_out or not historial_out.historial_posicionado:
            print(f"[SHEETS ADVERTENCIA] El territorio {numero_territorio} no tiene asignaciones.")
            return

        client = obtener_cliente_sheets()
        
        # Agrupar las operaciones por planilla para hacer BATCHING (1 request por archivo)
        operaciones_por_planilla = defaultdict(lambda: {"updates": [], "formats": []})

        for asig in historial_out.historial_posicionado:
            actualizaciones, formatos = self.calcular_payload_celda(asig)
            operaciones_por_planilla[asig.nombre_planilla]["updates"].extend(actualizaciones)
            operaciones_por_planilla[asig.nombre_planilla]["formats"].extend(formatos)

        # Ejecutar peticiones masivas
        for nombre_planilla, datos in operaciones_por_planilla.items():
            spreadsheet = self.abrir_o_buscar_planilla(client, nombre_planilla)
            if not spreadsheet:
                print(f"⏩ [SHEETS SALTADO] Omitiendo sincronización para '{nombre_planilla}' (no disponible).")
                continue

            try:
                sheet = spreadsheet.sheet1
                if datos["updates"]:
                    sheet.batch_update(datos["updates"], value_input_option='USER_ENTERED')
                if datos["formats"]:
                    sheet.batch_format(datos["formats"])
                print(f"✅ [SHEETS SUCCESS] Planilla '{nombre_planilla}' sincronizada en lote.")
            except Exception as e:
                print(f"❌ [SHEETS ERROR] Fallo al actualizar '{nombre_planilla}': {str(e)}")