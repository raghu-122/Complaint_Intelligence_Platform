"""
Database engine, session factory, and base model.
"""
from __future__ import annotations

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session
from typing import Generator

from app.config import get_settings


def _normalize_database_url(url: str) -> str:
    """Normalize database URL for SQLAlchemy (Render and others use postgres:// by default)."""
    if url.startswith("postgres://"):
        return "postgresql://" + url[len("postgres://"):]
    return url


def _get_engine():
    settings = get_settings()
    db_url = _normalize_database_url(settings.database_url)
    is_sqlite = "sqlite" in db_url

    engine_kwargs = {
        "echo": settings.database_echo,
        "pool_pre_ping": True,
    }

    if is_sqlite:
        engine_kwargs["connect_args"] = {"check_same_thread": False}
    else:
        # PostgreSQL connection pool tuning for production managed databases (Render free/starter)
        # Keeps max connections at 15 per worker, avoiding slot exhaustion
        engine_kwargs["pool_size"] = 5
        engine_kwargs["max_overflow"] = 10
        engine_kwargs["pool_timeout"] = 30
        engine_kwargs["pool_recycle"] = 1800

    engine = create_engine(db_url, **engine_kwargs)

    # Enable SQLite foreign key enforcement
    if is_sqlite:
        @event.listens_for(engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.close()

    return engine


engine = _get_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency for database sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create all tables."""
    import app.models  # noqa: F401 - import to register models
    Base.metadata.create_all(bind=engine)


def drop_db() -> None:
    """Drop all tables - use with caution."""
    Base.metadata.drop_all(bind=engine)
