"""
api/v1/router.py

Agrupador central de todos los routers de la versión 1 de la API.

main.py solo necesita importar este router y montarlo.
Agregar un nuevo dominio = una línea aquí, nada más.

Ventaja de versionar (/v1/):
  Si en el futuro necesitás un breaking change podés montar
  api/v2/router.py en paralelo sin tocar los clientes existentes.
"""

from fastapi import APIRouter
from api.v1 import auth, territorios, asignaciones

router = APIRouter(prefix="/api/v1")
router.include_router(auth.router)
router.include_router(territorios.router)
router.include_router(asignaciones.router)