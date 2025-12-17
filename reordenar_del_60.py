import psycopg2
from psycopg2.extras import DictCursor

# -----------------------------
# CONEXIÓN
# -----------------------------
def conectar_db():
    return psycopg2.connect(
        host="aws-0-us-west-2.pooler.supabase.com",
        database="postgres",
        user="postgres.qbpporkcnzredtedqwyx",
        password="hEqETD0V851JnBcB",
        port=6543,
        sslmode="require"
    )

# -----------------------------
# BUSCAR ASIGNACIÓN POR DATOS
# -----------------------------
def buscar_asignacion(conductor, fecha_asig, fecha_comp, abarcado):
    conn = conectar_db()
    cur = conn.cursor(cursor_factory=DictCursor)

    cur.execute("""
        SELECT
            a.id AS asignacion_id,
            c.nombre_completo,
            a.fecha_asignado,
            a.fecha_completado,
            a.cantidad_abarcado
        FROM asignaciones a
        JOIN conductores c ON c.id = a.conductor_id
        JOIN territorios t ON t.id = a.territorio_id
        WHERE t.numero = 60
          AND c.nombre_completo = %s
          AND a.fecha_asignado = %s
          AND a.fecha_completado = %s
          AND a.cantidad_abarcado = %s
    """, (conductor, fecha_asig, fecha_comp, abarcado))

    filas = cur.fetchall()
    conn.close()
    return filas

# -----------------------------
# MENÚ INTERACTIVO
# -----------------------------
def menu():
    print("\n=== IDENTIFICADOR DE ASIGNACIONES (Territorio 60) ===\n")

    while True:
        conductor = input("Nombre del conductor (ENTER para salir): ").strip()
        if not conductor:
            break

        fecha_asig = input("Fecha asignado (YYYY-MM-DD): ").strip()
        fecha_comp = input("Fecha completado (YYYY-MM-DD): ").strip()
        abarcado = input("Total abarcado: ").strip()

        resultados = buscar_asignacion(
            conductor, fecha_asig, fecha_comp, abarcado
        )

        if not resultados:
            print("\n❌ No se encontró ninguna asignación con esos datos.\n")
            continue

        print("\n✔ Coincidencias encontradas:\n")
        for r in resultados:
            print(f"ID: {r['asignacion_id']}")
            print(f"  Conductor: {r['nombre_completo']}")
            print(f"  Fecha asignado: {r['fecha_asignado']}")
            print(f"  Fecha completado: {r['fecha_completado']}")
            print(f"  Total abarcado: {r['cantidad_abarcado']}")
            print("-" * 40)

# -----------------------------
# EJECUCIÓN
# -----------------------------
if __name__ == "__main__":
    menu()
