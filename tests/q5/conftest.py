"""Conftest local para tests Q5.

Solución al problema del engine cacheado vs event loop por test:
proveemos una factory de sesiones fresh-engine-per-test que cada test
puede usar en lugar del `async_session` global de shared.database.
"""
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from shared.config import get_settings


@pytest_asyncio.fixture
async def fresh_session():
    """Engine + session nueva para este test, vinculada al loop actual."""
    settings = get_settings()
    engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as s:
        yield s
    await engine.dispose()
