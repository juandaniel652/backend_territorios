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
    
    def obtener_zona_de_territorio(self, numero: int) -> int | None:
        """Busca el territorio por su número y devuelve el valor numérico de su zona."""
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

    def obtener_sugerencias(self, desde: int, hasta: int, limit: int) -> list[SugerenciaTerritorio]:
        # Modificamos la query para calcular la última fecha buscando el MAX(fecha_completado) del historial
        sql = text("""
            SELECT
                t.numero,
                MAX(a.fecha_completado) AS ultima_fecha
            FROM territorios t
            LEFT JOIN asignaciones a ON t.id = a.territorio_id
            WHERE t.numero BETWEEN :desde AND :hasta
            GROUP BY t.id, t.numero
            ORDER BY ultima_fecha ASC NULLS FIRST
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
        
    def obtener_todos_con_metadata(self):
        # Traemos todos los territorios ordenados por número o como prefieras
        return self.db.query(Territorio).all()
    
    def obtener_sugerencias_antiguedad(self, desde: int, hasta: int, limit: int = 10):
        # La query ahora es mucho más simple y elegante
        sql = text("""
            SELECT 
                t.id, 
                t.numero, 
                t.zona,
                MAX(a.fecha_completado) as fecha_final
            FROM territorios t
            LEFT JOIN asignaciones a ON t.id = a.territorio_id
            WHERE t.numero BETWEEN :desde AND :hasta
            GROUP BY t.id, t.numero, t.zona
            ORDER BY 
                fecha_final ASC NULLS FIRST, 
                t.numero ASC
            LIMIT :limit
        """)
        
        result = self.db.execute(sql, {"desde": desde, "hasta": hasta, "limit": limit}).mappings().all()
        
        from datetime import date
        hoy = date.today()
        sugerencias = []
    
        for r in result:
            fecha_f = r["fecha_final"]
            if fecha_f is None:  # Si nunca tuvo una asignación completada en el historial
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
    
    def obtener_estado_detallado(self, numero: int):
        query = """
            SELECT 
                total_completados AS total_salidas, 
                ciclo_actual,
                proxima_fila,
                zona  -- <--- Ahora el repo lee la zona de la vista
            FROM vista_estado_territorios
            WHERE territorio = :num
        """
        result = self.db.execute(text(query), {"num": numero}).mappings().first()
        return result
    
    def obtener_zona_de_territorio(self, numero: int) -> int | None:
        """
        Busca la zona directa desde la tabla territorios utilizando el número público.
        """
        sql = text("SELECT zona FROM territorios WHERE numero = :numero")
        row = self.db.execute(sql, {"numero": numero}).mappings().first()
        return row["zona"] if row else None
    

    # --- NUEVOS MÉTODOS PARA EL REPORTE SEMANAL ---

    def obtener_todas_las_fechas_asignadas(self) -> list[date]:
        """Obtiene todas las fechas de asignación únicas ordenadas de forma descendente."""
        # Evitamos importar Asignacion arriba si genera ciclos; lo importamos localmente
        from domain.asignacion.model import Asignacion

        result = (
            self.db.query(Asignacion.fecha_asignado)
            .filter(Asignacion.fecha_asignado != None)
            .distinct()
            .order_by(Asignacion.fecha_asignado.desc())
            .all()
        )
        return [row[0] for row in result]

    def obtener_reporte_por_rango(self, fecha_inicio: date, fecha_fin: date) -> list[dict]:
        """Realiza el JOIN para obtener territorios, conductores y detalles en el rango."""
        from domain.asignacion.model import Asignacion
        from domain.conductor.model import Conductor
        from domain.territorio.model import Territorio

        results = (
            self.db.query(
                Territorio.numero.label("territorio_numero"),
                Territorio.zona.label("zona"),
                Conductor.nombre_completo.label("conductor_nombre"),
                Asignacion.fecha_asignado.label("fecha_asignado"),
                Asignacion.fecha_completado.label("fecha_completado"),
                Asignacion.cantidad_abarcado.label("cantidad_abarcado")
            )
            .join(Asignacion, Asignacion.territorio_id == Territorio.id)
            .outerjoin(Conductor, Asignacion.conductor_id == Conductor.id)
            .filter(
                Asignacion.fecha_asignado >= fecha_inicio,
                Asignacion.fecha_asignado <= fecha_fin
            )
            .order_by(Territorio.numero.asc())
            .all()
        )

        return [
            {
                "territorio_numero": r.territorio_numero,
                "zona": r.zona,
                "conductor_nombre": r.conductor_nombre,
                "fecha_asignado": r.fecha_asignado,
                "fecha_completado": r.fecha_completado,
                "cantidad_abarcado": r.cantidad_abarcado
            }
            for r in results
        ]