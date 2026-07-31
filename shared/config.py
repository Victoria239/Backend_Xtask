from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings

APP_VERSION: str = "0.2.0"


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database (shared default — used by gateway in monolith mode)
    DATABASE_URL: str = "postgresql+asyncpg://xtask:xtask_dev_2024@localhost:5432/xtask_db"

    # Per-service database URLs (default to shared DATABASE_URL)
    AUTH_DATABASE_URL: str = ""
    PROJECTS_DATABASE_URL: str = ""
    EMPLOYEES_DATABASE_URL: str = ""
    FINANCE_DATABASE_URL: str = ""
    PAYROLL_DATABASE_URL: str = ""
    KPIS_DATABASE_URL: str = ""
    SKILLS_DATABASE_URL: str = ""
    DASHBOARD_DATABASE_URL: str = ""

    def get_service_database_url(self, service: str) -> str:
        """Return the database URL for a specific service, falling back to DATABASE_URL."""
        key = f"{service.upper()}_DATABASE_URL"
        url = getattr(self, key, "") or ""
        return url if url else self.DATABASE_URL

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # JWT (legacy — usado solo si KEYCLOAK_ENABLED=false)
    JWT_SECRET: str = "change-this-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_MINUTES: int = 1440  # 24 hours

    # ─── Keycloak (auth provider canónico) ──────────────────────────
    # Cuando KEYCLOAK_ENABLED=true, los tokens se validan contra JWKS
    # de Keycloak y el flujo /login se proxy-ea al token endpoint.
    KEYCLOAK_ENABLED: bool = True
    KEYCLOAK_URL: str = "http://keycloak:8080"      # interno de docker network
    KEYCLOAK_PUBLIC_URL: str = "http://localhost:8088"  # para issuer matching (frontend lo ve)
    KEYCLOAK_REALM: str = "xtask-default"
    KEYCLOAK_CLIENT_ID_FRONTEND: str = "xtask-frontend"
    KEYCLOAK_CLIENT_ID_BACKEND: str = "xtask-backend"
    KEYCLOAK_CLIENT_SECRET: str = ""                # del client confidencial
    KEYCLOAK_AUDIENCE: str = "account"              # default audience que Keycloak inyecta
    KEYCLOAK_JWKS_CACHE_TTL: int = 3600             # 1h cache de JWKS

    # Server
    ENVIRONMENT: str = "development"
    GATEWAY_PORT: int = 8000
    GATEWAY_MODE: str = "monolith"  # "monolith" or "proxy"
    LOG_LEVEL: str = "DEBUG"

    @model_validator(mode="after")
    def _validate_jwt_secret(self):
        if self.ENVIRONMENT != "development" and self.JWT_SECRET == "change-this-in-production":
            raise ValueError("JWT_SECRET must be set to a secure value in non-development environments")
        return self

    # Microservice URLs (used in proxy mode)
    AUTH_SERVICE_URL: str = "http://localhost:8001"
    PROJECTS_SERVICE_URL: str = "http://localhost:8002"
    EMPLOYEES_SERVICE_URL: str = "http://localhost:8003"
    FINANCE_SERVICE_URL: str = "http://localhost:8004"
    PAYROLL_SERVICE_URL: str = "http://localhost:8005"
    KPIS_SERVICE_URL: str = "http://localhost:8006"
    SKILLS_SERVICE_URL: str = "http://localhost:8007"
    DASHBOARD_SERVICE_URL: str = "http://localhost:8008"
    AI_ASSISTANT_SERVICE_URL: str = "http://localhost:8009"
    RAG_SERVICE_URL: str = "http://localhost:8010"
    TENANTS_SERVICE_URL: str = "http://localhost:8011"
    NOTIFICATIONS_SERVICE_URL: str = "http://localhost:8012"
    ONBOARDING_SERVICE_URL: str = "http://localhost:8013"
    DOCGEN_SERVICE_URL: str = "http://localhost:8014"
    OKRS_SERVICE_URL: str = "http://localhost:8015"
    CONTRACTS_SERVICE_URL: str = "http://localhost:8016"
    PLANS_SERVICE_URL: str = "http://localhost:8017"
    LEAVES_SERVICE_URL: str = "http://localhost:8018"
    ATS_SERVICE_URL: str = "http://localhost:8019"
    PAYOUTS_SERVICE_URL: str = "http://localhost:8020"
    APPROVALS_SERVICE_URL: str = "http://localhost:8021"
    PREDICTIONS_SERVICE_URL: str = "http://localhost:8022"
    REVIEWS_SERVICE_URL: str = "http://localhost:8023"
    TASKS_SERVICE_URL: str = "http://localhost:8024"

    # CORS
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:3001,http://localhost:5173,http://localhost:8080"

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
