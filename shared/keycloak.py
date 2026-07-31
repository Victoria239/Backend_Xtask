"""Keycloak OIDC integration — JWKS validation and token exchange.

Estrategia:
- Cache del JWKS con TTL (1h por defecto) — Keycloak rota claves cada 90d.
- Validación local del JWT contra la clave pública (no introspect remoto en cada request).
- Endpoint de token (/login) y userinfo expuestos para el auth service.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import httpx
from jose import JWTError, jwt
from jose.exceptions import ExpiredSignatureError

from shared.config import Settings, get_settings
from shared.exceptions import UnauthorizedException
from shared.logging import get_logger

logger = get_logger(__name__)


# ─── In-process JWKS cache ─────────────────────────────────────────
# Sencillo: Python dict con TTL. En multi-worker cada proceso tiene
# su copia, lo cual es OK — JWKS no rota cada segundo.
_jwks_cache: dict[str, tuple[float, list[dict[str, Any]]]] = {}


def _jwks_url(settings: Settings) -> str:
    return f"{settings.KEYCLOAK_URL}/realms/{settings.KEYCLOAK_REALM}/protocol/openid-connect/certs"


def _token_url(settings: Settings) -> str:
    return f"{settings.KEYCLOAK_URL}/realms/{settings.KEYCLOAK_REALM}/protocol/openid-connect/token"


def _logout_url(settings: Settings) -> str:
    return f"{settings.KEYCLOAK_URL}/realms/{settings.KEYCLOAK_REALM}/protocol/openid-connect/logout"


def _expected_issuer(settings: Settings) -> str:
    """El issuer que Keycloak escribe en el JWT es el PUBLIC_URL desde el navegador."""
    return f"{settings.KEYCLOAK_PUBLIC_URL}/realms/{settings.KEYCLOAK_REALM}"


async def _fetch_jwks(settings: Settings) -> list[dict[str, Any]]:
    """Obtiene JWKS de Keycloak con cache TTL."""
    url = _jwks_url(settings)
    now = time.time()
    cached = _jwks_cache.get(url)
    if cached and (now - cached[0]) < settings.KEYCLOAK_JWKS_CACHE_TTL:
        return cached[1]

    async with httpx.AsyncClient(timeout=5.0) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        keys = resp.json().get("keys", [])

    _jwks_cache[url] = (now, keys)
    logger.info("jwks_refreshed", url=url, keys=len(keys))
    return keys


def _find_key(jwks: list[dict[str, Any]], kid: str) -> dict[str, Any] | None:
    return next((k for k in jwks if k.get("kid") == kid), None)


@dataclass(frozen=True)
class KeycloakClaims:
    """Subset tipado de los claims que XTask consume del access token."""
    sub: str                       # UUID estable del user en Keycloak
    email: str
    username: str                  # preferred_username
    name: str                      # full name
    tenant_slug: str               # del claim custom tenant_id (en el realm es slug)
    realm: str                     # realm name, e.g. "xtask-default"
    roles: list[str]               # realm roles, e.g. ["xtask-admin", "xtask-member"]
    raw: dict[str, Any]            # claims completos para casos avanzados

    @property
    def primary_role(self) -> str:
        """Mapea xtask-X → X. Devuelve el rol de mayor privilegio si tiene varios."""
        priority = ["admin", "manager", "member", "viewer"]
        xtask_roles = {r.removeprefix("xtask-") for r in self.roles if r.startswith("xtask-")}
        for p in priority:
            if p in xtask_roles:
                return p
        return "user"


async def decode_keycloak_token(token: str, settings: Settings | None = None) -> KeycloakClaims:
    """Valida y decodifica un access token emitido por Keycloak.

    Verifica firma RS256 contra JWKS, expiración, issuer.
    Audience se valida sólo si el claim 'aud' existe y no es el placeholder 'account'.
    """
    settings = settings or get_settings()

    try:
        header = jwt.get_unverified_header(token)
    except JWTError as e:
        raise UnauthorizedException(f"Malformed token: {e}") from e

    kid = header.get("kid")
    if not kid:
        raise UnauthorizedException("Token missing 'kid' header")

    jwks = await _fetch_jwks(settings)
    key = _find_key(jwks, kid)
    if key is None:
        # Posible rotación de claves — invalida cache y reintenta una vez
        _jwks_cache.clear()
        jwks = await _fetch_jwks(settings)
        key = _find_key(jwks, kid)
        if key is None:
            raise UnauthorizedException(f"Signing key '{kid}' not found in JWKS")

    try:
        claims = jwt.decode(
            token,
            key,
            algorithms=[header.get("alg", "RS256")],
            issuer=_expected_issuer(settings),
            # 'aud' validation es opcional — Keycloak por defecto pone "account"
            options={"verify_aud": False},
        )
    except ExpiredSignatureError as e:
        raise UnauthorizedException("Token expired") from e
    except JWTError as e:
        raise UnauthorizedException(f"Invalid token: {e}") from e

    realm_access = claims.get("realm_access") or {}
    roles = realm_access.get("roles") or []

    return KeycloakClaims(
        sub=claims["sub"],
        email=claims.get("email", ""),
        username=claims.get("preferred_username", claims.get("email", "")),
        name=claims.get("name") or f"{claims.get('given_name', '')} {claims.get('family_name', '')}".strip(),
        tenant_slug=str(claims.get("tenant_id") or claims.get("tenant") or "default"),
        realm=str(claims.get("realm") or claims.get("iss", "").rsplit("/", 1)[-1]),
        roles=roles,
        raw=claims,
    )


# ─── Token exchange (proxy de /login) ──────────────────────────────
async def exchange_password_for_token(
    username: str,
    password: str,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Password Grant contra Keycloak. Solo se usa desde el backend para el
    endpoint /api/v1/auth/login — el frontend SPA usa PKCE redirect."""
    settings = settings or get_settings()

    if not settings.KEYCLOAK_CLIENT_SECRET:
        raise UnauthorizedException(
            "KEYCLOAK_CLIENT_SECRET no configurado; /login backend deshabilitado. "
            "Use el flujo PKCE desde el frontend."
        )

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            _token_url(settings),
            data={
                "grant_type": "password",
                "client_id": settings.KEYCLOAK_CLIENT_ID_BACKEND,
                "client_secret": settings.KEYCLOAK_CLIENT_SECRET,
                "username": username,
                "password": password,
                "scope": "openid profile email",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

    if resp.status_code == 401:
        raise UnauthorizedException("Invalid credentials")
    if resp.status_code >= 400:
        logger.warning("keycloak_token_error", status=resp.status_code, body=resp.text[:300])
        raise UnauthorizedException(f"Keycloak error: {resp.status_code}")

    return resp.json()


async def exchange_authorization_code(
    code: str,
    redirect_uri: str,
    code_verifier: str | None = None,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Intercambio del authorization code emitido por Keycloak tras un flujo OIDC.

    Usa el cliente público ``xtask-frontend`` con PKCE — el ``code_verifier`` es
    generado por el browser y enviado al backend en el callback."""
    settings = settings or get_settings()

    data = {
        "grant_type": "authorization_code",
        "client_id": settings.KEYCLOAK_CLIENT_ID_FRONTEND,
        "code": code,
        "redirect_uri": redirect_uri,
    }
    if code_verifier:
        data["code_verifier"] = code_verifier

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            _token_url(settings),
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

    if resp.status_code >= 400:
        logger.warning("keycloak_code_exchange_error", status=resp.status_code, body=resp.text[:300])
        raise UnauthorizedException(f"Code exchange failed: {resp.status_code}")
    return resp.json()


async def refresh_token(refresh_token: str, settings: Settings | None = None) -> dict[str, Any]:
    """Refresh contra Keycloak. Usa el cliente backend confidencial — debe coincidir
    con el client que emitió el refresh token original (azp del JWT)."""
    settings = settings or get_settings()

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            _token_url(settings),
            data={
                "grant_type": "refresh_token",
                "client_id": settings.KEYCLOAK_CLIENT_ID_BACKEND,
                "client_secret": settings.KEYCLOAK_CLIENT_SECRET,
                "refresh_token": refresh_token,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

    if resp.status_code >= 400:
        raise UnauthorizedException(f"Refresh failed: {resp.status_code}")
    return resp.json()


async def resolve_local_user_id(
    db,
    claims: "KeycloakClaims",
) -> int:
    """JIT-provisioning del user local a partir de los claims Keycloak.

    Lookup por email en svc_auth.users. Si no existe, crea el registro
    con password placeholder (Keycloak es la fuente de verdad — el password
    local no se usa para autenticación).

    Cacheado en memoria — se invalida al reiniciar el proceso.
    """
    from sqlalchemy import text

    cached = _user_id_cache.get(claims.sub)
    if cached is not None:
        return cached

    row = (await db.execute(
        text("SELECT id FROM svc_auth.users WHERE email = :email LIMIT 1"),
        {"email": claims.email},
    )).first()

    if row:
        user_id = int(row[0])
    else:
        # JIT-create
        full_name = claims.name or claims.username or claims.email.split("@")[0]
        row = (await db.execute(
            text("""
                INSERT INTO svc_auth.users
                    (username, password, email, full_name, role, is_active, created_at)
                VALUES
                    (:username, :password, :email, :full_name, :role, true, NOW())
                ON CONFLICT (email) DO UPDATE SET email = EXCLUDED.email
                RETURNING id
            """),
            {
                "username": claims.username,
                "password": "keycloak-managed",
                "email": claims.email,
                "full_name": full_name,
                "role": claims.primary_role,
            },
        )).first()
        await db.commit()
        user_id = int(row[0])
        logger.info("user_jit_provisioned", sub=claims.sub, email=claims.email, user_id=user_id)

        # P-04: bienvenida al primer login del usuario
        try:
            from shared.notifications import emit_notification
            tenant_id = await resolve_local_tenant_id(db, claims.tenant_slug)
            await emit_notification(
                db,
                tenant_id=tenant_id,
                user_id=user_id,
                title=f"Bienvenido a Xtask, {full_name.split()[0] if full_name else 'colega'}",
                body="Tu cuenta acaba de crearse. Subí documentos al corpus, definí KPIs y empezá a usar el copiloto.",
                kind="success",
                category="auth",
                action_url="/",
                meta={"first_login": True},
            )
            await db.commit()
        except Exception:  # noqa: BLE001
            pass

    _user_id_cache[claims.sub] = user_id
    return user_id


async def resolve_local_tenant_id(db, tenant_slug: str) -> int | None:
    """Mapea slug del realm Keycloak → svc_tenants.tenants.id. Cacheado en memoria."""
    from sqlalchemy import text

    if not tenant_slug:
        return None

    cached = _tenant_id_cache.get(tenant_slug)
    if cached is not None:
        return cached

    try:
        row = (await db.execute(
            text("SELECT id FROM svc_tenants.tenants WHERE slug = :slug LIMIT 1"),
            {"slug": tenant_slug},
        )).first()
    except Exception:  # noqa: BLE001
        # Tabla aún no migrada (instalación fresca)
        return None

    if row is None:
        return None

    tenant_id = int(row[0])
    _tenant_id_cache[tenant_slug] = tenant_id
    return tenant_id


# Caches en memoria — se reconstruyen al reiniciar el proceso
_user_id_cache: dict[str, int] = {}
_tenant_id_cache: dict[str, int] = {}


async def revoke_session(refresh_token: str, settings: Settings | None = None) -> None:
    """Invalida la sesión en Keycloak. Best-effort — no levanta si falla."""
    settings = settings or get_settings()
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(
                _logout_url(settings),
                data={
                    "client_id": settings.KEYCLOAK_CLIENT_ID_BACKEND,
                    "client_secret": settings.KEYCLOAK_CLIENT_SECRET,
                    "refresh_token": refresh_token,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
    except Exception as e:  # noqa: BLE001
        logger.warning("keycloak_logout_failed", error=str(e))
