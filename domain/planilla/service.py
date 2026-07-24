import os
import traceback
from datetime import datetime, date
from typing import Optional  # <-- Agregado Optional
import gspread

from core.google_sheets import obtener_cliente_sheets
from core.utils import obtener_anio_servicio

# Importación relativa a la raíz del proyecto para localizar celdas
try:
    import utils.recorrer_filas as archivo
except ImportError:
    from core.utils import recorrer_filas as archivo  # Fallback si recorrer_filas está en core.utils

# Tus filas físicas fijas por territorio
VALORES_FILAS = [15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80, 85, 90, 95, 100, 105, 110]


class PlanillaService:

    def __init__(self, planilla_repo=None, territorio_service=None) -> None:
        self.planilla_repo = planilla_repo
        self.territorio_service = territorio_service
        self.base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    @staticmethod
    def obtener_anio_servicio(fecha: Optional[date] = None) -> int:
        f = fecha or date.today()
        # El año de servicio teocrático comienza el 1 de Septiembre
        return f.year + 1 if f.month >= 9 else f.year

    @staticmethod
    def generar_nombre_automatico(numero_territorio: int, ciclo: int, fecha: Optional[date] = None) -> str:
        anio = PlanillaService.obtener_anio_servicio(fecha)

        nombres_fijos = {
            1: {
                1: '1° Planilla, Casas 1-20; (2024)',
                2: '2° Planilla, Casas 1-20; (2025)',
                3: '3° Planilla, Casas 1-20; (2025)',
                4: '4° Planilla, Casas 1-20; (2026)',
            },
            2: {
                1: '1° Planilla, Casas 21-40; (2024)',
                2: '2° Planilla, Casas 21-40; (2025)',
                3: '3° Planilla, Casas 21-40; (2025)',
                4: '4° Planilla, Casas 21-40; (2025)',
                5: '1° Planilla, Casas 21-40; (2026)',
                6: '2° Planilla, Casas 21-40; (2026)',
            },
            3: {
                1: '1° Planilla, Casas 41-60; (2024)',
                2: '2° Planilla, Casas 41-60; (2025)',
            }
        }

        # 1. Búsqueda fija para históricos
        if numero_territorio in nombres_fijos and ciclo in nombres_fijos[numero_territorio]:
            return nombres_fijos[numero_territorio][ciclo]

        # 2. Lógica dinámica para nuevos ciclos (ej. ciclo 7 en territorio 2)
        rango_casas = f"Casas {(numero_territorio - 1) * 20 + 1}-{numero_territorio * 20}"
        return f"{ciclo}° Planilla, {rango_casas}; ({anio})"
    
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
        if not f: 
            return ""
        if isinstance(f, (date, datetime)): 
            return f.strftime("%d/%m/%Y")
        f_str = str(f).strip()
        try: 
            return datetime.strptime(f_str, "%Y-%m-%d").strftime("%d/%m/%Y")
        except ValueError:
            try: 
                return datetime.strptime(f_str, "%d/%m/%Y").strftime("%d/%m/%Y")
            except ValueError: 
                return f_str

    def calcular_tamanio_fuente_conductor(self, texto: str) -> int:
        largo = len(texto)
        if largo <= 14: 
            return 36
        if largo >= 38: 
            return 10
        tamanio_calculado = 36 - ((largo - 14) * (36 - 10) / (38 - 14))
        return int(round(tamanio_calculado))

    def preparar_texto_conductor(self, conductor: str, cantidad_abarcado: str) -> str:
        if cantidad_abarcado and str(cantidad_abarcado).strip().lower() != "completo":
            return f"{conductor} ({cantidad_abarcado})"
        return conductor

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
            client = obtener_cliente_sheets()
            
            nombre_planilla = datos_registro["nombre_planilla"]
            numero_territorio = datos_registro["numero_territorio"]
            fila_logica = datos_registro["fila"]  # 1 a 5 (salida_idx + 1)
            salida_idx = fila_logica - 1

            # 1. Resolver Zona mediante el nombre
            zona = self.detectar_zona_por_nombre(nombre_planilla)
            inicio_territorio = 1 if zona == 1 else (21 if zona == 2 else 41)
            
            if numero_territorio < inicio_territorio or numero_territorio >= inicio_territorio + len(VALORES_FILAS):
                print(f"[SHEETS OMITIDO] El territorio {numero_territorio} está fuera del rango lógico de la zona {zona}")
                return

            territorio_idx = numero_territorio - inicio_territorio
            fila_base = VALORES_FILAS[territorio_idx]

            # 2. Editar o insertar en hoja
            try:
                spreadsheet = client.open(nombre_planilla)
            except gspread.exceptions.SpreadsheetNotFound:
                print(f"⚠️ [SHEETS ADVERTENCIA] No se encontró la planilla '{nombre_planilla}'. Intentando crearla...")
                try:
                    spreadsheet = client.create(nombre_planilla)
                    print(f"✨ [SHEETS CREADO] Se generó automáticamente el archivo físico en Drive: '{nombre_planilla}'")
                except Exception as create_err:
                    print(f"❌ [SHEETS ERROR] No se pudo crear la planilla en Drive: {str(create_err)}")
                    return
            
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

            # 4. Construir Payload estético original
            conductor_base = self.preparar_texto_conductor(datos_registro["conductor"], datos_registro["cantidad_abarcado"])
            f_asig = self.formatear_fecha_ar(datos_registro["fecha_asignado"])
            f_comp = self.formatear_fecha_ar(datos_registro["fecha_completado"])

            if salida_idx == 4:  # Caso especial para la última fila física del bloque
                rango_fechas = f"{f_asig}\n{f_comp}" if f_comp else f_asig
                conductor_texto = f"{conductor_base}\n{rango_fechas}"
                f_asig, f_comp = "", ""
                fuente_cond = 12
            else:
                conductor_texto = conductor_base
                fuente_cond = self.calcular_tamanio_fuente_conductor(conductor_texto)

            # 5. Organizar actualizaciones y formatos estilo Batch
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
                        "horizontalAlignment": "CENTER", "verticalAlignment": "MIDDLE"
                    }
                }
            ]
            for r_fecha in [rango_asig, rango_comp]:
                lista_formatos.append({
                    "range": r_fecha,
                    "format": {
                        "textFormat": {"fontFamily": "Arial", "fontSize": 32},
                        "horizontalAlignment": "CENTER", "verticalAlignment": "MIDDLE"
                    }
                })

            # 6. Impactar de manera atómica
            sheet.batch_update(lista_actualizaciones, value_input_option='USER_ENTERED')
            sheet.batch_format(lista_formatos)
            
            print(f"[SHEETS SUCCESS] Sincronizado Territorio {numero_territorio} en Fila Física {fila_base} de la planilla: '{nombre_planilla}'")

        except Exception as e:
            print("[SHEETS ERROR] Falló la sincronización con Google Sheets:")
            traceback.print_exc()     
            
    def sincronizar_territorio_completo_a_drive(self, numero_territorio: int):
        """
        Sincroniza todas las asignaciones de un territorio en Drive respetando 
        estrictamente el historial posicionado.
        """
        if not self.territorio_service:
            raise ValueError("Se requiere territorio_service para obtener el historial posicionado.")

        # 1. Obtener la verdad absoluta trazada por el historial posicionado
        historial_out = self.territorio_service.obtener_historial_posicionado(numero_territorio)
        
        if not historial_out.historial_posicionado:
            print(f"[SHEETS ADVERTENCIA] El territorio {numero_territorio} no tiene asignaciones para sincronizar.")
            return

        # 2. Iterar sobre las asignaciones ya posicionadas y sincronizar en Sheets
        for asig in historial_out.historial_posicionado:
            datos_registro = {
                "nombre_planilla": asig.nombre_planilla,
                "numero_territorio": numero_territorio,
                "fila": asig.fila,  # 1 a 5
                "conductor": asig.conductor,
                "cantidad_abarcado": asig.cantidad_abarcado,
                "fecha_asignado": asig.fecha_asignado,
                "fecha_completado": asig.fecha_completado,
            }
            # Llama a la función quirúrgica con coordenadas exactas
            self.sincronizar_registro_bisturi(datos_registro)