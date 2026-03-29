"""
core/security.py

Extrae la lógica pura de seguridad de auth.py original.
auth.py mezclaba: hashing, JWT, acceso a DB y dependencia FastAPI — todo junto.

Aquí solo viven funciones puras sin efectos secundarios:
  - hash / verify de passwords
  - crear / decodificar tokens JWT

El acceso a DB para autenticar un usuario vive en auth_service.py (capa de servicio).
La dependencia FastAPI get_current_user vive en api/deps.py.

Esto hace que security.py sea testeable sin DB, sin HTTP, sin nada externo.
"""

from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
from core.config import settings


# --- Contexto de hashing ---
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


# --- Schema interno del token ---
class TokenData(BaseModel):
    user_id: int
    rol: str


# -------------------------
# Hashing
# -------------------------

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica que la contraseña plana coincide con el hash almacenado."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Genera el hash de una contraseña. Usar al registrar usuarios."""
    return pwd_context.hash(password)


# -------------------------
# JWT
# -------------------------

def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """
    Crea un JWT firmado con la SECRET_KEY.
    
    Args:
        data: payload a incluir (user_id, rol, etc.)
        expires_delta: tiempo de vida del token. Default: settings.ACCESS_TOKEN_EXPIRE_MINUTES
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> TokenData:
    """
    Decodifica y valida un JWT.
    
    Returns:
        TokenData con user_id y rol si el token es válido.
    
    Raises:
        JWTError: si el token es inválido o expiró.
    """
    payload = jwt.decode(
        token,
        settings.SECRET_KEY,
        algorithms=[settings.ALGORITHM],
    )
    user_id: int = payload.get("user_id")
    rol: str = payload.get("rol")

    if user_id is None or rol is None:
        raise JWTError("Payload incompleto")

    return TokenData(user_id=user_id, rol=rol)