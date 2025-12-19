from sqlalchemy import create_engine
from backend.settings import settings

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
)