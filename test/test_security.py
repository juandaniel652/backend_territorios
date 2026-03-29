"""
tests/test_security.py

Tests unitarios de core/security.py.

Son los más simples: funciones puras sin DB, sin HTTP.
Si estos fallan, todo lo demás falla también — son la base.
"""

import pytest
from datetime import timedelta
from jose import JWTError

from core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    decode_access_token,
)


# ── Hashing ──────────────────────────────────────────────────────────────────

class TestHashing:

    def test_hash_es_diferente_al_original(self):
        hashed = get_password_hash("mipassword")
        assert hashed != "mipassword"

    def test_verify_password_correcto(self):
        hashed = get_password_hash("mipassword")
        assert verify_password("mipassword", hashed) is True

    def test_verify_password_incorrecto(self):
        hashed = get_password_hash("mipassword")
        assert verify_password("otrapassword", hashed) is False

    def test_dos_hashes_del_mismo_password_son_distintos(self):
        """Argon2 agrega salt aleatorio — nunca dos hashes iguales."""
        h1 = get_password_hash("abc")
        h2 = get_password_hash("abc")
        assert h1 != h2


# ── JWT ───────────────────────────────────────────────────────────────────────

class TestJWT:

    def test_crear_y_decodificar_token(self):
        token = create_access_token({"user_id": 42, "rol": "admin"})
        data = decode_access_token(token)
        assert data.user_id == 42
        assert data.rol == "admin"

    def test_token_expirado_lanza_jwterror(self):
        token = create_access_token(
            {"user_id": 1, "rol": "admin"},
            expires_delta=timedelta(seconds=-1),  # ya expiró
        )
        with pytest.raises(JWTError):
            decode_access_token(token)

    def test_token_invalido_lanza_jwterror(self):
        with pytest.raises(JWTError):
            decode_access_token("esto.no.es.un.jwt")

    def test_token_sin_user_id_lanza_jwterror(self):
        """Payload incompleto debe ser rechazado."""
        token = create_access_token({"rol": "admin"})  # falta user_id
        with pytest.raises(JWTError):
            decode_access_token(token)

    def test_token_sin_rol_lanza_jwterror(self):
        token = create_access_token({"user_id": 1})  # falta rol
        with pytest.raises(JWTError):
            decode_access_token(token)