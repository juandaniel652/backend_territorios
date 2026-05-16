from fastapi import APIRouter
from api.v1 import auth, territorios, asignaciones, salida, agenda_router


router = APIRouter(prefix="/api/v1")

router.include_router(auth.router)
router.include_router(territorios.router)
router.include_router(asignaciones.router)  # ← ESTE ES EL FIX
router.include_router(salida.router)
router.include_router(agenda_router.router)