import os
from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    # URL de la base de datos (obligatorio)
    DATABASE_URL: str = Field(...)

    class Config:
        # En desarrollo, busca el .env en la raíz del proyecto
        env_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
        env_file_encoding = "utf-8"
        extra = "ignore"

# Instancia global para usar en todo el backend
settings = Settings()
