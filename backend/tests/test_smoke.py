from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.config import Settings, settings
from app.main import app


def test_settings_load() -> None:
    loaded_settings = Settings()  # pyright: ignore[reportCallIssue]
    assert loaded_settings.database_url
    assert loaded_settings.cors_origins
    assert settings.currency


def test_app_starts() -> None:
    with TestClient(app) as client:
        assert client.get("/").status_code == 404


async def test_test_database_works(test_engine: AsyncEngine) -> None:
    async with test_engine.connect() as connection:
        assert await connection.scalar(text("SELECT 1")) == 1
