# backend/db_utils.py
from sqlalchemy import text
from database import SessionLocal

def insertar_planilla(tabla: str, datos: dict):
    session = SessionLocal()
    try:
        columnas = ", ".join(datos.keys())
        valores = ", ".join([f":{k}" for k in datos.keys()])
        query = text(f"INSERT INTO {tabla} ({columnas}) VALUES ({valores})")
        session.execute(query, datos)
        session.commit()
    finally:
        session.close()

def obtener_planillas(tabla: str, limite: int = 10):
    session = SessionLocal()
    try:
        query = text(f"SELECT * FROM {tabla} ORDER BY id DESC LIMIT :limite")
        result = session.execute(query, {"limite": limite})
        return result.fetchall()
    finally:
        session.close()
