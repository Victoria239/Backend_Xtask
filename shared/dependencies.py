"""Shared FastAPI dependencies used across services.

Autenticación:
- Si KEYCLOAK_ENABLED=true (default), valida JWTs contra JWKS de Keycloak.
- En caso contrario, valida JWTs HS256 legacy firmados con JWT_SECRET.

El reemplazo total no rompe interfaces: ``CurrentUser`` mantiene los mismos
campos (id: int, role, tenant_id). Cuando viene de Keycloak:
- ``id`` se obtiene via JIT-provisioning local por email
- ``tenant_id`` via lookup slug → svc_tenants.tenants.id
- ``role`` mapeado de xtask-X → X (admin/manager/member/viewer)
"""

from dataclasses import dataclass
from typing import Callable

from fastapi import Depends, Header
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from shared.config import Settings, get_settings
from shared.database import get_db
from shared.exceptions import ForbiddenException, UnauthorizedException
from shared.keycloak import (
    KeycloakClaims,
    decode_keycloak_token,
    resolve_local_tenant_id,
    resolve_local_user_id,
)

security = HTTPBearer(auto_error=False)


# ─── Current User model ─────────────────────────────────────────
@dataclass(frozen=True)
class CurrentUser:
    """Authenticated user — fuente puede ser Keycloak o JWT legacy."""
    id: int
    username: str
    role: str
    tenant_id: int | None = None
    email: str = ""
    sub: str = ""                  # Keycloak UUID (empty en modo legacy)
    realm_roles: tuple[str, ...] = ()

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
    db: AsyncSession = Depends(get_db),
) -> CurrentUser:
    if credentials is None:
        raise UnauthorizedException("Missing authentication token")

    if settings.KEYCLOAK_ENABLED:
        return await _build_user_from_keycloak(credentials.credentials, settings, db)
    return await _build_user_from_legacy_jwt(credentials.credentials, settings)


async def _build_user_from_keycloak(
    token: str, settings: Settings, db: AsyncSession,
) -> CurrentUser:
    claims = await decode_keycloak_token(token, settings)
    user_id = await resolve_local_user_id(db, claims)
    tenant_id = await resolve_local_tenant_id(db, claims.tenant_slug)
    return CurrentUser(
        id=user_id,
        username=claims.username,
        role=claims.primary_role,
        tenant_id=tenant_id,
        email=claims.email,
        sub=claims.sub,
        realm_roles=tuple(claims.roles),
    )


async def _build_user_from_legacy_jwt(token: str, settings: Settings) -> CurrentUser:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            raise UnauthorizedException("Invalid token payload")
        return CurrentUser(
            id=int(user_id),
            username=payload.get("username", ""),
            role=payload.get("role", "user"),
            tenant_id=payload.get("tenant_id"),
        )
    except JWTError as e:
        raise UnauthorizedException(f"Invalid or expired token: {e}")


# ─── Multi-tenant resolution ────────────────────────────────────
async def get_current_tenant_id(
    user: CurrentUser = Depends(get_current_user),
    x_tenant_id: int | None = Header(default=None, alias="X-Tenant-Id"),
) -> int:
    """Resolve the active tenant for the current request.

    Resolution order:
      1. X-Tenant-Id header (must match a tenant the user belongs to — enforced
         downstream when querying memberships).
      2. tenant_id embedded in the JWT (default tenant at login time).
    """
    if x_tenant_id is not None:
        return int(x_tenant_id)
    if user.tenant_id is not None:
        return int(user.tenant_id)
    raise ForbiddenException(
        "No active tenant. Send X-Tenant-Id header or re-issue your JWT with a tenant claim."
    )


async def get_optional_tenant_id(
    x_tenant_id: int | None = Header(default=None, alias="X-Tenant-Id"),
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    settings: Settings = Depends(get_settings),
    db: AsyncSession = Depends(get_db),
) -> int | None:
    """Best-effort tenant resolution sin lanzar. Usado por endpoints públicos."""
    if x_tenant_id is not None:
        return int(x_tenant_id)
    if credentials is None:
        return None

    if settings.KEYCLOAK_ENABLED:
        try:
            claims = await decode_keycloak_token(credentials.credentials, settings)
            return await resolve_local_tenant_id(db, claims.tenant_slug)
        except UnauthorizedException:
            return None

    try:
        payload = jwt.decode(
            credentials.credentials, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM],
        )
        tid = payload.get("tenant_id")
        return int(tid) if tid is not None else None
    except JWTError:
        return None


# ─── Backward-compatible: extracts only user_id ─────────────────
async def get_current_user_id(user: CurrentUser = Depends(get_current_user)) -> int:
    return user.id


async def get_optional_user_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    settings: Settings = Depends(get_settings),
    db: AsyncSession = Depends(get_db),
) -> int | None:
    if credentials is None:
        return None
    try:
        user = await get_current_user(credentials, settings, db)
        return user.id
    except UnauthorizedException:
        return None


# ─── Role-based access control dependencies ─────────────────────
def require_roles(*allowed_roles: str) -> Callable:
    """Factory que crea una dependency que requiere roles específicos."""
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
require_user = require_roles("admin", "manager", "user", "member")
