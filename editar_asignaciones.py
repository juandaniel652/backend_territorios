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
# 2) Obtener ID del conductor por nombre
# ------------------------------------------
def obtener_conductor_id_por_nombre(nombre):
    conn = conectar_db()
    if not conn:
        return None

    cursor = conn.cursor()
    cursor.execute("""
        SELECT id 
        FROM conductores 
        WHERE nombre_completo = %s
    """, (nombre,))

    fila = cursor.fetchone()
    conn.close()

    if fila:
        return fila[0]
    else:
        print(f"\n❗ No existe el conductor '{nombre}' en la tabla conductores.")
        return None


# ------------------------------------------
# 3) Listar asignaciones del territorio
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
# 4) Mostrar asignación seleccionada
# ------------------------------------------
def mostrar_asignacion(id_asignacion):
    conn = conectar_db()
    if not conn:
        return

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
        JOIN conductores c ON a.conductor_id = c.id
        JOIN territorios t ON a.territorio_id = t.id
        WHERE a.id = %s
    """, (id_asignacion,))

    fila = cursor.fetchone()
    conn.close()

    if fila:
        print("\n=== ASIGNACIÓN ELEGIDA ===")
        print(f"ID: {fila[0]}")
        print(f"Conductor: {fila[1]}")
        print(f"Territorio: {fila[2]}")
        print(f"Fecha asignado: {fila[3]}")
        print(f"Fecha completado: {fila[4]}")
        print(f"Abarcado: {fila[5]}")
    else:
        print("No existe ese ID.")


# ------------------------------------------
# 5) Actualización de campos
# ------------------------------------------
def actualizar_asignacion(id_asignacion, campo, nuevo_valor):
    conn = conectar_db()
    if not conn:
        return

    cursor = conn.cursor()
    query = sql.SQL("UPDATE asignaciones SET {} = %s WHERE id = %s").format(sql.Identifier(campo))
    cursor.execute(query, (nuevo_valor, id_asignacion))
    conn.commit()
    conn.close()

    print(f"\n✔ ¡Valor actualizado! ({campo} → {nuevo_valor})")


# ------------------------------------------
# 6) Menú principal
# ------------------------------------------
def menu():
    print("\n========== EDITOR DE ASIGNACIONES ==========\n")

    territorio = input("Ingrese el número del territorio: ")

    filas = listar_asignaciones_por_territorio(territorio)
    if not filas:
        return

    id_asignacion = input("\nIngrese el ID que desea modificar: ")

    mostrar_asignacion(id_asignacion)

    print("\n¿Qué desea modificar?")
    print("1) Fecha asignado")
    print("2) Fecha completado")
    print("3) Conductor (por nombre)")
    print("4) Cantidad abarcado")
    print("5) Salir")

    opcion = input("\nElija una opción: ")

    if opcion == "1":
        nuevo = input("Nueva fecha asignado (YYYY-MM-DD): ")
        actualizar_asignacion(id_asignacion, "fecha_asignado", nuevo)

    elif opcion == "2":
        nuevo = input("Nueva fecha completado (YYYY-MM-DD): ")
        actualizar_asignacion(id_asignacion, "fecha_completado", nuevo)

    elif opcion == "3":
        nombre = input("Nuevo nombre del conductor: ")
        conductor_id = obtener_conductor_id_por_nombre(nombre)

        if conductor_id:
            actualizar_asignacion(id_asignacion, "conductor_id", conductor_id)

    elif opcion == "4":
        nuevo = input("Nuevo valor (ej. 'Completo', 'a,b', 'N/A'): ")
        actualizar_asignacion(id_asignacion, "cantidad_abarcado", nuevo)

    else:
        print("Saliendo...")


# ------------------------------------------
# EJECUCIÓN
# ------------------------------------------
if __name__ == "__main__":
    while True:
        menu()
        seguir = input("\n¿Desea seguir con otro? (S/N): ").strip().upper()
        if seguir != "S":
            print("\nPrograma finalizado. ¡Hasta luego!")
            break


#TENGO QUE ARREGLAR LETRAS DEL 23 AL 40. LUEGO VER QUE PASA DEL TERRITOORIO 52 EN ADELANTE
#(AL PARECER YA NO EXISTEN. LUEGO PASARLO A UN ENTORNO WEB CON FRONT Y LISTO, QUE FUNCIONE)