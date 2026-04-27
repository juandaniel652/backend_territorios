# backend/domain/salida/repository.py
from sqlalchemy.orm import Session
from domain.salida.model import Salida

class SalidaRepository:
    def __init__(self, db: Session):
        self.db = db

    def crear_muchos(self, salidas):
        self.db.add_all(salidas)
        self.db.flush()
        
    def listar(self):
        # Mejoramos el ordenamiento aquí también por consistencia
        return self.db.query(Salida).order_by(Salida.fecha.asc(), Salida.turno.asc()).all()
    
    def eliminar(self, salida_id: int):
        salida = self.db.get(Salida, salida_id)
        if salida:
            self.db.delete(salida)
            self.db.flush()