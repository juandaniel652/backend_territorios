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

def reordenar_territorio_especifico(numero_territorio_objetivo: int):
    db: Session = SessionLocal()
    try:
        print("="*60)
        print(f"🔄 REORDENAMIENTO Y SINCRONIZACIÓN: TERRITORIO #{numero_territorio_objetivo}")
        print("="*60)

        planilla_repo = PlanillaRepository(db)
        planilla_service = PlanillaService(planilla_repo=planilla_repo)
        client = get_sheets()  # Cliente gspread autenticado

        # 1. Buscar el territorio específico
        territorio = db.query(Territorio).filter(Territorio.numero == numero_territorio_objetivo).first()
        if not territorio:
            print(f"❌ [ERROR] No se encontró el territorio número {numero_territorio_objetivo} en la Base de Datos.")
            return

        # 2. Obtener todas sus asignaciones ordenadas cronológicamente
        asignaciones = (
            db.query(Asignacion)
            .filter(Asignacion.territorio_id == territorio.id)
            .order_by(Asignacion.fecha_asignado.asc(), Asignacion.id.asc())
            .all()
        )

        if not asignaciones:
            print(f"⚠️ El territorio #{territorio.numero} no tiene asignaciones registradas.")
            return

        print(f"\n🏠 Territorio {territorio.numero} (Zona {territorio.zona}) - Total asignaciones: {len(asignaciones)}")

        total_actualizadas_db = 0
        total_sincronizadas_sheets = 0
        total_creadas_nuevas = 0

        # 3. Recorrer de 5 en 5 (lógica de ciclos)
        for idx, asignacion in enumerate(asignaciones):
            ciclo_calculado = (idx // 5) + 1
            fila_calculada = (idx % 5) + 1
            zona = territorio.zona

            # Código dinámico (ej: Zona 3, Ciclo 120 -> 3120)
            codigo_planilla = int(f"{zona}{ciclo_calculado}")

            # Buscar planilla en BD
            planilla = (
                db.query(NombrePlanilla)
                .filter(NombrePlanilla.codigo == codigo_planilla)
                .first()
            )

            # Si no existe, crearla automáticamente en Drive
            if not planilla:
                nombre_temporal_codigo = str(codigo_planilla)
                print(f"   ✨ [AUTOCREACIÓN] No existe planilla para el código {codigo_planilla}. Creando en Drive...")
                
                try:
                    nuevo_spreadsheet = client.create(nombre_temporal_codigo)
                    spreadsheet_id = nuevo_spreadsheet.id
                    
                    nombre_descriptivo = f"{ciclo_calculado}° Planilla, Zona {zona} (Auto)"

                    planilla = NombrePlanilla(
                        codigo=codigo_planilla,
                        nombre_planilla=nombre_descriptivo,
                        spreadsheet_id=spreadsheet_id,
                        zona=zona,
                        ciclo=ciclo_calculado,
                        anio=2026
                    )
                    db.add(planilla)
                    db.commit()
                    db.refresh(planilla)
                    
                    total_creadas_nuevas += 1
                    print(f"   -> [SHEETS CREADO] ID: {spreadsheet_id} con nombre '{nombre_temporal_codigo}' guardado en BD.")
                
                except Exception as err:
                    print(f"   -> ❌ [ERROR CREACIÓN] Falló al crear la planilla {codigo_planilla}: {err}")
                    continue

            # Actualizar asignación en Base de Datos
            asignacion.planilla_ciclo = ciclo_calculado
            asignacion.fila = fila_calculada
            asignacion.planilla_id = planilla.id
            total_actualizadas_db += 1

            # Preparar payload y ejecutar el Bisturí en Google Sheets
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
                print(f"   -> [BISTURÍ OK] Asignación ID {asignacion.id} -> Ciclo {ciclo_calculado}, Fila {fila_calculada} sincronizada.")
            except Exception as ex:
                print(f"   -> ❌ [ERROR BISTURÍ] Asignación ID {asignacion.id}: {ex}")

        db.commit()
        print("="*60)
        print(f"✅ ¡PROCESO PARA EL TERRITORIO #{numero_territorio_objetivo} FINALIZADO!")
        print(f"   - Planillas nuevas creadas: {total_creadas_nuevas}")
        print(f"   - Asignaciones reordenadas en DB: {total_actualizadas_db}")
        print(f"   - Celdas sincronizadas por Bisturí: {total_sincronizadas_sheets}")
        print("="*60)

    except Exception as e:
        db.rollback()
        print(f"❌ [ERROR GENERAL]: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    # Puedes cambiar el número del territorio que deseas reordenar aquí abajo
    #TERRITORIO_A_REORDENAR = 12 
    reordenar_territorio_especifico(TERRITORIO_A_REORDENAR)