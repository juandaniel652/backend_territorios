from sqlalchemy import text
from database import engine
from datetime import datetime

def mostrar_asignaciones_territorio(numero_territorio: int):
    sql = """
    SELECT 
        c.nombre_completo AS conductor,
        a.fecha_asignado,
        a.fecha_completado,
        a.cantidad_abarcado
    FROM Asignaciones a
    JOIN Territorios t ON a.territorio_id = t.id
    JOIN Conductores c ON a.conductor_id = c.id
    WHERE t.numero = :numero;
    """

    try:
        with engine.connect() as conn:
            result = conn.execute(text(sql), {"numero": numero_territorio})
            filas = [dict(row._mapping) for row in result.fetchall()]  # <- cambio aquí

        if not filas:
            print(f"⚠️ No hay asignaciones para territorio {numero_territorio}")
            return

        filas.sort(
            key=lambda f: datetime.strptime(str(f["fecha_asignado"]), "%Y-%m-%d") if f["fecha_asignado"] else datetime.max
        )

        print(f"\n📌 Asignaciones — Territorio {numero_territorio} (orden cronológico)")
        print("-" * 65)
        for fila in filas:
            print(f"   Conductor: {fila['conductor']}")
            print(f"   Fecha Asignado:   {fila['fecha_asignado'] or '—'}")
            print(f"   Fecha Completado: {fila['fecha_completado'] or '—'}")
            print(f"   Territorios:     {fila['cantidad_abarcado'] or '—'}")
            print()
        print("-" * 65)

    except Exception as e:
        print(f"❌ Error al consultar PostgreSQL:", e)


if __name__ == "__main__":
    while True:
        print("POSTGRESQL - Consultar Asignaciones por Territorio (Hay cosas para corregir...)")
        num = input("Ingrese número del territorio a consultar (-1 para salir): ").strip()
        if num == "-1":
            print("Saliendo.")
            break
        if num.isdigit():
            mostrar_asignaciones_territorio(int(num))
        else:
            print("❌ Debe ingresar un número válido o -1 para salir.")
