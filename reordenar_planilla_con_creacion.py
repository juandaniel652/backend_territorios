import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy.orm import Session
from core.database import SessionLocal
from domain.territorio.model import Territorio
from domain.asignacion.model import Asignacion
from domain.planilla.model import NombrePlanilla
from domain.conductor.model import Conductor
from domain.planilla.repository import PlanillaRepository
from domain.planilla.service import PlanillaService
from core.google_sheets import get_sheets

def reordenar_y_crear_planillas_faltantes():
    db: Session = SessionLocal()
    try:
        print("="*60)
        print("🔄 INICIANDO REORDENAMIENTO Y AUTOCREACIÓN DE PLANILLAS EN SHEETS")
        print("="*60)

        planilla_repo = PlanillaRepository(db)
        planilla_service = PlanillaService(planilla_repo=planilla_repo)
        client = get_sheets()  # Cliente gspread autenticado

        territorios = db.query(Territorio).all()
        total_actualizadas_db = 0
        total_sincronizadas_sheets = 0
        total_creadas_nuevas = 0

        for territorio in territorios:
            asignaciones = (
                db.query(Asignacion)
                .filter(Asignacion.territorio_id == territorio.id)
                .order_by(Asignacion.fecha_asignado.asc(), Asignacion.id.asc())
                .all()
            )

            if not asignaciones:
                continue

            print(f"\n🏠 Procesando Territorio {territorio.numero} (Zona {territorio.zona}) - Total: {len(asignaciones)} asignaciones")

            for idx, asignacion in enumerate(asignaciones):
                ciclo_calculado = (idx // 5) + 1
                fila_calculada = (idx % 5) + 1
                zona = territorio.zona

                # Código dinámico (ej: Zona 3, Ciclo 120 -> 3120)
                codigo_planilla = int(f"{zona}{ciclo_calculado}")

                # 1. Buscar planilla en BD
                planilla = (
                    db.query(NombrePlanilla)
                    .filter(NombrePlanilla.codigo == codigo_planilla)
                    .first()
                )

                # 2. SI NO EXISTE: Crear la planilla automáticamente en Google Drive
                if not planilla:
                    nombre_temporal_codigo = str(codigo_planilla) # Ej: "3120"
                    print(f"   ✨ [AUTOCREACIÓN] No existe planilla en BD para el código {codigo_planilla}. Creando en Drive...")
                    
                    try:
                        # Crear el archivo en Google Sheets con el nombre del código
                        nuevo_spreadsheet = client.create(nombre_temporal_codigo)
                        spreadsheet_id = nuevo_spreadsheet.id
                        
                        # (Opcional) Si quieres moverla a una carpeta específica de Google Drive:
                        # folder_id = "TU_ID_DE_CARPETA_EN_DRIVE"
                        # file = client.client.files().get(fileId=spreadsheet_id, fields='parents').execute()
                        # client.client.files().update(fileId=spreadsheet_id, addParents=folder_id, removeParents=",".join(file.get('parents'))).execute()

                        # Generar un nombre descriptivo inicial para la BD
                        nombre_descriptivo = f"{ciclo_calculado}° Planilla, Zona {zona} (Auto)"

                        # Guardar la nueva planilla en la base de datos
                        planilla = NombrePlanilla(
                            codigo=codigo_planilla,
                            nombre_planilla=nombre_descriptivo,
                            spreadsheet_id=spreadsheet_id,
                            zona=zona,
                            ciclo=ciclo_calculado,
                            anio=2026 # O el año correspondiente
                        )
                        db.add(planilla)
                        db.commit()
                        db.refresh(planilla)
                        
                        total_creadas_nuevas += 1
                        print(f"   -> [SHEETS CREADO] ID: {spreadsheet_id} con nombre '{nombre_temporal_codigo}' guardado en BD.")
                    
                    except Exception as err:
                        print(f"   -> ❌ [ERROR CREACIÓN] No se pudo crear la planilla {codigo_planilla}: {err}")
                        continue

                # Actualizar asignación en Base de Datos
                asignacion.planilla_ciclo = ciclo_calculado
                asignacion.fila = fila_calculada
                asignacion.planilla_id = planilla.id
                total_actualizadas_db += 1

                # 3. Preparar payload y ejecutar el Bisturí en Google Sheets
                conductor_nombre = asignacion.conductor.nombre_completo if asignacion.conductor else "Sin Asignar"

                sheets_payload = {
                    "numero_territorio": territorio.numero,
                    "conductor": conductor_nombre,
                    "fecha_asignado": asignacion.fecha_asignado,
                    "fecha_completado": asignacion.fecha_completado,
                    "cantidad_abarcado": asignacion.cantidad_abarcado,
                    "fila": fila_calculada,
                    "zona": zona,
                    "spreadsheet_id": planilla.spreadsheet_id
                }

                try:
                    planilla_service.sincronizar_registro_bisturi(sheets_payload)
                    total_sincronizadas_sheets += 1
                except Exception as ex:
                    print(f"   -> ❌ [ERROR BISTURÍ] Asignación ID {asignacion.id}: {ex}")

        db.commit()
        print("="*60)
        print(f"✅ ¡PROCESO MASIVO Y AUTOCREACIÓN FINALIZADOS!")
        print(f"   - Planillas nuevas creadas en Drive y BD: {total_creadas_nuevas}")
        print(f"   - Asignaciones actualizadas en DB: {total_actualizadas_db}")
        print(f"   - Registros sincronizados por Bisturí: {total_sincronizadas_sheets}")
        print("="*60)

    except Exception as e:
        db.rollback()
        print(f"❌ [ERROR GENERAL]: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    reordenar_y_crear_planillas_faltantes()