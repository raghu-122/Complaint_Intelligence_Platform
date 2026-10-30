"""
Pytest configuration and shared fixtures.
"""
from __future__ import annotations

import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from app.config import get_settings
from app.database import Base, get_db
from app.main import app
from app.generator.orchestrator import DataGenerator
from app.generator.loader import load_all

# Use in-memory SQLite with StaticPool for thread-safe test isolation
TEST_DATABASE_URL = "sqlite:///:memory:"

test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="session", autouse=True)
def isolate_test_data(tmp_path_factory):
    """Keep generated anomaly and export files outside the repository data directory."""
    settings = get_settings()
    original_data_dir = settings.data_dir
    settings.data_dir = tmp_path_factory.mktemp("yottaflex-test-data")
    yield
    settings.data_dir = original_data_dir


@pytest.fixture(scope="session", autouse=True)
def setup_test_db(isolate_test_data):
    """Create all tables in memory once for the test session."""
    from app.models import (  # noqa: F401
        customer, product, order, complaint, message,
        category, priority_rule, assignment, sla, resolution, survey,
        agent, team, generation_run
    )
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def db_session():
    """Provide a clean database session per test with rolled back transaction."""
    connection = test_engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture(scope="session")
def seeded_db(setup_test_db):
    """Generate and load standard starter dataset into in-memory DB for read-only tests."""
    with TestingSessionLocal() as session:
        generator = DataGenerator(seed=20261022, scale="starter")
        data = generator.generate_all()
        load_all(session, data, clear_first=True)
    return test_engine


@pytest.fixture
def client(seeded_db):
    """FastAPI TestClient with overridden get_db dependency pointing to seeded test db."""
    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
