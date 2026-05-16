from fastapi import APIRouter
from api.v1 import auth, territorios, asignaciones, salida, agenda  # ← Cambiamos 'agenda_router' por 'agenda'

router = APIRouter(prefix="/api/v1")

router.include_router(auth.router)
router.include_router(territorios.router)
router.include_router(asignaciones.router)
router.include_router(salida.router)
router.include_router(agenda.router)  # ← Incluimos el nuevo router quincenal