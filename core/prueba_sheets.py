import os
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# ==========================================
# CONFIGURACIÓN CORREGIDA
# ==========================================
# Esto detecta automáticamente la carpeta 'core/' donde está este script y la llave
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
CREDENTIALS_PATH = os.path.join(CURRENT_DIR, "llave_nueva.json") 

SPREADSHEET_NAME = "salida_modelo"  # Cambia por el nombre exacto de tu Google Sheet

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

# El JSON de ejemplo que proporcionaste (recortado para la prueba, contiene semanas y salidas)
datos_json = {
  "propuesta": [
    {
      "semana_numero": 1,
      "rango_fechas": "Semana del 26 de Octubre al 1 de Noviembre 2026",
      "salidas": [
        {"fecha": "2026-10-26", "territorio_numero": 21, "conductor_nombre": "Juan Herrera"},
        {"fecha": "2026-10-27", "territorio_numero": 34, "conductor_nombre": "Lautaro Ludueña"},
        {"fecha": "2026-10-27", "territorio_numero": 35, "conductor_nombre": "Francisco Cristaldo"},
        {"fecha": "2026-10-28", "territorio_numero": 36, "conductor_nombre": "Karolaine Cardozo"},
        {"fecha": "2026-10-29", "territorio_numero": 24, "conductor_nombre": "Analia Israelson"},
        {"fecha": "2026-10-29", "territorio_numero": 1, "conductor_nombre": "Francisco Cristaldo"},
        {"fecha": "2026-10-30", "territorio_numero": 2, "conductor_nombre": "Juan Dominguez"},
        {"fecha": "2026-10-30", "territorio_numero": 19, "conductor_nombre": "Maximiliano Gomez"},
        {"fecha": "2026-10-31", "territorio_numero": 57, "conductor_nombre": "Juan Herrera"},
        {"fecha": "2026-10-31", "territorio_numero": 8, "conductor_nombre": "Jorge Cardozo"}
      ]
    }
  ]
}

def obtener_dia_semana(fecha_str):
    """
    Convierte una fecha 'YYYY-MM-DD' a un número de día de la semana:
    0 = Lunes, 1 = Martes, ..., 6 = Domingo
    """
    dt = datetime.strptime(fecha_str, "%Y-%m-%d")
    return dt.weekday() # weekday() en Python devuelve 0 para Lunes y 6 para Domingo

def ejecutar_prueba():
    if not os.path.exists(CREDENTIALS_PATH):
        print(f"Error: No se encontró el archivo de credenciales en '{CREDENTIALS_PATH}'")
        return

    # Autenticación con gspread
    creds = Credentials.from_service_account_file(CREDENTIALS_PATH, scopes=SCOPES)
    client = gspread.authorize(creds)

    try:
        sheet = client.open(SPREADSHEET_NAME).sheet1
        print(f"Conectado exitosamente a la hoja '{SPREADSHEET_NAME}'.")
    except Exception as e:
        print(f"Error al abrir la hoja de cálculo. Asegúrate de compartirla con el correo de la cuenta de servicio. Detalle: {e}")
        return

    # Posición inicial solicitada: Fila 3, Columna 1 (aunque empezaremos a escribir en C y D)
    # Columna 3 = C (Territorio), Columna 4 = D (Conductor)
    fila_actual = 3
    ultimo_dia = None

    for semana in datos_json["propuesta"]:
        print(f"\n Procesando {semana['rango_fechas']}...")
        
        for salida in semana["salidas"]:
            fecha = salida["fecha"]
            territorio = salida["territorio_numero"]
            conductor = salida["conductor_nombre"]

            # Obtener el día de la semana (0 a 6)
            dia_actual = obtener_dia_semana(fecha)

            if ultimo_dia is None:
                # Primer elemento: arranca en la fila base (3)
                fila_actual = 3
            elif dia_actual == ultimo_dia:
                # Si es el MISMO día o nombre, escribe en la fila de abajo (misma columna)
                fila_actual += 1
            else:
                # Si es DISTINTO, escribe 2 filas abajo
                fila_actual += 2

            ultimo_dia = dia_actual

            # Escribir en Columnas C (3) y D (4)
            # Columna C -> Territorio, Columna D -> Conductor (la columna B se deja vacía)
            sheet.update_cell(fila_actual, 3, territorio)
            sheet.update_cell(fila_actual, 4, conductor)
            
            print(f" -> Día {dia_actual} ({fecha}) | Fila {fila_actual}: Territorio {territorio}, Conductor {conductor}")

    print("\n ¡Proceso de prueba finalizado con éxito!")

if __name__ == "__main__":
    ejecutar_prueba()