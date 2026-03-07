"""Auth service - API routes."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database import get_service_db
from shared.dependencies import get_current_user_id, require_admin
from services.auth.repository import UserRepository
from services.auth.service import AuthService
from services.auth.schemas import (
    LoginRequest,
    LoginResponse,
    RegisterRequest,
    UserOut,
    ValidateTokenRequest,
    ValidateTokenResponse,
)

router = APIRouter()


def get_auth_service(db: AsyncSession = Depends(get_service_db("auth"))) -> AuthService:
    return AuthService(UserRepository(db))


@router.post("/login", response_model=LoginResponse)
async def login(data: LoginRequest, service: AuthService = Depends(get_auth_service)):
    return await service.login(data)


@router.post("/register", response_model=LoginResponse, dependencies=[Depends(require_admin)])
async def register(data: RegisterRequest, service: AuthService = Depends(get_auth_service)):
    return await service.register(data)


@router.post("/logout")
async def logout():
    return {"success": True, "message": "Logged out successfully"}


@router.get("/me", response_model=UserOut)
async def get_me(
    user_id: int = Depends(get_current_user_id),
    service: AuthService = Depends(get_auth_service),
):
    return await service.get_current_user(user_id)


@router.post("/validate-token", response_model=ValidateTokenResponse)
async def validate_token(data: ValidateTokenRequest, service: AuthService = Depends(get_auth_service)):
    valid = service.validate_token(data.token)
    return ValidateTokenResponse(valid=valid)
