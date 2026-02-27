"""Shared FastAPI dependencies used across services."""

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from shared.config import Settings, get_settings
from shared.database import get_db
from shared.exceptions import UnauthorizedException

security = HTTPBearer(auto_error=False)


async def get_current_user_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    settings: Settings = Depends(get_settings),
) -> int:
    """Extract and validate user ID from JWT token."""
    if credentials is None:
        raise UnauthorizedException("Missing authentication token")

    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
        )
        user_id: int | None = payload.get("sub")
        if user_id is None:
            raise UnauthorizedException("Invalid token payload")
        return int(user_id)
    except JWTError:
        raise UnauthorizedException("Invalid or expired token")


async def get_optional_user_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    settings: Settings = Depends(get_settings),
) -> int | None:
    """Extract user ID from JWT token, or return None if not authenticated."""
    if credentials is None:
        return None

    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
        )
        user_id = payload.get("sub")
        return int(user_id) if user_id is not None else None
    except JWTError:
        return None
