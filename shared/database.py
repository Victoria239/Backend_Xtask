from typing import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from shared.config import get_settings

# ─── Schema names per service ─────────────────────────────────────
SERVICE_SCHEMAS: dict[str, str] = {
    "auth": "svc_auth",
    "projects": "svc_projects",
    "employees": "svc_employees",
    "finance": "svc_finance",
    "payroll": "svc_payroll",
    "kpis": "svc_kpis",
    "skills": "svc_skills",
    "dashboard": "svc_dashboard",
}


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""
    pass


# ─── Per-service database factory ─────────────────────────────────
_engines: dict[str, object] = {}
_sessions: dict[str, async_sessionmaker] = {}


def _get_engine(service_name: str):
    """Get or create an async engine for a service."""
    if service_name not in _engines:
        settings = get_settings()
        url = settings.get_service_database_url(service_name)
        schema = SERVICE_SCHEMAS.get(service_name, "public")
        eng = create_async_engine(
            url,
            echo=settings.is_development,
            pool_size=20,
            max_overflow=10,
            pool_pre_ping=True,
            connect_args={"server_settings": {"search_path": f"{schema},public"}},
        )
        _engines[service_name] = eng
    return _engines[service_name]


def _get_session_factory(service_name: str) -> async_sessionmaker:
    """Get or create an async session factory for a service."""
    if service_name not in _sessions:
        eng = _get_engine(service_name)
        _sessions[service_name] = async_sessionmaker(
            eng, class_=AsyncSession, expire_on_commit=False,
        )
    return _sessions[service_name]


def get_service_db(service_name: str):
    """Create a FastAPI dependency that provides a DB session for a specific service."""
    async def _dependency() -> AsyncGenerator[AsyncSession, None]:
        factory = _get_session_factory(service_name)
        async with factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()
    _dependency.__qualname__ = f"get_db_{service_name}"
    return _dependency


# ─── Default engine/session (gateway monolith mode — all schemas) ─
settings = get_settings()

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.is_development,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
)

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Default dependency — used by gateway monolith mode (all schemas visible)."""
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Create schemas if they don't exist. Used for development only."""
    async with engine.begin() as conn:
        for schema_name in SERVICE_SCHEMAS.values():
            await conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema_name}"))
        await conn.commit()
