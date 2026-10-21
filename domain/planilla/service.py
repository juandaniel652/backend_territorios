import os
import traceback
from datetime import datetime, date
from typing import Any, Optional
import gspread

from core.google_sheets import get_sheets
import utils.recorrer_filas as archivo

VALORES_FILAS = [15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80, 85, 90, 95, 100, 105, 110]


class PlanillaService:

    def __init__(self, planilla_repo=None, historial_repo=None) -> None:
        self.planilla_repo = planilla_repo
        self.historial_repo = historial_repo
        self.base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    # ============================================
    # Lógica de elección, validación y autocreación de planilla
    
    def validar_planilla_por_id(self, client: gspread.Client, spreadsheet_id: str) -> Optional[gspread.Spreadsheet]:
        """
        Abre el archivo de Google Sheets mediante su Spreadsheet ID inmutable.
        """
        try:
            return client.open_by_key(spreadsheet_id)
        except gspread.exceptions.SpreadsheetNotFound:
            print(f"❌ [SHEETS ERROR] No existe la planilla en Drive con ID: '{spreadsheet_id}'")
            return None
        except Exception as e:
            print(f"⚠️ [SHEETS ERROR] Error al abrir la planilla ID '{spreadsheet_id}': {e}")
            return None

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

    def asegurar_planilla_dinamica(self, db_session, zona: int, ciclo: int) -> Optional[str]:
        """
        Busca en la base de datos la planilla correspondiente a la zona y ciclo.
        Si no existe, la crea automáticamente en Google Drive usando solo el código
        como nombre provisional (ej: '3120') y registra la entidad en la BD.
        Retorna el spreadsheet_id listo para usar.
        """
        codigo_planilla = int(f"{zona}{ciclo}")
        
        if not self.planilla_repo:
            print("⚠️ [AUTOCREACIÓN] No hay un repositorio de planillas configurado en el servicio.")
            return None

        # 1. Buscar en BD si ya existe
        planilla_db = self.planilla_repo.obtener_por_codigo(db_session, codigo_planilla) if hasattr(self.planilla_repo, 'obtener_por_codigo') else None
        
        # Fallback directo con SQLAlchemy si el repo no tiene el método exacto
        if not planilla_db and hasattr(self.planilla_repo, 'db'):
            from domain.planilla.model import NombrePlanilla
            planilla_db = db_session.query(NombrePlanilla).filter(NombrePlanilla.codigo == codigo_planilla).first()

        if planilla_db and planilla_db.spreadsheet_id:
            return planilla_db.spreadsheet_id

        # 2. SI NO EXISTE: Autocrear en Google Drive al vuelo
        try:
            client = get_sheets()
            nombre_temporal = str(codigo_planilla)
            print(f"✨ [AUTOCREACIÓN BACKEND] La planilla con código {codigo_planilla} no existe. Creando en Google Drive...")
            
            nuevo_spreadsheet = client.create(nombre_temporal)
            spreadsheet_id = nuevo_spreadsheet.id
            
            # Nombre descriptivo por defecto
            nombre_descriptivo = f"{ciclo}° Planilla, Zona {zona} (Auto)"
            anio_actual = datetime.now().year

            # Guardar en la Base de Datos
            from domain.planilla.model import NombrePlanilla
            nueva_planilla = NombrePlanilla(
                codigo=codigo_planilla,
                nombre_planilla=nombre_descriptivo,
                spreadsheet_id=spreadsheet_id,
                zona=zona,
                ciclo=ciclo,
                anio=anio_actual
            )
            db_session.add(nueva_planilla)
            db_session.commit()
            db_session.refresh(nueva_planilla)
            
            print(f"✅ [AUTOCREACIÓN ÉXITO] Planilla '{nombre_temporal}' creada en Drive y guardada en BD.")
            return spreadsheet_id

        except Exception as e:
            print(f"❌ [ERROR AUTOCREACIÓN] No se pudo crear la planilla automática para código {codigo_planilla}: {e}")
            traceback.print_exc()
            return None

    def sincronizar_registro_bisturi(self, datos_registro: dict, db_session=None):
        """
        Inyecta una única asignación en tiempo real en las coordenadas físicas 
        exactas de Google Sheets calculadas por 'recorrer_fila_planilla'.
        Si la planilla no existe, la autocrea de forma transparente.
        """
        print("="*60)
        print(f"DEBUG BISTURÍ:")
        print(f" -> Spreadsheet ID inicial: {datos_registro.get('spreadsheet_id')}")
        print(f" -> Territorio: {datos_registro.get('numero_territorio')}")
        print(f" -> Fila lógica (1-5): {datos_registro.get('fila')}")
        print(f" -> Conductor: {datos_registro.get('conductor')}")
        print("="*60)
        
        try:
            spreadsheet_id = datos_registro.get("spreadsheet_id")
            zona = datos_registro.get("zona")
            ciclo = datos_registro.get("planilla_ciclo")

            # Si no viene el spreadsheet_id pero tenemos zona y ciclo, intentamos asegurarlo/autocrearlo
            if not spreadsheet_id and zona and ciclo and db_session:
                spreadsheet_id = self.asegurar_planilla_dinamica(db_session, zona, ciclo)

            if not spreadsheet_id:
                print("❌ [SHEETS OMITIDO] No se proporcionó un 'spreadsheet_id' válido ni se pudo autocrear.")
                return

            client = get_sheets()
            
            # 1. Validar y abrir la planilla directamente por su ID inmutable
            spreadsheet = self.validar_planilla_por_id(client, spreadsheet_id)
            if not spreadsheet:
                print(f"❌ [SHEETS CANCELADO] Omitiendo sincronización porque no se encontró la planilla con ID en Drive.")
                return

            numero_territorio = datos_registro["numero_territorio"]
            fila_logica = datos_registro["fila"]  # 1 a 5 (salida_idx + 1)

            # 🛡️ NORMALIZACIÓN / CONTROL DE RANGO (1 a 5)
            if fila_logica > 5:
                fila_logica = ((fila_logica - 1) % 5) + 1

            salida_idx = fila_logica - 1

            # 2. Resolver Zona de forma matemática/directa por número de territorio o parámetro
            if not zona:
                if 1 <= numero_territorio <= 20:
                    zona = 1
                elif 21 <= numero_territorio <= 40:
                    zona = 2
                elif 41 <= numero_territorio <= 60:
                    zona = 3
                else:
                    raise ValueError(f"No se pudo determinar la zona para el territorio {numero_territorio}")

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

            # 🛡️ CONTROL DE SEGURIDAD CONTRA INDEX ERROR
            if salida_idx >= len(celdas_cond):
                print(f"❌ [SHEETS OMITIDO] El índice de salida ({salida_idx}) excede las celdas físicamente mapeadas ({len(celdas_cond)}).")
                return

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
            
            print(f"[SHEETS SUCCESS] Sincronizado Territorio {numero_territorio} en Fila Física {fila_base} para la Planilla ID.")

        except Exception as e:
            print("[SHEETS ERROR] Falló la sincronización con Google Sheets:")
            traceback.print_exc()
    
    # ============================================
    # Llamada del repositorio 'obtener_todas', devuelve todas las planillas con sus atributos
    
    def listar_planillas(self):
        return self.planilla_repo.obtener_todas()
    
    def obtener_planillas_totales (self):

        return self.planilla_repo.obtener_total_de_planillas()
    
    def obtener_solo_planillas_completas (self): 

        return self.planilla_repo.obtener_total_de_planillas_completadas()
    
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