from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://xtask:xtask_dev_2024@localhost:5432/xtask_db"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # JWT
    JWT_SECRET: str = "change-this-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_MINUTES: int = 1440  # 24 hours

    # Server
    ENVIRONMENT: str = "development"
    GATEWAY_PORT: int = 8000
    GATEWAY_MODE: str = "monolith"  # "monolith" or "proxy"
    LOG_LEVEL: str = "DEBUG"

    # Microservice URLs (used in proxy mode)
    AUTH_SERVICE_URL: str = "http://localhost:8001"
    PROJECTS_SERVICE_URL: str = "http://localhost:8002"
    EMPLOYEES_SERVICE_URL: str = "http://localhost:8003"
    FINANCE_SERVICE_URL: str = "http://localhost:8004"
    PAYROLL_SERVICE_URL: str = "http://localhost:8005"
    KPIS_SERVICE_URL: str = "http://localhost:8006"
    SKILLS_SERVICE_URL: str = "http://localhost:8007"
    DASHBOARD_SERVICE_URL: str = "http://localhost:8008"

    # CORS
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:5173,http://localhost:8080"

    # Email
    SENDGRID_API_KEY: str = ""
    EMAIL_FROM: str = "noreply@xtask.com"

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]

    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT == "development"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
