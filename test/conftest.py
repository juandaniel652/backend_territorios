"""
tests/conftest.py

Infraestructura compartida para todos los tests.

Qué resuelve este archivo:
  - Crea una DB SQLite en memoria por cada sesión de test (sin tocar PostgreSQL)
  - Provee una sesión de DB aislada por test (rollback automático al terminar)
  - Provee un TestClient de FastAPI con la DB de test inyectada
  - Define fixtures reutilizables: territorio, conductor, asignacion de prueba

Flujo de aislamiento:
  engine_test (SQLite en memoria, creado una vez por sesión)
      └── db (sesión nueva por test, con rollback al final)
              └── client (TestClient con dependency_override apuntando a db)

Esto garantiza que cada test empieza con un estado limpio sin
necesidad de limpiar tablas manualmente.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base, get_db
from main import app

# ── Motor SQLite en memoria ──────────────────────────────────────────────────
# connect_args necesario para SQLite: permite compartir la conexión entre hilos
# (FastAPI y pytest corren en hilos distintos).
TEST_DATABASE_URL = "sqlite:///:memory:"

engine_test = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
)

TestingSessionLocal = sessionmaker(
    bind=engine_test,
    autocommit=False,
    autoflush=False,
)


# ── Crear todas las tablas una vez por sesión de pytest ──────────────────────

@pytest.fixture(scope="session", autouse=True)
def crear_tablas():
    """Crea el schema completo en SQLite antes de correr cualquier test."""
    Base.metadata.create_all(bind=engine_test)
    yield
    Base.metadata.drop_all(bind=engine_test)


# ── Sesión aislada por test ──────────────────────────────────────────────────

@pytest.fixture()
def db():
    """
    Sesión de DB con rollback automático al finalizar cada test.

    Patrón: abre una transacción, corre el test, hace rollback.
    La DB queda exactamente igual para el test siguiente.
    No necesitás DELETE FROM en ningún test.
    """
    connection = engine_test.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


# ── TestClient con DB de test ────────────────────────────────────────────────

@pytest.fixture()
def client(db):
    """
    Cliente HTTP de FastAPI apuntando a la DB de test.

    dependency_overrides reemplaza get_db() en toda la app
    por la sesión de test — sin tocar nada del código de producción.
    """
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ── Fixtures de datos reutilizables ─────────────────────────────────────────

@pytest.fixture()
def territorio_existente(db):
    """Inserta un territorio de prueba y lo retorna."""
    from domain.territorio.model import Territorio
    t = Territorio(numero=99)
    db.add(t)
    db.flush()
    return t


@pytest.fixture()
def conductor_existente(db):
    """Inserta un conductor de prueba y lo retorna."""
    from domain.conductor.model import Conductor
    c = Conductor(nombre_completo="Juan Pérez")
    db.add(c)
    db.flush()
    return c


@pytest.fixture()
def asignacion_existente(db, territorio_existente, conductor_existente):
    """Inserta una asignación completa de prueba y la retorna."""
    from domain.asignacion.model import Asignacion
    from datetime import date
    a = Asignacion(
        territorio_id=territorio_existente.id,
        conductor_id=conductor_existente.id,
        fecha_asignado=date(2024, 1, 15),
        fecha_completado=date(2024, 2, 10),
        cantidad_abarcado="Completo",
    )
    db.add(a)
    db.flush()
    return a


@pytest.fixture()
def token_admin(client):
    """
    Genera un JWT de admin válido para tests de endpoints protegidos.
    Usa create_access_token directamente — sin pasar por el endpoint de login
    para no depender de que exista un usuario en la DB de test.
    """
    from core.security import create_access_token
    return create_access_token({"user_id": 1, "rol": "admin"})


@pytest.fixture()
def token_usuario(client):
    """JWT con rol 'usuario' para verificar que rutas admin lo rechazan."""
    from core.security import create_access_token
    return create_access_token({"user_id": 2, "rol": "usuario"})


@pytest.fixture()
def auth_admin(token_admin):
    """Header Authorization listo para pasar a client.post/get."""
    return {"Authorization": f"Bearer {token_admin}"}


@pytest.fixture()
def auth_usuario(token_usuario):
    """Header Authorization con rol no-admin."""
    return {"Authorization": f"Bearer {token_usuario}"}