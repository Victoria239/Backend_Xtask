"""Shared test fixtures."""

import pytest
from jose import jwt
from httpx import ASGITransport, AsyncClient

from gateway.main import app
from shared.config import get_settings

settings = get_settings()

ADMIN_TOKEN = jwt.encode(
    {"sub": "1", "username": "admin", "role": "admin", "exp": 9999999999},
    settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM,
)
MANAGER_TOKEN = jwt.encode(
    {"sub": "2", "username": "manager", "role": "manager", "exp": 9999999999},
    settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM,
)
USER_TOKEN = jwt.encode(
    {"sub": "3", "username": "user", "role": "user", "exp": 9999999999},
    settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM,
)


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_headers():
    return auth_header(ADMIN_TOKEN)


@pytest.fixture
def manager_headers():
    return auth_header(MANAGER_TOKEN)


@pytest.fixture
def user_headers():
    return auth_header(USER_TOKEN)


@pytest.fixture
async def client():
    """Async test client que apunta al gateway running.

    Si los tests corren dentro del docker network (via scripts/run_tests.sh),
    gateway se resuelve por hostname. Desde el host shell directo, el usuario
    puede sobreescribir con GATEWAY_URL=http://localhost:8001.
    """
    import os
    base_url = os.getenv("GATEWAY_URL", "http://gateway:8000")
    async with AsyncClient(base_url=base_url) as c:
        yield c
