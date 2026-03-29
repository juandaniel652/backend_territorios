"""
core/database.py

Unifica database.py y db_utils.py del código original.
Elimina la segunda conexión con psycopg2 hardcodeada de insertar_asignaciones.py.

Patrón DI: get_db() es una dependencia inyectable en FastAPI.
Los repositories reciben Session como argumento → nunca crean su propia conexión.
Esto permite mockear la DB completa en tests sin tocar un solo router.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from core.config import settings


# --- Motor SQLAlchemy ---
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,       # valida conexión antes de usarla
    pool_size=5,              # conexiones activas simultáneas
    max_overflow=10,          # conexiones extra bajo carga
)

# --- Fábrica de sesiones ---
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
)


# --- Base declarativa compartida para todos los modelos ---
class Base(DeclarativeBase):
    pass


# --- Dependencia FastAPI (Dependency Injection) ---
def get_db():
    """
    Generador que abre una sesión por request y la cierra al terminar.
    
    Uso en routers:
        def mi_ruta(db: Session = Depends(get_db)):
            ...
    
    En tests:
        app.dependency_overrides[get_db] = lambda: test_session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()