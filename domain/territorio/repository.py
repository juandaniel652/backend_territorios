"""
domain/territorio/repository.py

Patrón Repository + Inversión de Dependencia.

Estructura:
  1. TerritorioRepositoryProtocol — interfaz (typing.Protocol)
     Define el contrato que cualquier implementación debe cumplir.
     Los servicios dependen de este protocolo, nunca de la implementación concreta.

  2. TerritorioRepository — implementación real con SQLAlchemy ORM
     Todo el SQL del dominio territorio vive aquí.
     Reemplaza:
       - La query inline de app.py (GET /territorios/{numero})
       - La query inline de sugerir_territorios.py
       - querys_territorios.py completo

Ventaja de testing:
  En tests se pasa un MockTerritorioRepository que implementa el mismo protocolo
  sin tocar la DB real. El servicio no nota la diferencia.
"""
from sqlalchemy import or_
from typing import Protocol, runtime_checkable
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime, timedelta, date

from domain.territorio.model import Territorio
from domain.territorio.schema import AsignacionDeTerritorioOut, SugerenciaTerritorio


# ─────────────────────────────────────────────
# 1. Protocolo (interfaz para DI)
# ─────────────────────────────────────────────

@runtime_checkable
class TerritorioRepositoryProtocol(Protocol):

    def obtener_por_numero(self, numero: int) -> Territorio | None:
        """Devuelve un Territorio por su número público, o None si no existe."""
        ...

    def obtener_por_id(self, territorio_id: int) -> Territorio | None:
        """Devuelve un Territorio por su PK interna."""
        ...

    def obtener_asignaciones_historial(
        self, numero: int
    ) -> list[AsignacionDeTerritorioOut]:
        """
        Devuelve el historial de asignaciones de un territorio ordenado
        cronológicamente. Listo para serializar directo al cliente.
        """
        ...

    def obtener_sugerencias(
        self, desde: int, hasta: int, limit: int
    ) -> list[SugerenciaTerritorio]:
        """
        Devuelve territorios del rango ordenados por fecha de última
        asignación ascendente (los más atrasados primero).
        """
        ...


# ─────────────────────────────────────────────
# 2. Implementación SQLAlchemy
# ─────────────────────────────────────────────

class TerritorioRepository:
    """
    Implementación concreta del repositorio de territorios.
    Recibe la Session como argumento → no crea conexiones propias (DI).
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def obtener_por_numero(self, numero: int) -> Territorio | None:
        return (
            self.db.query(Territorio)
            .filter(Territorio.numero == numero)
            .first()
        )

    def obtener_por_id(self, territorio_id: int) -> Territorio | None:
        return self.db.get(Territorio, territorio_id)

    def obtener_asignaciones_historial(
        self, numero: int
    ) -> list[AsignacionDeTerritorioOut]:
        """
        Query con JOIN hacia Asignaciones y Conductores.
        Reemplaza el SQL inline que vivía en app.py y querys_territorios.py.
        Ordenamiento cronológico resuelto en SQL, no en Python.
        """
        sql = text("""
            SELECT
                a.id,
                c.nombre_completo  AS conductor,
                a.fecha_asignado,
                a.fecha_completado,
                a.cantidad_abarcado
            FROM asignaciones a
            JOIN territorios t  ON a.territorio_id = t.id
            JOIN conductores c  ON a.conductor_id  = c.id
            WHERE t.numero = :numero
            ORDER BY a.fecha_asignado ASC NULLS LAST
        """)

        rows = self.db.execute(sql, {"numero": numero}).mappings().all()

        return [AsignacionDeTerritorioOut(**row) for row in rows]

    # Dentro de TerritorioRepository en domain/territorio/repository.py

    def obtener_sugerencias(self, desde: int, hasta: int, limit: int) -> list[SugerenciaTerritorio]:
        # Usamos COALESCE para que si la fecha es NULL (nunca se hizo), 
        # se comporte como una fecha muy vieja.
        sql = text("""
            SELECT
                numero,
                ultima_fecha_completado AS ultima_fecha
            FROM territorios
            WHERE numero BETWEEN :desde AND :hasta
            ORDER BY 
                ultima_fecha_completado ASC NULLS FIRST
            LIMIT :limit
        """)
    
        rows = self.db.execute(
            sql, {"desde": desde, "hasta": hasta, "limit": limit}
        ).mappings().all()
    
        return [
            SugerenciaTerritorio(
                numero=row["numero"],
                ultima_fecha=row["ultima_fecha"],
                dias_atraso=None,
                severidad="",
            )
            for row in rows
        ]
        
    # En backend/domain/territorio/repository.py
    def obtener_todos_con_metadata(self):
        # Traemos todos los territorios ordenados por número o como prefieras
        return self.db.query(Territorio).all()
    
    def obtener_sugerencias_antiguedad(self, desde: int, hasta: int, limit: int = 10):
        sql = text("""
            SELECT 
                id, numero, zona, 
                ultima_fecha_completado, -- Asegurate que el nombre sea exacto
                COALESCE(CURRENT_DATE - ultima_fecha_completado, 999) as dias_atraso,
                CASE 
                    WHEN ultima_fecha_completado IS NULL THEN 'critico'
                    WHEN (CURRENT_DATE - ultima_fecha_completado) > 120 THEN 'critico'
                    WHEN (CURRENT_DATE - ultima_fecha_completado) > 60 THEN 'severo'
                    ELSE 'normal'
                END as severidad
            FROM territorios
            WHERE numero BETWEEN :desde AND :hasta
            ORDER BY dias_atraso DESC, numero ASC
            LIMIT :limit
        """)
        
        # IMPORTANTE: .mappings().all() es vital para que devuelva diccionarios
        result = self.db.execute(sql, {"desde": desde, "hasta": hasta, "limit": limit}).mappings().all()
        
        # Convertimos a una lista de dicts limpia para evitar errores de serialización
        lista = []
        for r in result:
            lista.append({
                "id": r["id"],
                "numero": r["numero"],
                "zona": r["zona"],
                "ultima_visita": str(r["ultima_fecha_completado"]) if r["ultima_fecha_completado"] else "Nunca",
                "dias_atraso": r["dias_atraso"],
                "severidad": r["severidad"]
            })
        return lista