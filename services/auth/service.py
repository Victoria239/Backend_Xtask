"""Auth service - Business logic."""

from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt

from shared.config import get_settings
from shared.exceptions import ConflictException, UnauthorizedException
from services.auth.models import User
from services.auth.repository import UserRepository
from services.auth.schemas import LoginRequest, RegisterRequest, UserOut, LoginResponse


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


class AuthService:
    def __init__(self, repo: UserRepository):
        self.repo = repo
        self.settings = get_settings()

    async def login(self, data: LoginRequest) -> LoginResponse:
        user = await self.repo.get_by_identifier(data.identifier)
        if not user or not verify_password(data.password, user.password):
            raise UnauthorizedException("Invalid credentials")

        tenant_id = await self._resolve_default_tenant_id(user.id)
        token = self._create_token(user, tenant_id=tenant_id)
        return LoginResponse(token=token, user=UserOut.from_orm_user(user))

    async def register(self, data: RegisterRequest) -> LoginResponse:
        existing = await self.repo.get_by_username(data.username)
        if existing:
            raise ConflictException(f"Username '{data.username}' already taken")

        existing = await self.repo.get_by_email(data.email)
        if existing:
            raise ConflictException(f"Email '{data.email}' already registered")

        hashed_password = hash_password(data.password)
        user = await self.repo.create({
            "username": data.username,
            "email": data.email,
            "password": hashed_password,
            "full_name": data.fullName,
            "role": data.role or "user",
        })

        tenant_id = await self._resolve_default_tenant_id(user.id)
        token = self._create_token(user, tenant_id=tenant_id)
        return LoginResponse(token=token, user=UserOut.from_orm_user(user))

    async def _resolve_default_tenant_id(self, user_id: int) -> int | None:
        """Look up the user's default tenant from svc_tenants.tenant_memberships.

        Failure-tolerant: if the table doesn't exist yet (fresh install) or
        the user has no memberships, return ``None`` and let the caller decide.
        """
        from sqlalchemy import text

        try:
            res = await self.repo.db.execute(
                text(
                    """
                    SELECT tenant_id
                    FROM svc_tenants.tenant_memberships
                    WHERE user_id = :uid
                    ORDER BY is_default DESC, id ASC
                    LIMIT 1
                    """
                ),
                {"uid": user_id},
            )
            row = res.first()
            return int(row[0]) if row else None
        except Exception:  # noqa: BLE001
            return None

    async def get_current_user(self, user_id: int) -> UserOut:
        user = await self.repo.get_by_id(user_id)
        if not user:
            raise UnauthorizedException("User not found")
        return UserOut.from_orm_user(user)

    def validate_token(self, token: str) -> bool:
        try:
            jwt.decode(token, self.settings.JWT_SECRET, algorithms=[self.settings.JWT_ALGORITHM])
            return True
        except JWTError:
            return False

    def _create_token(self, user: User, tenant_id: int | None = None) -> str:
        expire = datetime.now(timezone.utc) + timedelta(minutes=self.settings.JWT_EXPIRATION_MINUTES)
        payload = {
            "sub": str(user.id),
            "username": user.username,
            "role": user.role,
            "exp": expire,
        }
        if tenant_id is not None:
            payload["tenant_id"] = tenant_id
        return jwt.encode(payload, self.settings.JWT_SECRET, algorithm=self.settings.JWT_ALGORITHM)
