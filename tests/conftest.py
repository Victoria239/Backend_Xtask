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
    """Async test client that hits the running ASGI app via the live server."""
    async with AsyncClient(base_url="http://localhost:8000") as c:
        yield c
