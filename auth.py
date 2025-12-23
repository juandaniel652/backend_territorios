# auth.py
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from datetime import datetime, timedelta
from passlib.context import CryptContext
from pydantic import BaseModel
from database import engine
from sqlalchemy import text

# -------------------------
# Configuración seguridad
# -------------------------
SECRET_KEY = "TU_CLAVE_SECRETA_SUPER_SEGURA"  # Cambiar en .env para producción
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


# -------------------------
# Schemas
# -------------------------
class TokenData(BaseModel):
    user_id: int
    rol: str

# -------------------------
# Funciones auxiliares
# -------------------------
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def authenticate_user(username: str, password: str):
   
    print("PASSWORD RECIBIDA:", password)
    print("LARGO:", len(password.encode("utf-8")))

    """Verifica usuario y contraseña en la DB"""
    with engine.connect() as conn:
        user = conn.execute(
            text("SELECT id, email, password_hash, rol FROM Usuarios WHERE email = :u"),
            {"u": username}
        ).fetchone()

    if not user:
        return None
    user_id, username_db, password_hash, rol = user
    if not verify_password(password, password_hash):
        return None
    return {"user_id": user_id, "username": username_db, "rol": rol}

def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# -------------------------
# Dependencia para rutas protegidas
# -------------------------
def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudo validar el token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: int = payload.get("user_id")
        rol: str = payload.get("rol")
        if user_id is None or rol is None:
            raise credentials_exception
        token_data = TokenData(user_id=user_id, rol=rol)
    except JWTError:
        raise credentials_exception
    return {"user_id": token_data.user_id, "rol": token_data.rol}

