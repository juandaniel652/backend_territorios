"""
scripts/insertar_asignaciones.py

CLI para insertar asignaciones directamente desde terminal.
Útil para carga masiva o correcciones puntuales sin pasar por la API.

Migración desde el original:
  - Eliminada la conexión psycopg2 con credenciales hardcodeadas
  - Usa SQLAlchemy + settings desde .env (misma config que la API)
  - Reutiliza los repositorios del dominio → cero duplicación de lógica
  - La sesión se maneja igual que en la API (SessionLocal + commit/rollback)

Ejecutar desde la raíz del proyecto:
    python -m scripts.insertar_asignaciones
"""

import sys
from pathlib import Path

# Permite importar los módulos del backend cuando se ejecuta como script
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from datetime import date
from core.database import SessionLocal
from domain.territorio.repository import TerritorioRepository
from domain.conductor.repository import ConductorRepository
from domain.asignacion.repository import AsignacionRepository


# ─────────────────────────────────────────────
# Helpers de input
# ─────────────────────────────────────────────

def pedir_fecha(mensaje: str, obligatorio: bool = True) -> date | None:
    while True:
        raw = input(f"{mensaje} (YYYY-MM-DD){'' if obligatorio else ' [Enter para omitir]'}: ").strip()
        if not raw and not obligatorio:
            return None
        try:
            return date.fromisoformat(raw)
        except ValueError:
            print("❌ Formato inválido. Usá YYYY-MM-DD (ej: 2024-03-15)")


def pedir_entero(mensaje: str) -> int:
    while True:
        raw = input(f"{mensaje}: ").strip()
        if raw.lstrip("-").isdigit():
            return int(raw)
        print("❌ Ingresá un número entero válido.")


# ─────────────────────────────────────────────
# Flujo principal
# ─────────────────────────────────────────────

def insertar_una_asignacion(db) -> bool:
    """
    Guía al usuario para ingresar una asignación.
    Retorna True si se insertó correctamente, False si el usuario canceló.

    Reutiliza los repositorios del dominio exactamente igual que AsignacionService,
    pero con interacción por consola en lugar de HTTP.
    """
    print("\n" + "=" * 52)
    print("   INGRESO DE ASIGNACIÓN")
    print("=" * 52)

    territorio_repo = TerritorioRepository(db)
    conductor_repo  = ConductorRepository(db)
    asignacion_repo = AsignacionRepository(db)

    # ── Territorio ───────────────────────────
    numero = pedir_entero("Número del territorio")
    territorio = territorio_repo.obtener_por_numero(numero)
    if not territorio:
        print(f"❌ No existe el territorio {numero} en la base de datos.")
        return False

    # ── Conductor ────────────────────────────
    nombre = input("Nombre completo del conductor: ").strip()
    if not nombre:
        print("❌ El nombre no puede estar vacío.")
        return False

    conductor, creado = conductor_repo.obtener_o_crear(nombre)
    if creado:
        print(f"   ℹ️  Conductor '{nombre}' no existía — será creado.")

    # ── Fechas ───────────────────────────────
    fecha_asignado   = pedir_fecha("Fecha asignado")
    fecha_completado = pedir_fecha("Fecha completado", obligatorio=False)

    if fecha_completado and fecha_completado < fecha_asignado:
        print("❌ La fecha completado no puede ser anterior a la fecha asignado.")
        return False

    # ── Cantidad abarcado ────────────────────
    cantidad = input("Cantidad abarcado (ej: 'Completo', 'a,b,c'): ").strip()

    # ── Confirmación ─────────────────────────
    print("\n── Resumen ──────────────────────────────────")
    print(f"   Territorio : {territorio.numero}")
    print(f"   Conductor  : {conductor.nombre_completo}{' (nuevo)' if creado else ''}")
    print(f"   Asignado   : {fecha_asignado}")
    print(f"   Completado : {fecha_completado or '—'}")
    print(f"   Abarcado   : {cantidad}")
    print("─────────────────────────────────────────────")

    confirmar = input("¿Confirmar inserción? [s/N]: ").strip().lower()
    if confirmar != "s":
        print("⚠️  Inserción cancelada.")
        db.rollback()
        return False

    asignacion_repo.crear(
        territorio_id=territorio.id,
        conductor_id=conductor.id,
        fecha_asignado=fecha_asignado,
        fecha_completado=fecha_completado,
        cantidad_abarcado=cantidad,
    )
    db.commit()
    print(f"✔  Asignación registrada con ID: {asignacion_repo.db.identity_key(type(asignacion_repo.crear.__self__))}")
    return True


def main():
    print("\n╔══════════════════════════════════════════════════╗")
    print("║     INSERTAR ASIGNACIONES — CLI                  ║")
    print("╚══════════════════════════════════════════════════╝")

    cantidad = pedir_entero("\n¿Cuántas asignaciones querés ingresar?")
    if cantidad <= 0:
        print("Nada que hacer. Saliendo.")
        return

    exitosas = 0
    for i in range(cantidad):
        print(f"\n[{i + 1}/{cantidad}]")
        db = SessionLocal()
        try:
            ok = insertar_una_asignacion(db)
            if ok:
                exitosas += 1
        except Exception as e:
            db.rollback()
            print(f"❌ Error inesperado: {e}")
        finally:
            db.close()

    print(f"\n✅ Proceso terminado: {exitosas}/{cantidad} asignaciones insertadas.")


if __name__ == "__main__":
    main()