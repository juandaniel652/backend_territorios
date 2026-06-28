"""
backend/core/google_sheets.py
"""
import os
import json
import gspread
from google.oauth2.service_account import Credentials

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CREDENTIALS_PATH = os.path.join(BASE_DIR, "core", "llave_nueva.json")

def obtener_cliente_sheets():
    """Inicializa y retorna el cliente autenticado de gspread."""
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    
    # 1. Intentar leer la variable de entorno de Render (Producción seguro)
    creds_env = os.environ.get("GOOGLE_CREDS_JSON")
    if creds_env:
        info = json.loads(creds_env)
        creds = Credentials.from_service_account_info(info, scopes=scopes)
        return gspread.authorize(creds)
        
    # 2. Fallback al archivo físico (Para cuando programás local)
    if os.path.exists(CREDENTIALS_PATH):
        creds = Credentials.from_service_account_file(CREDENTIALS_PATH, scopes=scopes)
        return gspread.authorize(creds)
        
    raise FileNotFoundError(
        "No se encontró 'GOOGLE_CREDS_JSON' en las variables de entorno "
        f"ni el archivo físico en: {CREDENTIALS_PATH}"
    )