"""
backend/domain/planilla/service.py
"""
import os
import traceback
from datetime import datetime, date
import gspread

from core.google_sheets import get_sheets
from core.utils import obtener_anio_servicio
# Importamos tus localizadores nativos
import utils.recorrer_filas as archivo

# Tus filas físicas fijas por territorio
VALORES_FILAS = [15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80, 85, 90, 95, 100, 105, 110]


class PlanillaService:

    def __init__(self, planilla_repo=None) -> None:
        self.planilla_repo = planilla_repo
        self.base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    @staticmethod
    def generar_nombre_automatico(zona: int, ciclo: int, planilla_repo=None) -> str:
        """
        Genera el nombre oficial de la planilla buscando primero en el mapeo histórico.
        """
        nombres_fijos = {
            1: {
                1: '1° Planilla, Casas 1-20; (2025)',
                2: '2° Planilla, Casas 1-20; (2025)',
                3: '3° Planilla, Casas 1-20; (2025)',
                4: '1° Planilla, Casas 1-20; (2026)',
                5: '2° Planilla, Casas 1-20; (2026)'
            },
            2: {
                1: '2° Planilla, Casas 21-40; (2024)',
                2: '3° Planilla, Casas 21-40; (2024)',
                3: '4° Planilla, Casas 21-40; (2024)',
                4: '1° Planilla, Casas 21-40; (2025)',
                5: '2° Planilla, Casas 21-40; (2025)',
                6: '3° Planilla, Casas 21-40; (2025)',
                7: '1° Planilla, Casas 21-40; (2026)',
                8: '2° Planilla, Casas 21-40; (2026)'
            },
            3: {
                1: '1° Planilla, Casas 41-60; (2024)',
                2: '2° Planilla, Casas 41-60; (2024)',
                3: '1° Planilla, Casas 41-60; (2025)',
                4: '2° Planilla, Casas 41-60; (2025)',
                5: '1° Planilla, Casas 41-60; (2026)',
                6: '2° Planilla, Casas 41-60; (2026)'
            }
        }

        # 1. Revisar diccionario histórico
        nombre_mapeado = nombres_fijos.get(zona, {}).get(ciclo)
        if nombre_mapeado:
            return nombre_mapeado

        # 2. Lógica dinámica para ciclos nuevos
        anio_servicio = obtener_anio_servicio()
        proximo_numero = 1

        if planilla_repo:
            try:
                ultima_planilla_db = planilla_repo.obtener_ultima_planilla_creada(zona)
                if ultima_planilla_db and ultima_planilla_db.nombre_planilla:
                    from utils.recorrer_filas import extraer_info_planilla
                    num_anterior, anio_anterior = extraer_info_planilla(ultima_planilla_db.nombre_planilla)
                    
                    if num_anterior is not None and anio_anterior is not None:
                        if anio_anterior == anio_servicio:
                            proximo_numero = num_anterior + 1
                        else:
                            proximo_numero = 1
            except Exception:
                proximo_numero = 1

        rangos = {1: "1-20", 2: "21-40", 3: "41-60"}
        rango_txt = rangos.get(zona, f"Zona {zona}")

        return f"{proximo_numero}° Planilla, Casas {rango_txt}; ({anio_servicio})"
    
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
            client = get_sheets()
            
            nombre_planilla = datos_registro["nombre_planilla"]
            numero_territorio = datos_registro["numero_territorio"]
            fila_logica = datos_registro["fila"]  # 1 a 5 (salida_idx + 1)
            salida_idx = fila_logica - 1

            # 1. Resolver Zona mediante el nombre
            zona = self.detectar_zona_por_nombre(nombre_planilla, numero_territorio)
            inicio_territorio = 1 if zona == 1 else (21 if zona == 2 else 41)
            
            # Calcular en qué índice de nuestra lista VALORES_FILAS cae este territorio
            # Ej: Territorio 1 en Zona 1 -> índice 0 -> Fila base 15
            # Ej: Territorio 26 en Zona 2 -> índice 5 -> Fila base 40
            if numero_territorio < inicio_territorio or numero_territorio >= inicio_territorio + len(VALORES_FILAS):
                print(f"[SHEETS OMITIDO] El territorio {numero_territorio} está fuera del rango lógico de la zona {zona}")
                return

            territorio_idx = numero_territorio - inicio_territorio
            fila_base = VALORES_FILAS[territorio_idx]

            #2. Editar o inserar en hoja
            #RECORDA... TENES QUE AJUSTAR EL FECHA DE ASINGADO DEL FRON A DOMINGO, ESTA EN LUNES
            try:
                spreadsheet = client.open(nombre_planilla)
            except gspread.exceptions.SpreadsheetNotFound:
                print(f"⚠️ [SHEETS ADVERTENCIA] No se encontró la planilla '{nombre_planilla}'. Intentando crearla...")
                try:
                    # Crea una planilla nueva en la raíz de tu Drive con ese nombre exacto
                    spreadsheet = client.create(nombre_planilla)
                    
                    # 💡 NOTA: Las planillas nuevas vienen vacías. 
                    # Si querés que hereden el diseño de tus planillas anteriores, 
                    # podrías buscar una planilla modelo/base y clonarla en su lugar:
                    # plantilla_base = client.open("Casas 1-20; (2026)") # Tu modelo base
                    # spreadsheet = client.copy(plantilla_base.id, title=nombre_planilla)
                    
                    print(f"✨ [SHEETS CREADO] Se generó automáticamente el archivo físico en Drive: '{nombre_planilla}'")
                except Exception as create_err:
                    print(f"❌ [SHEETS ERROR] No se pudo crear la planilla en Drive: {str(create_err)}")
                    return
            
            sheet = spreadsheet.sheet1

            # 3. Localizar coordenadas físicas exactas del script original
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