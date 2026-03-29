"""
tests/test_endpoints.py

Tests de integración HTTP — el nivel más alto de la pirámide.

Usan TestClient de FastAPI con la DB SQLite de test inyectada via
dependency_overrides (configurado en conftest.py).

Qué testeamos:
  - Códigos de respuesta HTTP correctos
  - Shape del JSON de respuesta
  - Autenticación y autorización (401, 403)
  - Validación de input (422)
  - Casos borde (territorio sin asignaciones, rango inválido)

Qué NO testeamos aquí (ya cubierto en capas anteriores):
  - Lógica de severidad (test_services.py)
  - Orden cronológico (test_repositories.py)
  - Hashing y JWT (test_security.py)
"""

import pytest
from datetime import date


# ─────────────────────────────────────────────
# Tests: GET /v1/territorios/{numero}
# ─────────────────────────────────────────────

class TestObtenerHistorial:

    def test_territorio_sin_asignaciones_retorna_200_con_lista_vacia(
        self, client, territorio_existente
    ):
        response = client.get(f"/v1/territorios/{territorio_existente.numero}")
        assert response.status_code == 200

        data = response.json()
        assert data["territorio"] == territorio_existente.numero
        assert data["asignaciones"] == []
        assert "mensaje" in data

    def test_territorio_con_asignaciones_retorna_lista(
        self, client, asignacion_existente, territorio_existente
    ):
        response = client.get(f"/v1/territorios/{territorio_existente.numero}")
        assert response.status_code == 200

        data = response.json()
        assert len(data["asignaciones"]) == 1
        asig = data["asignaciones"][0]
        assert "conductor" in asig
        assert "fecha_asignado" in asig
        assert "fecha_completado" in asig
        assert "cantidad_abarcado" in asig

    def test_numero_no_entero_retorna_422(self, client):
        response = client.get("/v1/territorios/abc")
        assert response.status_code == 422


# ─────────────────────────────────────────────
# Tests: GET /v1/territorios/sugerencias
# ─────────────────────────────────────────────

class TestSugerencias:

    def test_rango_valido_retorna_200(self, client, territorio_existente):
        response = client.get("/v1/territorios/sugerencias?rango=1-20")
        assert response.status_code == 200

        data = response.json()
        assert "rango" in data
        assert "total" in data
        assert "sugerencias" in data
        assert isinstance(data["sugerencias"], list)

    def test_rango_invalido_retorna_400(self, client):
        response = client.get("/v1/territorios/sugerencias?rango=99-100")
        assert response.status_code == 400

    def test_sin_rango_retorna_422(self, client):
        response = client.get("/v1/territorios/sugerencias")
        assert response.status_code == 422

    def test_severidad_presente_en_cada_sugerencia(
        self, client, territorio_existente, asignacion_existente
    ):
        response = client.get("/v1/territorios/sugerencias?rango=1-20&limit=60")
        assert response.status_code == 200

        for s in response.json()["sugerencias"]:
            assert s["severidad"] in ("nunca", "critico", "alto", "normal")


# ─────────────────────────────────────────────
# Tests: POST /v1/asignaciones
# ─────────────────────────────────────────────

class TestCrearAsignacion:

    def _payload_valido(self, numero_territorio: int):
        return {
            "numero_territorio": numero_territorio,
            "conductor": "Conductor Test",
            "fecha_asignado": "2024-03-01",
            "fecha_completado": "2024-04-01",
            "total_abarcado": "Completo",
        }

    def test_crear_asignacion_correctamente(
        self, client, territorio_existente, auth_admin
    ):
        response = client.post(
            "/v1/asignaciones",
            json=self._payload_valido(territorio_existente.numero),
            headers=auth_admin,
        )
        assert response.status_code == 201

        data = response.json()
        assert data["message"] == "Asignación creada correctamente"
        assert "asignacion_id" in data
        assert "conductor_creado" in data

    def test_conductor_nuevo_reporta_creado_true(
        self, client, territorio_existente, auth_admin
    ):
        response = client.post(
            "/v1/asignaciones",
            json={**self._payload_valido(territorio_existente.numero),
                  "conductor": "Conductor Totalmente Nuevo XYZ"},
            headers=auth_admin,
        )
        assert response.status_code == 201
        assert response.json()["conductor_creado"] is True

    def test_sin_token_retorna_401(self, client, territorio_existente):
        response = client.post(
            "/v1/asignaciones",
            json=self._payload_valido(territorio_existente.numero),
        )
        assert response.status_code == 401

    def test_token_sin_rol_admin_retorna_403(
        self, client, territorio_existente, auth_usuario
    ):
        response = client.post(
            "/v1/asignaciones",
            json=self._payload_valido(territorio_existente.numero),
            headers=auth_usuario,
        )
        assert response.status_code == 403

    def test_territorio_inexistente_retorna_404(self, client, auth_admin):
        response = client.post(
            "/v1/asignaciones",
            json=self._payload_valido(9999),   # no existe
            headers=auth_admin,
        )
        assert response.status_code == 404

    def test_fecha_completado_anterior_a_asignado_retorna_422(
        self, client, territorio_existente, auth_admin
    ):
        response = client.post(
            "/v1/asignaciones",
            json={
                "numero_territorio": territorio_existente.numero,
                "conductor": "Test",
                "fecha_asignado": "2024-05-01",
                "fecha_completado": "2024-01-01",   # anterior → inválido
                "total_abarcado": "Completo",
            },
            headers=auth_admin,
        )
        assert response.status_code == 422

    def test_conductor_vacio_retorna_422(
        self, client, territorio_existente, auth_admin
    ):
        response = client.post(
            "/v1/asignaciones",
            json={**self._payload_valido(territorio_existente.numero),
                  "conductor": "   "},  # solo espacios
            headers=auth_admin,
        )
        assert response.status_code == 422

    def test_payload_incompleto_retorna_422(self, client, auth_admin):
        response = client.post(
            "/v1/asignaciones",
            json={"conductor": "Solo conductor, faltan campos"},
            headers=auth_admin,
        )
        assert response.status_code == 422


# ─────────────────────────────────────────────
# Tests: GET /health
# ─────────────────────────────────────────────

class TestHealth:

    def test_health_retorna_ok(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"