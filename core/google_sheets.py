"""
backend/core/google_sheets.py
"""
import os
import json
import gspread
from google.oauth2.service_account import Credentials

BASE_DIRECTORY = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CREDENTIALS_PATH = os.path.join(BASE_DIRECTORY, "core", "llave_nueva.json")

def get_sheets():
    """Inicializa y retorna el cliente autenticado de gspread."""
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    
    # 1. Intentar leer la variable de entorno de Render (Producción seguro)
    credentials_env = os.environ.get("GOOGLE_CREDS_JSON")
    if credentials_env:
        info = json.loads(credentials_env)
        credentials = Credentials.from_service_account_info(info, scopes=scopes)
        return gspread.authorize(credentials)
        
    # 2. Fallback al archivo físico (Para cuando programás local)
    if os.path.exists(CREDENTIALS_PATH):
        credentials = Credentials.from_service_account_file(CREDENTIALS_PATH, scopes=scopes)
        return gspread.authorize(credentials)
        
    raise FileNotFoundError(
        "No se encontró 'GOOGLE_CREDS_JSON' en las variables de entorno "
        f"ni el archivo físico en: {CREDENTIALS_PATH}"
    )