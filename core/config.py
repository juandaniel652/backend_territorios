"""
core/config.py

Fuente única de verdad para toda la configuración de la app.
Reemplaza settings.py y elimina SECRET_KEY hardcodeada en auth.py.

Patrón: Settings como singleton inyectable → facilita testing (override en tests).
"""

import os
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # --- Base de datos ---
    DATABASE_URL: str = Field(..., description="PostgreSQL connection string")

    # --- Seguridad JWT ---
    SECRET_KEY: str = Field(..., description="Clave secreta para firmar JWT")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # --- App ---
    ENVIRONMENT: str = Field(default="development")  # development | production
    ALLOWED_ORIGINS: list[str] = Field(
        default=[
            "http://127.0.0.1:5500",
            "http://localhost:5500",
            "http://127.0.0.1:5501",
            "http://localhost:5501",
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "https://territorios-front-end.vercel.app",
        ]
    )

    class Config:
        env_file = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), ".env"
        )
        env_file_encoding = "utf-8"
        extra = "ignore"


# Singleton — se importa desde cualquier capa sin re-instanciar
settings = Settings()