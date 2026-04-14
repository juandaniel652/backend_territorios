"""
domain/conductor/repository.py

Patrón Repository + DI para el dominio Conductor.

Responsabilidad clave de este repo:
  obtener_o_crear() — operación usada por AsignacionService al registrar
  una asignación nueva. Si el conductor ya existe lo retorna, si no lo crea.
  Esto reemplaza el bloque IF/ELSE inline que vivía en asignaciones.py original.

El método es parte del repositorio (acceso a datos) y no del servicio
porque es una decisión de persistencia: "¿existe este registro? si no, insertalo".
La regla de negocio ("un conductor se crea automáticamente si no existe")
vive en el servicio que llama a este método.
"""

from typing import Protocol, runtime_checkable
from sqlalchemy.orm import Session

from domain.conductor.model import Conductor


# ─────────────────────────────────────────────
# 1. Protocolo (interfaz para DI)
# ─────────────────────────────────────────────

@runtime_checkable
class ConductorRepositoryProtocol(Protocol):

    def obtener_por_nombre(self, nombre: str) -> Conductor | None:
        """Busca un conductor por nombre completo exacto."""
        ...

    def obtener_por_id(self, conductor_id: int) -> Conductor | None:
        """Busca un conductor por su PK."""
        ...

    def crear(self, nombre: str) -> Conductor:
        """Inserta un nuevo conductor y lo retorna con su id asignado."""
        ...

    def obtener_o_crear(self, nombre: str) -> tuple[Conductor, bool]:
        """
        Retorna (conductor, created).
        created=True si fue insertado en esta llamada.
        Operación atómica dentro de la sesión activa.
        """
        ...


# ─────────────────────────────────────────────
# 2. Implementación SQLAlchemy
# ─────────────────────────────────────────────

class ConductorRepository:
    """
    Implementación concreta del repositorio de conductores.
    Recibe Session como argumento → sin conexiones propias (DI).
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def obtener_por_nombre(self, nombre: str) -> Conductor | None:
        return (
            self.db.query(Conductor)
            .filter(Conductor.nombre_completo == nombre)
            .first()
        )

    def obtener_por_id(self, conductor_id: int) -> Conductor | None:
        return self.db.get(Conductor, conductor_id)

    def crear(self, nombre: str) -> Conductor:
        conductor = Conductor(nombre_completo=nombre)
        self.db.add(conductor)
        self.db.flush()   # obtiene el id sin cerrar la transacción
        return conductor

    def obtener_o_crear(self, nombre: str) -> tuple[Conductor, bool]:
        """
        Reemplaza el bloque IF/ELSE inline de asignaciones.py original:

            conductor = conn.execute(SELECT id FROM Conductores WHERE ...)
            if conductor:
                conductor_id = conductor[0]
            else:
                result = conn.execute(INSERT INTO Conductores ...)
                conductor_id = result.fetchone()[0]

        Ahora es un método reutilizable, testeable y con nombre semántico.
        """
        existente = self.obtener_por_nombre(nombre)
        if existente:
            return existente, False

        nuevo = self.crear(nombre)
        return nuevo, True
    
    def obtener_todos_los_nombres(self) -> list[str]:
        return [c.nombre_completo for c in self.db.query(Conductor.nombre_completo).all()]