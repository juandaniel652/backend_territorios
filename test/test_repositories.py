"""
tests/test_repositories.py

Tests de la capa de repositorios contra SQLite en memoria.

A diferencia de los tests de servicios (que usan mocks), acá
sí usamos la DB — pero SQLite en memoria, no PostgreSQL.

Qué testeamos:
  - Que las queries devuelven lo que se insertó
  - Que obtener_o_crear funciona correctamente
  - Que el historial retorna en orden cronológico
  - Casos borde: territorio sin asignaciones, conductor inexistente
"""

import pytest
from datetime import date

from domain.territorio.repository import TerritorioRepository
from domain.conductor.repository import ConductorRepository
from domain.asignacion.repository import AsignacionRepository
from domain.territorio.model import Territorio
from domain.conductor.model import Conductor
from domain.asignacion.model import Asignacion


# ─────────────────────────────────────────────
# Tests: TerritorioRepository
# ─────────────────────────────────────────────

class TestTerritorioRepository:

    def test_obtener_por_numero_existente(self, db, territorio_existente):
        repo = TerritorioRepository(db)
        resultado = repo.obtener_por_numero(territorio_existente.numero)
        assert resultado is not None
        assert resultado.id == territorio_existente.id

    def test_obtener_por_numero_inexistente_retorna_none(self, db):
        repo = TerritorioRepository(db)
        resultado = repo.obtener_por_numero(9999)
        assert resultado is None

    def test_obtener_por_id_existente(self, db, territorio_existente):
        repo = TerritorioRepository(db)
        resultado = repo.obtener_por_id(territorio_existente.id)
        assert resultado is not None
        assert resultado.numero == territorio_existente.numero

    def test_historial_vacio_cuando_no_hay_asignaciones(self, db, territorio_existente):
        repo = TerritorioRepository(db)
        resultado = repo.obtener_asignaciones_historial(territorio_existente.numero)
        assert resultado == []

    def test_historial_retorna_asignaciones_en_orden_cronologico(
        self, db, territorio_existente, conductor_existente
    ):
        """Inserta dos asignaciones fuera de orden y verifica que vuelven ordenadas."""
        db.add(Asignacion(
            territorio_id=territorio_existente.id,
            conductor_id=conductor_existente.id,
            fecha_asignado=date(2024, 6, 1),
            fecha_completado=date(2024, 7, 1),
            cantidad_abarcado="Completo",
        ))
        db.add(Asignacion(
            territorio_id=territorio_existente.id,
            conductor_id=conductor_existente.id,
            fecha_asignado=date(2024, 1, 1),   # más antigua
            fecha_completado=date(2024, 2, 1),
            cantidad_abarcado="Parcial",
        ))
        db.flush()

        repo = TerritorioRepository(db)
        resultado = repo.obtener_asignaciones_historial(territorio_existente.numero)

        assert len(resultado) == 2
        assert resultado[0].fecha_asignado == date(2024, 1, 1)   # primera cronológicamente
        assert resultado[1].fecha_asignado == date(2024, 6, 1)


# ─────────────────────────────────────────────
# Tests: ConductorRepository
# ─────────────────────────────────────────────

class TestConductorRepository:

    def test_obtener_por_nombre_existente(self, db, conductor_existente):
        repo = ConductorRepository(db)
        resultado = repo.obtener_por_nombre(conductor_existente.nombre_completo)
        assert resultado is not None
        assert resultado.id == conductor_existente.id

    def test_obtener_por_nombre_inexistente_retorna_none(self, db):
        repo = ConductorRepository(db)
        resultado = repo.obtener_por_nombre("Nombre Que No Existe")
        assert resultado is None

    def test_crear_conductor(self, db):
        repo = ConductorRepository(db)
        nuevo = repo.crear("María González")
        assert nuevo.id is not None
        assert nuevo.nombre_completo == "María González"

    def test_obtener_o_crear_conductor_nuevo(self, db):
        repo = ConductorRepository(db)
        conductor, creado = repo.obtener_o_crear("Conductor Nuevo")
        assert creado is True
        assert conductor.nombre_completo == "Conductor Nuevo"
        assert conductor.id is not None

    def test_obtener_o_crear_conductor_existente(self, db, conductor_existente):
        repo = ConductorRepository(db)
        conductor, creado = repo.obtener_o_crear(conductor_existente.nombre_completo)
        assert creado is False
        assert conductor.id == conductor_existente.id

    def test_obtener_o_crear_no_duplica(self, db):
        """Llamar dos veces con el mismo nombre no crea dos conductores."""
        repo = ConductorRepository(db)
        repo.obtener_o_crear("Carlos Ruiz")
        _, creado_segunda_vez = repo.obtener_o_crear("Carlos Ruiz")
        assert creado_segunda_vez is False

        total = db.query(Conductor).filter(
            Conductor.nombre_completo == "Carlos Ruiz"
        ).count()
        assert total == 1


# ─────────────────────────────────────────────
# Tests: AsignacionRepository
# ─────────────────────────────────────────────

class TestAsignacionRepository:

    def test_crear_asignacion(self, db, territorio_existente, conductor_existente):
        repo = AsignacionRepository(db)
        asignacion = repo.crear(
            territorio_id=territorio_existente.id,
            conductor_id=conductor_existente.id,
            fecha_asignado=date(2024, 5, 1),
            fecha_completado=date(2024, 6, 1),
            cantidad_abarcado="Completo",
        )
        assert asignacion.id is not None
        assert asignacion.territorio_id == territorio_existente.id
        assert asignacion.conductor_id == conductor_existente.id

    def test_obtener_por_id_existente(self, db, asignacion_existente):
        repo = AsignacionRepository(db)
        resultado = repo.obtener_por_id(asignacion_existente.id)
        assert resultado is not None
        assert resultado.id == asignacion_existente.id

    def test_obtener_por_id_inexistente_retorna_none(self, db):
        repo = AsignacionRepository(db)
        resultado = repo.obtener_por_id(99999)
        assert resultado is None

    def test_listar_por_territorio(
        self, db, territorio_existente, conductor_existente
    ):
        repo = AsignacionRepository(db)
        repo.crear(
            territorio_id=territorio_existente.id,
            conductor_id=conductor_existente.id,
            fecha_asignado=date(2024, 3, 1),
            fecha_completado=date(2024, 4, 1),
            cantidad_abarcado="a,b",
        )
        repo.crear(
            territorio_id=territorio_existente.id,
            conductor_id=conductor_existente.id,
            fecha_asignado=date(2024, 1, 1),
            fecha_completado=date(2024, 2, 1),
            cantidad_abarcado="c,d",
        )

        resultado = repo.listar_por_territorio(territorio_existente.id)

        assert len(resultado) == 2
        # Verifica orden cronológico
        assert resultado[0].fecha_asignado <= resultado[1].fecha_asignado

    def test_listar_por_territorio_vacio(self, db, territorio_existente):
        repo = AsignacionRepository(db)
        resultado = repo.listar_por_territorio(territorio_existente.id)
        assert resultado == []