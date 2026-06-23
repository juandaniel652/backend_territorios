"""
backend/core/google_sheets.py
"""
import os
import gspread
from google.oauth2.service_account import Credentials
from core.config import settings # Si tenés variables de entorno ahí, o rutas fijas

# Rutas relativas seguras basadas en la ubicación de core/
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CREDENTIALS_PATH = os.path.join(BASE_DIR, "core", "llave_nueva.json")

def obtener_cliente_sheets():
    """Inicializa y retorna el cliente autenticado de gspread."""
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    if not os.path.exists(CREDENTIALS_PATH):
        raise FileNotFoundError(f"No se encontró el archivo de credenciales de Google Sheets en: {CREDENTIALS_PATH}")
        
    creds = Credentials.from_service_account_file(CREDENTIALS_PATH, scopes=scopes)
    return gspread.authorize(creds)