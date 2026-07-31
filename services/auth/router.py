"""Auth service - API routes.

Keycloak es la fuente de verdad. Este servicio:
- /login: proxy al token endpoint de Keycloak (password grant) + JIT-provision del user local
- /me: devuelve la identidad del JWT validado
- /refresh: refresca el access_token contra Keycloak
- /logout: invalida la sesión en Keycloak
- /register: deshabilitado en modo Keycloak (usar admin console o script de provisión)
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from shared.config import Settings, get_settings
from shared.database import get_db
from shared.dependencies import CurrentUser, get_current_user
from shared.keycloak import (
    decode_keycloak_token,
    exchange_authorization_code,
    exchange_password_for_token,
    refresh_token as keycloak_refresh,
    resolve_local_tenant_id,
    resolve_local_user_id,
    revoke_session,
)
from services.auth.schemas import (
    LoginRequest,
    LoginResponse,
    UserOut,
    ValidateTokenRequest,
    ValidateTokenResponse,
)

router = APIRouter()


@router.post("/login", response_model=LoginResponse)
async def login(
    data: LoginRequest,
    settings: Settings = Depends(get_settings),
    db: AsyncSession = Depends(get_db),
):
    """Password Grant proxy a Keycloak.

    El frontend SPA normalmente debería usar PKCE redirect; este endpoint
    existe para clientes legacy y para CLI/tests. Requiere KEYCLOAK_CLIENT_SECRET.
    """
    token_response = await exchange_password_for_token(
        username=data.identifier, password=data.password, settings=settings,
    )
    access_token = token_response["access_token"]
    refresh_token_value = token_response.get("refresh_token", "")

    # JIT-provision del user local + lookup tenant
    claims = await decode_keycloak_token(access_token, settings)
    user_id = await resolve_local_user_id(db, claims)
    await resolve_local_tenant_id(db, claims.tenant_slug)

    return LoginResponse(
        token=access_token,
        refresh_token=refresh_token_value,
        user=UserOut(
            id=user_id,
            username=claims.username,
            email=claims.email,
            fullName=claims.name,
            role=claims.primary_role,
        ),
    )


@router.post("/keycloak-callback", response_model=LoginResponse)
async def keycloak_callback(
    data: dict,
    settings: Settings = Depends(get_settings),
    db: AsyncSession = Depends(get_db),
):
    """Recibe el ``code`` que Keycloak entregó al frontend tras un flujo OIDC
    (login con Google IdP u otro), lo intercambia por tokens y devuelve la
    misma forma que /login para que el AuthContext lo consuma igual."""
    code = data.get("code")
    redirect_uri = data.get("redirect_uri")
    code_verifier = data.get("code_verifier")
    if not code or not redirect_uri:
        raise HTTPException(status_code=400, detail="code y redirect_uri requeridos")

    token_response = await exchange_authorization_code(
        code, redirect_uri, code_verifier=code_verifier, settings=settings,
    )
    access_token = token_response["access_token"]
    refresh_token_value = token_response.get("refresh_token", "")

    claims = await decode_keycloak_token(access_token, settings)
    user_id = await resolve_local_user_id(db, claims)
    await resolve_local_tenant_id(db, claims.tenant_slug)

    return LoginResponse(
        token=access_token,
        refresh_token=refresh_token_value,
        user=UserOut(
            id=user_id,
            username=claims.username,
            email=claims.email,
            fullName=claims.name,
            role=claims.primary_role,
        ),
    )


@router.post("/refresh", response_model=LoginResponse)
async def refresh(
    data: dict,
    settings: Settings = Depends(get_settings),
    db: AsyncSession = Depends(get_db),
):
    refresh_value = data.get("refresh_token")
    if not refresh_value:
        raise HTTPException(status_code=400, detail="refresh_token required")

    token_response = await keycloak_refresh(refresh_value, settings)
    access_token = token_response["access_token"]
    new_refresh = token_response.get("refresh_token", refresh_value)

    claims = await decode_keycloak_token(access_token, settings)
    user_id = await resolve_local_user_id(db, claims)

    return LoginResponse(
        token=access_token,
        refresh_token=new_refresh,
        user=UserOut(
            id=user_id,
            username=claims.username,
            email=claims.email,
            fullName=claims.name,
            role=claims.primary_role,
        ),
    )


@router.post("/register", status_code=status.HTTP_410_GONE)
async def register():
    """Deprecated. La creación de usuarios se hace en Keycloak admin console
    o via el script keycloak/scripts/provision-tenant.sh."""
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail=(
            "Registration moved to Keycloak. Use the admin console at "
            "http://localhost:8088 or the provision-tenant.sh script."
        ),
    )


@router.post("/logout")
async def logout(
    data: dict | None = None,
    settings: Settings = Depends(get_settings),
):
    refresh_value = (data or {}).get("refresh_token")
    if refresh_value:
        await revoke_session(refresh_value, settings)
    return {"success": True, "message": "Logged out successfully"}


@router.get("/me", response_model=UserOut)
async def get_me(user: CurrentUser = Depends(get_current_user)):
    return UserOut(
        id=user.id,
        username=user.username,
        email=user.email,
        fullName=user.username,
        role=user.role,
    )


@router.post("/validate-token", response_model=ValidateTokenResponse)
async def validate_token(
    data: ValidateTokenRequest,
    settings: Settings = Depends(get_settings),
):
    """Smoke endpoint: valida un token contra Keycloak y devuelve sus claims útiles."""
    try:
        claims = await decode_keycloak_token(data.token, settings)
        return ValidateTokenResponse(
            valid=True,
            sub=claims.sub,
            email=claims.email,
            tenant_slug=claims.tenant_slug,
            roles=list(claims.roles),
        )
    except Exception:  # noqa: BLE001
        return ValidateTokenResponse(valid=False)
