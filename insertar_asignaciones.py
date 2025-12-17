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
# 3) Obtener ID del territorio por número
# ------------------------------------------
def obtener_territorio_id_por_numero(numero):
    conn = conectar_db()
    if not conn:
        return None

    cursor = conn.cursor()
    cursor.execute("""
        SELECT id 
        FROM territorios 
        WHERE numero = %s
    """, (numero,))

    fila = cursor.fetchone()
    conn.close()

    if fila:
        return fila[0]
    else:
        print(f"\n❗ No existe el territorio '{numero}' en la tabla territorios.")
        return None

# ------------------------------------------
# 4) Insertar nueva asignación
# ------------------------------------------
def insertar_asignacion(conductor_id, territorio_id, fecha_asignado, fecha_completado, cantidad_abarcado):
    conn = conectar_db()
    if not conn:
        return

    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO asignaciones (conductor_id, territorio_id, fecha_asignado, fecha_completado, cantidad_abarcado)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id
    """, (conductor_id, territorio_id, fecha_asignado, fecha_completado, cantidad_abarcado))

    id_nuevo = cursor.fetchone()[0]
    conn.commit()
    conn.close()

    print(f"\n✔ ¡Asignación ingresada con éxito! ID: {id_nuevo}")

# ------------------------------------------
# 5) Menú principal
# ------------------------------------------
def menu():
    print("\n========== INGRESO DE NUEVAS ASIGNACIONES ==========\n")

    numero_territorio = input("Ingrese el número del territorio: ")
    territorio_id = obtener_territorio_id_por_numero(numero_territorio)
    if not territorio_id:
        return

    nombre_conductor = input("Ingrese el nombre completo del conductor: ")
    conductor_id = obtener_conductor_id_por_nombre(nombre_conductor)
    if not conductor_id:
        return

    fecha_asignado = input("Ingrese fecha asignado (YYYY-MM-DD): ")
    fecha_completado = input("Ingrese fecha completado (YYYY-MM-DD): ")
    cantidad_abarcado = input("Ingrese cantidad abarcado (ej. 'Completo', 'a,b'): ")

    insertar_asignacion(conductor_id, territorio_id, fecha_asignado, fecha_completado, cantidad_abarcado)

# ------------------------------------------
# EJECUCIÓN
# ------------------------------------------
if __name__ == "__main__":
    menu()
