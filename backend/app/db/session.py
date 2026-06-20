from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from backend.app.core.config import get_settings


def create_database_engine(database_url: str | None = None) -> Engine:
    settings = get_settings()
    return create_engine(database_url or settings.database_url, pool_pre_ping=True)

