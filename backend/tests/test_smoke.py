import os

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine

from app.main import app


def test_app_starts() -> None:
    with TestClient(app) as client:
        assert client.get("/").status_code == 404


async def test_test_database_works(test_engine: AsyncEngine) -> None:
    async with test_engine.connect() as connection:
        assert await connection.scalar(text("SELECT 1")) == 1


def test_test_database_is_separate_from_the_application_database() -> None:
    test_database_url = os.environ["TEST_DATABASE_URL"]
    application_database_url = os.environ["DATABASE_URL"]
    assert (
        make_url(test_database_url).database
        != make_url(application_database_url).database
    )
