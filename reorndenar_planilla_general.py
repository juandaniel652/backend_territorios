import sys
import os

# Asegurar que el script encuentre la ruta de la app FastAPI
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy.orm import Session
from core.database import SessionLocal

# Importar modelos y servicios reales del proyecto
from domain.territorio.model import Territorio
from domain.asignacion.model import Asignacion
from domain.planilla.model import NombrePlanilla
from domain.conductor.model import Conductor
from domain.planilla.repository import PlanillaRepository
from domain.planilla.service import PlanillaService

def reordenar_y_sincronizar_todo():
    db: Session = SessionLocal()
    try:
        print("="*60)
        print("🔄 INICIANDO REORDENAMIENTO Y BISTURÍ MASIVO EN GOOGLE SHEETS")
        print("="*60)

        # Inicializamos el repositorio de planillas y el PlanillaService real
        planilla_repo = PlanillaRepository(db)
        planilla_service = PlanillaService(planilla_repo=planilla_repo)

        territorios = db.query(Territorio).all()
        total_actualizadas_db = 0
        total_sincronizadas_sheets = 0

        for territorio in territorios:
            # 1. Obtener todas las asignaciones del territorio ordenadas cronológicamente
            asignaciones = (
                db.query(Asignacion)
                .filter(Asignacion.territorio_id == territorio.id)
                .order_by(Asignacion.fecha_asignado.asc(), Asignacion.id.asc())
                .all()
            )

            if not asignaciones:
                continue

            print(f"\n🏠 Procesando Territorio {territorio.numero} (Zona {territorio.zona}) - Total: {len(asignaciones)} asignaciones")

            # 2. Recorrer y recalcular ciclo, fila y planilla exacta de 5 en 5
            for idx, asignacion in enumerate(asignaciones):
                ciclo_calculado = (idx // 5) + 1
                fila_calculada = (idx % 5) + 1
                zona = territorio.zona

                codigo_planilla = int(f"{zona}{ciclo_calculado}")

                planilla = (
                    db.query(NombrePlanilla)
                    .filter(NombrePlanilla.codigo == codigo_planilla)
                    .first()
                )

                if not planilla:
                    print(f"⚠️ [ALERTA] No se encontró planilla en BD para el código {codigo_planilla} (Zona {zona}, Ciclo {ciclo_calculado}). Omitiendo sincronización.")
                    continue

                # Actualizar en Base de Datos
                asignacion.planilla_ciclo = ciclo_calculado
                asignacion.fila = fila_calculada
                asignacion.planilla_id = planilla.id
                total_actualizadas_db += 1

                # 3. Preparar payload para el Bisturí de Google Sheets usando 'nombre_completo'
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

                # Ejecutar Bisturí individual por cada celda calculada
                try:
                    planilla_service.sincronizar_registro_bisturi(sheets_payload)
                    total_sincronizadas_sheets += 1
                    print(f"   -> [SHEETS OK] Asignación ID {asignacion.id} -> Ciclo {ciclo_calculado}, Fila {fila_calculada} sincronizada.")
                except Exception as ex:
                    print(f"   -> ❌ [ERROR SHEETS] Falló al sincronizar Asignación ID {asignacion.id}: {ex}")

        db.commit()
        print("="*60)
        print(f"✅ ¡PROCESO COMPLETADO EXITOSAMENTE!")
        print(f"   - Asignaciones actualizadas en Base de Datos: {total_actualizadas_db}")
        print(f"   - Registros inyectados por Bisturí en Google Sheets: {total_sincronizadas_sheets}")
        print("="*60)

    except Exception as e:
        db.rollback()
        print(f"❌ [ERROR GENERAL] Falló el proceso masivo: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    reordenar_y_sincronizar_todo()