"""
Synchronous DB fixtures for S1 model tests.

Uses psycopg2 (sync) so tests stay simple and free of asyncio complexity.
DATABASE_URL from environment; asyncpg scheme is swapped for psycopg2.

Each test gets a fresh transaction that is rolled back on teardown,
leaving the DB clean without truncating tables.
"""
import os
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Importing the models package registers all classes with Base.metadata.
import app.models  # noqa: F401
from app.database import Base


def _sync_url() -> str:
    url = os.environ["DATABASE_URL"]
    return url.replace("postgresql+asyncpg://", "postgresql+psycopg2://").replace(
        "postgresql://", "postgresql+psycopg2://"
    )


@pytest.fixture(scope="session")
def engine():
    eng = create_engine(_sync_url(), echo=False)
    yield eng
    eng.dispose()


@pytest.fixture
def session(engine):
    connection = engine.connect()
    transaction = connection.begin()
    Session = sessionmaker(bind=connection)
    sess = Session()
    yield sess
    sess.close()
    transaction.rollback()
    connection.close()
