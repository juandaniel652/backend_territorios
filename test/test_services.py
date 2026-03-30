"""
tests/test_services.py

Tests unitarios de la capa de servicios.

Patrón: los servicios dependen de protocolos (interfaces), no de
implementaciones concretas. Acá creamos mocks simples que implementan
esos mismos protocolos — sin DB, sin HTTP, sin nada externo.

Esto testea la lógica de negocio pura:
  - ¿Calcula bien la severidad?
  - ¿Lanza 404 si no existe el territorio?
  - ¿Hace rollback si falla algo?
  - ¿Retorna conductor_creado=True cuando corresponde?
"""

import pytest
from datetime import date
from unittest.mock import MagicMock
from fastapi import HTTPException

from domain.territorio.service import TerritorioService, _calcular_severidad
from domain.territorio.schema import AsignacionDeTerritorioOut, SugerenciaTerritorio
from domain.asignacion.service import AsignacionService
from domain.asignacion.schema import AsignacionCreate
from domain.territorio.model import Territorio
from domain.conductor.model import Conductor
from domain.asignacion.model import Asignacion


# ─────────────────────────────────────────────
# Helpers: mocks de repositorios
# ─────────────────────────────────────────────

def mock_territorio_repo(
    territorio=None,
    asignaciones=None,
    sugerencias=None,
):
    """Crea un mock del repositorio de territorios con valores configurables."""
    repo = MagicMock()
    repo.obtener_por_numero.return_value = territorio
    repo.obtener_asignaciones_historial.return_value = asignaciones or []
    repo.obtener_sugerencias.return_value = sugerencias or []
    return repo


def mock_conductor_repo(conductor=None, creado=False):
    repo = MagicMock()
    repo.obtener_o_crear.return_value = (conductor, creado)
    return repo


def mock_asignacion_repo(asignacion=None):
    repo = MagicMock()
    repo.crear.return_value = asignacion
    return repo


# ─────────────────────────────────────────────
# Tests: lógica de negocio pura (sin mocks)
# ─────────────────────────────────────────────

class TestCalcularSeveridad:
    """
    _calcular_severidad es una función pura — el test más simple posible.
    Si esta lógica cambia, estos tests fallan inmediatamente.
    """

    def test_nunca_asignado(self):
        assert _calcular_severidad(None) == "nunca"

    def test_critico(self):
        assert _calcular_severidad(30) == "critico"
        assert _calcular_severidad(90) == "critico"

    def test_alto(self):
        assert _calcular_severidad(15) == "alto"
        assert _calcular_severidad(29) == "alto"

    def test_normal(self):
        assert _calcular_severidad(0) == "normal"
        assert _calcular_severidad(14) == "normal"


# ─────────────────────────────────────────────
# Tests: TerritorioService
# ─────────────────────────────────────────────

class TestTerritorioServiceHistorial:

    def test_retorna_asignaciones_cuando_existen(self):
        asignaciones = [
            AsignacionDeTerritorioOut(
                conductor="Ana García",
                fecha_asignado=date(2024, 1, 1),
                fecha_completado=date(2024, 2, 1),
                cantidad_abarcado="Completo",
            )
        ]
        repo = mock_territorio_repo(asignaciones=asignaciones)
        service = TerritorioService(repo)

        result = service.obtener_historial(5)

        assert result.territorio == 5
        assert len(result.asignaciones) == 1
        assert result.asignaciones[0].conductor == "Ana García"
        assert result.mensaje is None

    def test_retorna_mensaje_cuando_no_hay_asignaciones(self):
        repo = mock_territorio_repo(asignaciones=[])
        service = TerritorioService(repo)

        result = service.obtener_historial(5)

        assert result.asignaciones == []
        assert result.mensaje is not None

    def test_llama_al_repo_con_el_numero_correcto(self):
        repo = mock_territorio_repo()
        service = TerritorioService(repo)

        service.obtener_historial(42)

        repo.obtener_asignaciones_historial.assert_called_once_with(42)


class TestTerritorioServiceSugerencias:

    def test_rango_invalido_lanza_400(self):
        repo = mock_territorio_repo()
        service = TerritorioService(repo)

        with pytest.raises(HTTPException) as exc:
            service.obtener_sugerencias("99-100", limit=5)

        assert exc.value.status_code == 400

    def test_enriquece_severidad_correctamente(self):
        hoy = date.today()
        from datetime import timedelta
        hace_40_dias = hoy - timedelta(days=40)

        sugerencias_raw = [
            SugerenciaTerritorio(
                numero=1,
                ultima_fecha=hace_40_dias,
                dias_atraso=None,
                severidad="",
            )
        ]
        repo = mock_territorio_repo(sugerencias=sugerencias_raw)
        service = TerritorioService(repo)

        result = service.obtener_sugerencias("1-20", limit=5)

        assert result.sugerencias[0].severidad == "critico"
        assert result.sugerencias[0].dias_atraso == 40

    def test_territorio_nunca_asignado_tiene_severidad_nunca(self):
        sugerencias_raw = [
            SugerenciaTerritorio(
                numero=2,
                ultima_fecha=None,
                dias_atraso=None,
                severidad="",
            )
        ]
        repo = mock_territorio_repo(sugerencias=sugerencias_raw)
        service = TerritorioService(repo)

        result = service.obtener_sugerencias("1-20", limit=5)

        assert result.sugerencias[0].severidad == "nunca"
        assert result.sugerencias[0].dias_atraso is None


# ─────────────────────────────────────────────
# Tests: AsignacionService
# ─────────────────────────────────────────────

class TestAsignacionService:

    def _hacer_servicio(
        self,
        territorio=None,
        conductor=None,
        conductor_creado=False,
        asignacion=None,
    ):
        """Factory helper para construir el servicio con mocks configurados."""
        db = MagicMock()

        t = territorio or Territorio(id=1, numero=5)
        c = conductor or Conductor(id=1, nombre_completo="Pedro López")
        a = asignacion or Asignacion(
            id=10,
            territorio_id=1,
            conductor_id=1,
            fecha_asignado=date(2024, 3, 1),
            fecha_completado=date(2024, 4, 1),
            cantidad_abarcado="Completo",
        )

        return AsignacionService(
            db=db,
            asignacion_repo=mock_asignacion_repo(a),
            territorio_repo=mock_territorio_repo(territorio=t),
            conductor_repo=mock_conductor_repo(c, conductor_creado),
        ), db

    def _data_valida(self):
        return AsignacionCreate(
            numero_territorio=5,
            conductor="Pedro López",
            fecha_asignado=date(2024, 3, 1),
            fecha_completado=date(2024, 4, 1),
            cantidad_abarcado="Completo",
        )

    def test_crea_asignacion_correctamente(self):
        service, db = self._hacer_servicio()

        result = service.crear_asignacion(self._data_valida())

        assert result.message == "Asignación creada correctamente"
        assert result.asignacion_id == 10
        db.commit.assert_called_once()

    def test_conductor_nuevo_reporta_conductor_creado_true(self):
        service, _ = self._hacer_servicio(conductor_creado=True)

        result = service.crear_asignacion(self._data_valida())

        assert result.conductor_creado is True

    def test_conductor_existente_reporta_conductor_creado_false(self):
        service, _ = self._hacer_servicio(conductor_creado=False)

        result = service.crear_asignacion(self._data_valida())

        assert result.conductor_creado is False

    def test_territorio_inexistente_lanza_404(self):
        db = MagicMock()
        service = AsignacionService(
            db=db,
            asignacion_repo=mock_asignacion_repo(),
            territorio_repo=mock_territorio_repo(territorio=None),  # no existe
            conductor_repo=mock_conductor_repo(),
        )

        with pytest.raises(HTTPException) as exc:
            service.crear_asignacion(self._data_valida())

        assert exc.value.status_code == 404
        db.rollback.assert_called_once()

    def test_error_inesperado_hace_rollback_y_lanza_500(self):
        db = MagicMock()
        territorio_repo = mock_territorio_repo(territorio=Territorio(id=1, numero=5))
        conductor_repo = MagicMock()
        conductor_repo.obtener_o_crear.side_effect = RuntimeError("DB caída")

        service = AsignacionService(
            db=db,
            asignacion_repo=mock_asignacion_repo(),
            territorio_repo=territorio_repo,
            conductor_repo=conductor_repo,
        )

        with pytest.raises(HTTPException) as exc:
            service.crear_asignacion(self._data_valida())

        assert exc.value.status_code == 500
        db.rollback.assert_called_once()