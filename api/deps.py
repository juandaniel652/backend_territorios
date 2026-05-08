from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.orm import Session

from core.database import get_db
from core.security import decode_access_token

# --- NUEVOS IMPORTS PARA EL SERVICE FACTORY ---
from domain.asignacion.service import AsignacionService
from domain.asignacion.repository import AsignacionRepository
from domain.territorio.repository import TerritorioRepository
from domain.conductor.repository import ConductorRepository
from domain.salida.repository import SalidaRepository

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

CurrentUser = dict

# ─────────────────────────────────────────────────────────────────────────────
# 1. Sesión de DB
# ─────────────────────────────────────────────────────────────────────────────

def get_db_session() -> Session:
    return get_db()

DatabaseDep = Depends(get_db)

# ── NUEVA DEPENDENCIA: Factoría de AsignacionService ────────────────────────
def get_asignacion_service(db: Session = Depends(get_db)) -> AsignacionService:
    """
    Construye el AsignacionService con todos sus repositorios.
    Permite que cualquier router (como territorios.py) use la lógica de asignación.
    """
    return AsignacionService(
        db=db,
        asignacion_repo=AsignacionRepository(db),
        territorio_repo=TerritorioRepository(db),
        conductor_repo=ConductorRepository(db),
        salida_repo=SalidaRepository(db)
    )

# ─────────────────────────────────────────────────────────────────────────────
# 2. Usuario autenticado
# ─────────────────────────────────────────────────────────────────────────────

def get_current_user(
    token: str = Depends(oauth2_scheme),
) -> CurrentUser:
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
# 3. Usuario admin
# ─────────────────────────────────────────────────────────────────────────────

def require_admin(
    current_user: CurrentUser = Depends(get_current_user),
) -> CurrentUser:
    if current_user["rol"] != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requieren permisos de administrador",
        )
    return current_user