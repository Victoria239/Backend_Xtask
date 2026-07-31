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
    "tenants": "svc_tenants",
    "rag": "svc_rag",
    "ai_assistant": "svc_ai",
    "notifications": "svc_notifications",
    "onboarding": "svc_onboarding",
    "docgen": "svc_docgen",
    "okrs": "svc_okrs",
    "contracts": "svc_contracts",
    "plans": "svc_plans",
    "leaves": "svc_leaves",
    "ats": "svc_ats",
    "payouts": "svc_payouts",
    "approvals": "svc_approvals",
    "predictions": "svc_predictions",
    "reviews": "svc_reviews",
    "tasks": "svc_tasks",
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
    """Bootstrap the dev database.

    1. Create per-service schemas.
    2. Enable pgvector (required by RAG models).
    3. Import all model modules so their tables get registered against ``Base``.
    4. ``create_all`` to materialise every table. Idempotent — safe on hot reload.

    All steps are wrapped in defensive try/except because multiple service
    containers race to initialise the same DB on first startup.
    """

    # Step 1+2: schemas + extension. Each in its own transaction so a failure
    # in one doesn't poison the rest.
    for schema_name in SERVICE_SCHEMAS.values():
        try:
            async with engine.begin() as conn:
                await conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema_name}"))
        except Exception:  # noqa: BLE001
            pass
    try:
        async with engine.begin() as conn:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    except Exception:  # noqa: BLE001
        pass

    # Step 3: import models so Base.metadata is populated.
    from services.auth import models as _auth  # noqa: F401
    from services.projects import models as _proj  # noqa: F401
    from services.employees import models as _emp  # noqa: F401
    from services.finance import models as _fin  # noqa: F401
    from services.payroll import models as _pay  # noqa: F401
    from services.kpis import models as _kpi  # noqa: F401
    from services.skills import models as _skl  # noqa: F401
    from services.dashboard import models as _dsh  # noqa: F401
    from services.tenants import models as _tnt  # noqa: F401
    from services.rag import models as _rag  # noqa: F401
    from services.ai_assistant import models as _ai  # noqa: F401
    from services.notifications import models as _notif  # noqa: F401
    from services.onboarding import models as _onb  # noqa: F401
    from services.docgen import models as _dg  # noqa: F401
    from services.okrs import models as _okrs  # noqa: F401
    from services.contracts import models as _ctr  # noqa: F401
    from services.plans import models as _pln  # noqa: F401
    from services.leaves import models as _lvs  # noqa: F401
    from services.ats import models as _ats  # noqa: F401
    from services.payouts import models as _pay  # noqa: F401
    from services.approvals import models as _appr  # noqa: F401
    from services.reviews import models as _rvw  # noqa: F401
    from services.tasks import models as _tasks  # noqa: F401

    # Step 4: create all tables.
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    except Exception:  # noqa: BLE001
        # Another container likely created them first; let the next health
        # check confirm everything is in place.
        pass
