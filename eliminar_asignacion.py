import psycopg2
from psycopg2 import sql, OperationalError

# ------------------------------------------
# 1) Conexión a la BD
# ------------------------------------------
def conectar_db():
    try:
        conn = psycopg2.connect(
            host="aws-0-us-west-2.pooler.supabase.com",
            database="postgres",
            user="postgres.qbpporkcnzredtedqwyx",
            password="hEqETD0V851JnBcB",
            port=6543,
            sslmode="require"
        )
        return conn
    except OperationalError as e:
        print("Error al conectar a la BD:", e)
        return None

# ------------------------------------------
# 2) Listar asignaciones por territorio
# ------------------------------------------
def listar_asignaciones_por_territorio(numero_territorio):
    conn = conectar_db()
    if not conn:
        return []

    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            a.id,
            c.nombre_completo,
            t.numero,
            a.fecha_asignado,
            a.fecha_completado,
            a.cantidad_abarcado
        FROM asignaciones a
        JOIN territorios t ON a.territorio_id = t.id
        JOIN conductores c ON a.conductor_id = c.id
        WHERE t.numero = %s
        ORDER BY a.fecha_asignado DESC
    """, (numero_territorio,))

    filas = cursor.fetchall()
    conn.close()

    if not filas:
        print("\n❗ No hay asignaciones para ese territorio.")
        return []

    print("\n=== ASIGNACIONES DEL TERRITORIO", numero_territorio, "===")
    for f in filas:
        print(f"\nID: {f[0]}")
        print(f"  Conductor: {f[1]}")
        print(f"  Territorio: {f[2]}")
        print(f"  Fecha asignado: {f[3]}")
        print(f"  Fecha completado: {f[4]}")
        print(f"  Abarcado: {f[5]}")
        print("-" * 40)

    return filas

# ------------------------------------------
# 3) Eliminar asignación por ID
# ------------------------------------------
def eliminar_asignacion(id_asignacion):
    conn = conectar_db()
    if not conn:
        return

    cursor = conn.cursor()
    query = sql.SQL("DELETE FROM asignaciones WHERE id = %s")
    cursor.execute(query, (id_asignacion,))
    conn.commit()
    conn.close()

    print(f"\n✔ ¡Asignación con ID {id_asignacion} eliminada!")

# ------------------------------------------
# 4) Menú principal
# ------------------------------------------
def menu():
    print("\n========== ELIMINADOR DE ASIGNACIONES ==========\n")

    territorio = input("Ingrese el número del territorio: ")

    filas = listar_asignaciones_por_territorio(territorio)
    if not filas:
        return

    ids_eliminar = input("\nIngrese los ID que desea eliminar (separados por coma): ")
    ids_eliminar = [id.strip() for id in ids_eliminar.split(",")]

    for id_asignacion in ids_eliminar:
        eliminar_asignacion(id_asignacion)

# ------------------------------------------
# EJECUCIÓN
# ------------------------------------------
if __name__ == "__main__":
    menu()
