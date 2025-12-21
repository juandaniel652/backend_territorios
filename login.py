# login.py
from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import OAuth2PasswordRequestForm
from auth import authenticate_user, create_access_token

router = APIRouter()

@router.post("/login")
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Recibe username y password, devuelve JWT si son correctos
    """
    if not form_data:
        raise HTTPException(status_code=400, detail="Formulario de login vacío")

    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario o contraseña incorrectos")

    token = create_access_token({"user_id": user["user_id"], "rol": user["rol"]})
    return {"access_token": token, "token_type": "bearer"}
