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

from domain.planilla.repository import PlanillaRepository # Nuevo import
from domain.territorio.service import TerritorioService

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
    # 1. Instanciamos los repositorios necesarios
    territorio_repo = TerritorioRepository(db)
    planilla_repo = PlanillaRepository(db)
    
    # 2. Instanciamos el TerritorioService (que el AsignacionService necesita para la lógica de planillas)
    territorio_service = TerritorioService(territorio_repo, planilla_repo)

    # 3. Construimos el AsignacionService con TODO lo que pide su __init__
    return AsignacionService(
        db=db,
        planilla_repo=planilla_repo,
        territorio_service=territorio_service,
        asignacion_repo=AsignacionRepository(db),
        territorio_repo=territorio_repo,
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