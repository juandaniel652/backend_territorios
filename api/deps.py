"""
api/deps.py

Dependencias FastAPI compartidas por todos los routers.

Centraliza:
  1. get_db()           — sesión de DB por request
  2. get_current_user() — validación JWT y extracción de usuario
  3. require_admin()    — shortcut para rutas solo-admin

Problemas del código original:
  - get_current_user() vivía en auth.py junto con hashing y JWT
  - Accedía a la DB con engine.connect() directo (sin sesión gestionada)
  - oauth2_scheme estaba hardcodeado en auth.py sin posibilidad de override
  - require_admin no existía: la verificación if user["rol"] != "admin"
    estaba inline en cada router que la necesitaba

Ahora cada dependencia tiene una única responsabilidad y puede
ser sobreescrita en tests con app.dependency_overrides.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.orm import Session

from core.database import get_db
from core.security import decode_access_token


# ── OAuth2 scheme ────────────────────────────────────────────────────────────
# tokenUrl apunta al endpoint de login. FastAPI lo usa para el botón
# "Authorize" en /docs — no afecta la validación real del token.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


# ── Tipos de retorno ─────────────────────────────────────────────────────────
# Dict simple por ahora. Si el sistema crece conviene un dataclass/schema.
CurrentUser = dict  # {"user_id": int, "rol": str}


# ─────────────────────────────────────────────────────────────────────────────
# 1. Sesión de DB
# ─────────────────────────────────────────────────────────────────────────────

# Re-exportamos get_db desde core/database para que los routers
# solo importen desde api/deps y no necesiten conocer core/
def get_db_session() -> Session:
    """
    Re-export de core.database.get_db para uso en routers.
    Permite override en tests sin tocar core/:

        app.dependency_overrides[deps.get_db_session] = lambda: test_db
    """
    return get_db()


# Usamos directamente el generador de core como dependencia
DatabaseDep = Depends(get_db)


# ─────────────────────────────────────────────────────────────────────────────
# 2. Usuario autenticado
# ─────────────────────────────────────────────────────────────────────────────

def get_current_user(
    token: str = Depends(oauth2_scheme),
) -> CurrentUser:
    """
    Valida el JWT del header Authorization: Bearer <token>.

    Reemplaza get_current_user() de auth.py original que:
      - Accedía a la DB para buscar el usuario (innecesario: el payload ya tiene todo)
      - Tenía la lógica de hashing mezclada en el mismo archivo

    Ahora solo decodifica el token — sin DB, sin efectos secundarios.

    Raises:
        HTTPException 401: token inválido, expirado o mal formado.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudo validar el token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        token_data = decode_access_token(token)
    except JWTError:
        raise credentials_exception

    return {"user_id": token_data.user_id, "rol": token_data.rol}


# ─────────────────────────────────────────────────────────────────────────────
# 3. Usuario admin (shortcut para rutas protegidas)
# ─────────────────────────────────────────────────────────────────────────────

def require_admin(
    current_user: CurrentUser = Depends(get_current_user),
) -> CurrentUser:
    """
    Dependencia para rutas exclusivas de admin.

    Reemplaza el bloque inline que aparecía en asignaciones.py:
        if user["rol"] != "admin":
            raise HTTPException(status_code=403, ...)

    Uso en routers:
        @router.post("/asignaciones")
        def crear(user = Depends(require_admin)):
            ...

    Raises:
        HTTPException 403: si el usuario autenticado no tiene rol admin.
    """
    if current_user["rol"] != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requieren permisos de administrador",
        )
    return current_user