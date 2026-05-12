from pydantic import BaseModel

class PlanillaBase(BaseModel):
    zona: int
    ciclo: int
    nombre_planilla: str
    anio: int

class PlanillaCreate(PlanillaBase):
    """Para crear una nueva (aunque el Trigger ya lo hace)"""
    pass

class PlanillaOut(PlanillaBase):
    """Lo que devuelve la API"""
    id: int

    class Config:
        from_attributes = True