from collections.abc import Generator
from pathlib import Path
import os
import tempfile

# Override before importing app/settings/session: never touch the configured personal DB.
_TEST_ROOT = tempfile.TemporaryDirectory(prefix="pc-synthetic-")
os.environ["DATABASE_URL"] = f"sqlite:///{Path(_TEST_ROOT.name) / 'calendar-tests.sqlite'}"
os.environ["APP_ENV"] = "test"
os.environ["AUTH_USERNAME"] = "synthetic-legacy"
os.environ["AUTH_PASSWORD"] = "synthetic-password"
os.environ["AUTH_SESSION_SECRET"] = "synthetic-test-session-secret"
os.environ["LEGACY_AUTH_ENABLED"] = "true"
os.environ["LEGACY_PRINCIPAL_ID"] = "synthetic-legacy"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

# Ensure backend root is importable and .env is found
BACKEND_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session", autouse=True)
def synthetic_schema():
    from app.infrastructure.db.session import Base, engine
    from app.infrastructure.db import models  # noqa: F401
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture(scope="session")
def settings():
    from app.core.config import get_settings

    get_settings.cache_clear()
    return get_settings()


@pytest.fixture(scope="session")
def client(settings) -> Generator[TestClient, None, None]:
    from app.main import create_app

    # Reload settings after .env may include auth (cache was primed at import time).
    from app.core.config import get_settings

    get_settings.cache_clear()
    settings = get_settings()

    app = create_app()
    with TestClient(app) as test_client:
        if settings.auth_username and settings.auth_password and settings.auth_session_secret:
            logged_in = test_client.post(
                "/api/auth/login",
                json={"username": settings.auth_username, "password": settings.auth_password},
            )
            assert logged_in.status_code == 200, logged_in.text
        yield test_client


@pytest.fixture(scope="session")
def db_engine(settings):
    engine = create_engine(settings.database_url, pool_pre_ping=True, future=True)
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    yield engine
    engine.dispose()


@pytest.fixture()
def db_session() -> Generator[Session, None, None]:
    from app.infrastructure.db.session import engine

    connection = engine.connect()
    transaction = connection.begin()
    if connection.dialect.name == 'sqlite':
        connection.exec_driver_sql('BEGIN')
    SessionLocal = sessionmaker(bind=connection, autoflush=False, autocommit=False, future=True)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        if transaction.is_active:
            transaction.rollback()
        connection.close()


@pytest.fixture()
def repos(db_session: Session):
    from app.infrastructure.repositories import Repositories

    return Repositories(db_session)
