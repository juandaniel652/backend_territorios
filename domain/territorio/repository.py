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
        
    def actualizar_fecha_terminado(self, territorio_id: int, fecha: date) -> None:
        """
        Actualiza el campo ultima_fecha_completado en la tabla territorios.
        Esto asegura que las sugerencias por antigüedad funcionen al instante.
        """
        territorio = self.obtener_por_id(territorio_id)
        if territorio:
            territorio.ultima_fecha_completado = fecha


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
        # Esta query une la fecha estática de la tabla territorios 
        # con la fecha más nueva de la tabla asignaciones
        sql = text("""
            WITH UltimaAsignacionPorTerritorio AS (
                SELECT territorio_id, MAX(fecha_completado) as fecha_max
                FROM asignaciones
                GROUP BY territorio_id
            )
            SELECT 
                t.id, 
                t.numero, 
                t.zona,
                -- Elegimos la mayor entre la fecha vieja y la del historial
                GREATEST(
                    COALESCE(t.ultima_fecha_completado, '1900-01-01'), 
                    COALESCE(ua.fecha_max, '1900-01-01')
                ) as fecha_final
            FROM territorios t
            LEFT JOIN UltimaAsignacionPorTerritorio ua ON t.id = ua.territorio_id
            WHERE t.numero BETWEEN :desde AND :hasta
            ORDER BY 
                -- Los que tienen NULL o '1900-01-01' (nunca hechos) van primero
                fecha_final ASC, 
                t.numero ASC
            LIMIT :limit
        """)
        
        result = self.db.execute(sql, {"desde": desde, "hasta": hasta, "limit": limit}).mappings().all()
        
        # Procesamos los resultados para calcular los días de atraso en Python
        from datetime import date
        hoy = date.today()
        sugerencias = []
    
        for r in result:
            fecha_f = r["fecha_final"]
            if fecha_f == date(1900, 1, 1):
                ultima_visita = "Nunca"
                dias_atraso = 999
                severidad = "critico"
            else:
                ultima_visita = str(fecha_f)
                dias_atraso = (hoy - fecha_f).days
                if dias_atraso > 120: severidad = "critico"
                elif dias_atraso > 60: severidad = "severo"
                else: severidad = "normal"
    
            sugerencias.append({
                "id": r["id"],
                "numero": r["numero"],
                "zona": r["zona"],
                "ultima_visita": ultima_visita,
                "dias_atraso": dias_atraso,
                "severidad": severidad
            })
        
        # Re-ordenamos por días de atraso (más días arriba)
        return sorted(sugerencias, key=lambda x: x['dias_atraso'], reverse=True)
    
    def obtener_sugerencias_por_dia(self, es_sabado: bool, limit: int = 10):
        # Regla: Sábado AM habilita Z3 y Z2 crítica. Semana las prohíbe.
        if es_sabado:
            filtro = "(t.numero BETWEEN 42 AND 60 OR t.numero IN (28, 29, 30, 31))"
        else:
            filtro = "(t.numero NOT BETWEEN 42 AND 60 AND t.numero NOT IN (28, 29, 30, 31))"

        sql = text(f"""
            WITH UltimaAsignacion AS (
                SELECT territorio_id, MAX(fecha_completado) as fecha_max
                FROM asignaciones
                GROUP BY territorio_id
            )
            SELECT 
                t.id, 
                t.numero, 
                t.zona,
                COALESCE(ua.fecha_max, t.ultima_fecha_completado) as ultima_fecha
            FROM territorios t
            LEFT JOIN UltimaAsignacion ua ON t.id = ua.territorio_id
            WHERE {filtro}
            ORDER BY ultima_fecha ASC NULLS FIRST
            LIMIT :limit
        """)
        
        return self.db.execute(sql, {"limit": limit}).mappings().all()
    
    
    def actualizar_fecha_terminado(self, territorio_id: int, fecha: date) -> None:
        """
        Actualiza el campo ultima_fecha_completado en la tabla territorios.
        Esto asegura que las sugerencias por antigüedad funcionen al instante.
        """
        territorio = self.obtener_por_id(territorio_id)
        if territorio:
            territorio.ultima_fecha_completado = fecha