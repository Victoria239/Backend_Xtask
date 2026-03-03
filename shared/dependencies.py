"""Shared FastAPI dependencies used across services."""

from dataclasses import dataclass
from typing import Callable

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from shared.config import Settings, get_settings
from shared.database import get_db
from shared.exceptions import ForbiddenException, UnauthorizedException

security = HTTPBearer(auto_error=False)


# ─── Current User model ─────────────────────────────────────────
@dataclass(frozen=True)
class CurrentUser:
    """Authenticated user extracted from JWT token."""
    id: int
    username: str
    role: str

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    @property
    def is_manager(self) -> bool:
        return self.role in ("admin", "manager")


# ─── Core authentication dependency ─────────────────────────────
async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    settings: Settings = Depends(get_settings),
) -> CurrentUser:
    """Extract and validate full user info from JWT token."""
    if credentials is None:
        raise UnauthorizedException("Missing authentication token")

    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
        )
        user_id = payload.get("sub")
        if user_id is None:
            raise UnauthorizedException("Invalid token payload")
        return CurrentUser(
            id=int(user_id),
            username=payload.get("username", ""),
            role=payload.get("role", "user"),
        )
    except JWTError as e:
        raise UnauthorizedException(f"Invalid or expired token: {str(e)}")


# ─── Backward-compatible: extracts only user_id ─────────────────
async def get_current_user_id(
    user: CurrentUser = Depends(get_current_user),
) -> int:
    """Extract user ID from JWT token (backward compatible)."""
    return user.id


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


# ─── Role-based access control dependencies ─────────────────────
def require_roles(*allowed_roles: str) -> Callable:
    """Factory that creates a dependency requiring specific roles.

    Usage in router:
        @router.delete("/{id}", dependencies=[Depends(require_roles("admin"))])
        @router.post("/", dependencies=[Depends(require_roles("admin", "manager"))])
    """
    async def _check_role(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if user.role not in allowed_roles:
            raise ForbiddenException(
                f"Role '{user.role}' not authorized. Required: {', '.join(allowed_roles)}"
            )
        return user
    return _check_role


# ─── Convenience shortcuts ───────────────────────────────────────
require_admin = require_roles("admin")
require_manager = require_roles("admin", "manager")
require_user = require_roles("admin", "manager", "user")
