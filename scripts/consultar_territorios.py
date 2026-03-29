"""
scripts/consultar_territorios.py

CLI para consultar el historial de asignaciones de un territorio.
Migrado desde querys_territorios.py original.

Cambios respecto al original:
  - Usa TerritorioService en lugar de SQL inline
  - El ordenamiento cronológico lo hace la DB (no Python)
  - Reutiliza los schemas del dominio para el output
  - Salida con formato más claro y colores ANSI opcionales

Ejecutar desde la raíz del proyecto:
    python -m scripts.consultar_territorios
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.database import SessionLocal
from domain.territorio.repository import TerritorioRepository
from domain.territorio.service import TerritorioService


# ─────────────────────────────────────────────
# Presentación
# ─────────────────────────────────────────────

def imprimir_historial(numero: int) -> None:
    """Consulta y muestra el historial de un territorio en consola."""
    db = SessionLocal()
    try:
        repo    = TerritorioRepository(db)
        service = TerritorioService(repo)
        result  = service.obtener_historial(numero)
    finally:
        db.close()

    print(f"\n{'─' * 60}")
    print(f"  📌 Territorio {result.territorio}")
    print(f"{'─' * 60}")

    if result.mensaje:
        print(f"  ⚠️  {result.mensaje}")
        return

    for i, a in enumerate(result.asignaciones, start=1):
        print(f"\n  [{i}] Conductor  : {a.conductor}")
        print(f"      Asignado   : {a.fecha_asignado or '—'}")
        print(f"      Completado : {a.fecha_completado or '—'}")
        print(f"      Abarcado   : {a.cantidad_abarcado or '—'}")

    print(f"\n{'─' * 60}")
    print(f"  Total: {len(result.asignaciones)} asignación/es\n")


# ─────────────────────────────────────────────
# Loop principal
# ─────────────────────────────────────────────

def main():
    print("\n╔══════════════════════════════════════════════════╗")
    print("║     CONSULTAR TERRITORIOS — CLI                  ║")
    print("╚══════════════════════════════════════════════════╝")
    print("  Ingresá -1 para salir.\n")

    while True:
        raw = input("Número de territorio: ").strip()

        if raw == "-1":
            print("Saliendo.")
            break

        if not raw.isdigit():
            print("❌ Ingresá un número válido o -1 para salir.")
            continue

        try:
            imprimir_historial(int(raw))
        except Exception as e:
            print(f"❌ Error al consultar: {e}")


if __name__ == "__main__":
    main()