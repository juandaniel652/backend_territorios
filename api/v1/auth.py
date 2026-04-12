"""
api/v1/auth.py

Router de autenticación. Solo HTTP: recibe credenciales, devuelve token.

La lógica de verificar usuario y crear token vive en AuthService
(que crearemos en domain/auth/ — por ahora inline aquí de forma limpia
hasta que el dominio auth justifique su propia carpeta).

Reemplaza login.py original que importaba directamente de auth.py
mezclando responsabilidades HTTP con lógica de seguridad.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import text

from core.database import get_db
from core.security import verify_password, create_access_token, get_password_hash

router = APIRouter(prefix="/auth", tags=["auth"])


# ── Schema de respuesta ──────────────────────────────────────────────────────

class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"

class UserCreate(BaseModel):
    email: str
    password: str


# ── Helpers locales (hasta que auth tenga su propio dominio) ─────────────────

def _get_user_by_email(email: str, db: Session) -> dict | None:
    """
    Busca un usuario por email en la DB.
    Retorna dict con user_id, email, password_hash, rol — o None.

    Separado del endpoint para ser testeable sin HTTP.
    """
    row = db.execute(
        text(
            "SELECT id, email, password_hash, rol "
            "FROM usuarios WHERE email = :email"
        ),
        {"email": email},
    ).fetchone()

    if not row:
        return None

    return {
        "user_id": row.id,
        "email": row.email,
        "password_hash": row.password_hash,
        "rol": row.rol,
    }


# ── Endpoint ─────────────────────────────────────────────────────────────────

@router.post("/login", response_model=TokenOut)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """
    Autentica un usuario y devuelve un JWT.

    - username: email del usuario
    - password: contraseña en texto plano (se verifica contra el hash en DB)

    Raises:
        HTTPException 401: credenciales incorrectas.
    """
    user = _get_user_by_email(form_data.username, db)

    if not user or not verify_password(form_data.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token(
        {"user_id": user["user_id"], "rol": user["rol"]}
    )

    return TokenOut(access_token=token)

#---------------------------------------------

@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(user_in: UserCreate, db: Session = Depends(get_db)):
    """
    Registra un nuevo usuario. Por defecto el rol es 'user'.
    """
    # 1. Verificar si ya existe
    existe = _get_user_by_email(user_in.email, db)
    if existe:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El email ya está registrado"
        )
    
    # 2. Hashear password e insertar
    h_password = get_password_hash(user_in.password)
    
    try:
        db.execute(
            text("INSERT INTO usuarios (email, password_hash) VALUES (:email, :pw)"),
            {"email": user_in.email, "pw": h_password}
        )
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Error al crear usuario")

    return {"message": "Usuario creado exitosamente"}