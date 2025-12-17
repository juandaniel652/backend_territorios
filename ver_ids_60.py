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
    )

# -----------------------------
# OBTENER ASIGNACIONES DEL 60
# -----------------------------
def obtener_asignaciones_territorio_60():
    conn = conectar_db()
    cur = conn.cursor(cursor_factory=DictCursor)

    cur.execute("""
        SELECT
            a.id AS asignacion_id,
            c.nombre_completo AS conductor,
            a.fecha_asignado,
            a.fecha_completado,
            a.cantidad_abarcado
        FROM asignaciones a
        JOIN territorios t ON t.id = a.territorio_id
        JOIN conductores c ON c.id = a.conductor_id
        WHERE t.numero = 60
        ORDER BY a.id ASC
    """)

    filas = cur.fetchall()
    conn.close()
    return filas

# -----------------------------
# MOSTRAR DATOS
# -----------------------------
def menu():
    filas = obtener_asignaciones_territorio_60()

    if not filas:
        print("No hay asignaciones en el territorio 60.")
        return

    print("\n=== ASIGNACIONES – TERRITORIO 60 (ORDENADAS POR ID) ===\n")

    for i, f in enumerate(filas, start=1):
        print(f"{i:02d}) ID: {f['asignacion_id']}")
        print(f"    Conductor: {f['conductor']}")
        print(f"    Fecha asignado: {f['fecha_asignado']}")
        print(f"    Fecha completado: {f['fecha_completado']}")
        print(f"    Total abarcado: {f['cantidad_abarcado']}")
        print("-" * 50)

# -----------------------------
# EJECUCIÓN
# -----------------------------
if __name__ == "__main__":
    menu()
