"""
Database engine, session factory, and base model.
"""
from __future__ import annotations

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session
from typing import Generator

from app.config import get_settings


def _get_engine():
    settings = get_settings()
    engine = create_engine(
        settings.database_url,
        echo=settings.database_echo,
        connect_args={"check_same_thread": False} if "sqlite" in settings.database_url else {},
    )

    # Enable SQLite foreign key enforcement
    if "sqlite" in settings.database_url:
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
    from app.models import (  # noqa: F401 - import to register models
        customer, product, order, complaint, message,
        category, priority_rule, assignment, sla, resolution, survey,
        agent, team, generation_run
    )
    Base.metadata.create_all(bind=engine)


def drop_db() -> None:
    """Drop all tables - use with caution."""
    Base.metadata.drop_all(bind=engine)
