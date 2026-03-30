"""
domain/asignacion/service.py

Servicio del dominio Asignacion.
Es el más importante del sistema: coordina tres repositorios en una
sola transacción atómica.

Flujo de crear_asignacion():
  1. Verificar que el territorio existe           → TerritorioRepository
  2. Obtener o crear el conductor                 → ConductorRepository
  3. Insertar la asignación con los IDs resueltos → AsignacionRepository
  4. Confirmar la transacción                     → db.commit()

Problemas del código original que resuelve este servicio:
  - asignaciones.py ejecutaba todo dentro de engine.begin() con SQL crudo
  - La lógica de "obtener o crear conductor" estaba inline en el router
  - No había forma de testear el flujo sin una DB real
  - El manejo de errores era un except Exception genérico que ocultaba el origen

Ahora cada paso tiene un responsable claro y el servicio puede
testearse con mocks de los tres repositorios.
"""

from fastapi import HTTPException
from sqlalchemy.orm import Session

from domain.asignacion.repository import AsignacionRepositoryProtocol
from domain.asignacion.schema import AsignacionCreate, AsignacionCreatedOut
from domain.conductor.repository import ConductorRepositoryProtocol
from domain.territorio.repository import TerritorioRepositoryProtocol


class AsignacionService:
    """
    Orquesta la creación de asignaciones coordinando los tres dominios.

    Depende de los tres protocolos (no de implementaciones concretas).
    La Session se inyecta para que el servicio controle el commit/rollback
    sin que los repositorios necesiten conocerse entre sí.
    """

    def __init__(
        self,
        db: Session,
        asignacion_repo: AsignacionRepositoryProtocol,
        territorio_repo: TerritorioRepositoryProtocol,
        conductor_repo: ConductorRepositoryProtocol,
    ) -> None:
        self.db = db
        self.asignacion_repo = asignacion_repo
        self.territorio_repo = territorio_repo
        self.conductor_repo = conductor_repo

    def crear_asignacion(
        self, data: AsignacionCreate
    ) -> AsignacionCreatedOut:
        """
        Crea una asignación completa de forma atómica.

        Raises:
            HTTPException 404: si el territorio no existe en la DB.
            HTTPException 500: si falla la transacción (reraise con contexto).
        """
        try:
            # ── Paso 1: verificar territorio ─────────────────────────────────
            territorio = self.territorio_repo.obtener_por_numero(
                data.numero_territorio
            )
            if not territorio:
                raise HTTPException(
                    status_code=404,
                    detail=f"Territorio {data.numero_territorio} no encontrado",
                )

            # ── Paso 2: obtener o crear conductor ────────────────────────────
            # Regla de negocio: si el conductor no existe se crea automáticamente.
            # El repositorio hace flush() interno, pero el commit es nuestro.
            conductor, conductor_creado = self.conductor_repo.obtener_o_crear(
                data.conductor
            )

            # ── Paso 3: insertar asignación ──────────────────────────────────
            asignacion = self.asignacion_repo.crear(
                territorio_id=territorio.id,
                conductor_id=conductor.id,
                fecha_asignado=data.fecha_asignado,
                fecha_completado=data.fecha_completado,
                cantidad_abarcado=data.cantidad_abarcado,
            )

            # ── Paso 4: confirmar toda la transacción ────────────────────────
            # Un único commit para los tres pasos → atómico.
            # Si algo falló arriba, el except hace rollback y nada persiste.
            self.db.commit()

        except HTTPException:
            self.db.rollback()
            raise

        except Exception as e:
            self.db.rollback()
            raise HTTPException(
                status_code=500,
                detail=f"Error al crear la asignación: {str(e)}",
            ) from e

        return AsignacionCreatedOut(
            message="Asignación creada correctamente",
            asignacion_id=asignacion.id,
            conductor_creado=conductor_creado,
        )