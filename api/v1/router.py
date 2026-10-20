from fastapi import APIRouter
from api.v1 import auth, territorios, asignaciones, salida, agenda, planillas

router = APIRouter(prefix="/api/v1")

router.include_router(auth.router)
router.include_router(territorios.router)
router.include_router(asignaciones.router)
router.include_router(salida.router)
router.include_router(agenda.router) 
router.include_router(planillas.router)
