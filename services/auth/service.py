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

        token = self._create_token(user)
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

        token = self._create_token(user)
        return LoginResponse(token=token, user=UserOut.from_orm_user(user))

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

    def _create_token(self, user: User) -> str:
        expire = datetime.now(timezone.utc) + timedelta(minutes=self.settings.JWT_EXPIRATION_MINUTES)
        payload = {
            "sub": str(user.id),
            "username": user.username,
            "role": user.role,
            "exp": expire,
        }
        return jwt.encode(payload, self.settings.JWT_SECRET, algorithm=self.settings.JWT_ALGORITHM)
