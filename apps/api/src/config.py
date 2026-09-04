import os
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from packages.utils.src.version import APP_VERSION


class RuntimeSecurityConfig(BaseModel):
    mode: str = "development"
    allow_mock_verifiers: bool = True
    allow_fake_encoders: bool = True

    @classmethod
    def load(cls) -> "RuntimeSecurityConfig":
        mode = os.getenv("DGX_MODE", "development")
        if mode == "production":
            return cls(mode=mode, allow_mock_verifiers=False, allow_fake_encoders=False)
        return cls(mode=mode, allow_mock_verifiers=True, allow_fake_encoders=True)


class Settings(BaseSettings):
    environment: Literal["local", "test", "staging", "prod"] = "local"

    # Core API Settings
    api_title: str = "DriftGuard-X API"
    api_version: str = APP_VERSION

    # Postgres
    database_url: SecretStr = Field(default=SecretStr("sqlite+aiosqlite:///./driftguardx_dev.db"))

    # Redis
    redis_url: SecretStr = Field(default=SecretStr("redis://localhost:6379/0"))

    # Security (Must be provided in staging/prod)
    auth_mode: Literal["mock", "oidc"] = "mock"
    oidc_issuer: str | None = None
    oidc_audience: str | None = None
    oidc_jwks_uri: str | None = None
    kms_key_arn: str | None = None
    allow_jit_user_provisioning: bool = False
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    max_request_body_bytes: int = Field(default=2 * 1024 * 1024, ge=1024, le=64 * 1024 * 1024)

    # Feature Flags
    enable_canary: bool = False
    use_real_rag_pipeline: bool = False
    llm_api_key: SecretStr | None = None

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def production_like(self) -> bool:
        runtime_mode = os.getenv("DGX_MODE", "").lower()
        app_env = os.getenv("APP_ENV", "").lower()
        return (
            self.environment in ["staging", "prod"]
            or runtime_mode == "production"
            or app_env in {"staging", "production", "prod"}
        )

    @property
    def cors_origin_list(self) -> list[str]:
        return [
            origin.strip().rstrip("/") for origin in self.cors_origins.split(",") if origin.strip()
        ]

    def check_unsafe_settings(self) -> None:
        """Validates that unsafe settings are not used in production."""
        if self.production_like:
            if self.auth_mode == "mock":
                raise ValueError("Unsafe auth_mode 'mock' detected in production environment!")
            if not self.oidc_issuer or not self.oidc_audience or not self.oidc_jwks_uri:
                raise ValueError("OIDC parameters must be set in production mode!")
            if (
                urlparse(self.oidc_issuer).scheme != "https"
                or urlparse(self.oidc_jwks_uri).scheme != "https"
            ):
                raise ValueError("OIDC issuer and JWKS endpoints must use HTTPS in production")
            if not self.database_url.get_secret_value().startswith("postgresql+"):
                raise ValueError("Production requires an async PostgreSQL database URL")
            if "*" in self.cors_origin_list or not self.cors_origin_list:
                raise ValueError("Production CORS origins must be an explicit non-empty allowlist")
            for name in ("DGX_CAPABILITY_SECRET", "DGX_TRANSPORT_KEY"):
                if len(os.getenv(name, "")) < 32:
                    raise ValueError(f"{name} must be configured with at least 32 characters")
            if self.enable_canary and not self.kms_key_arn:
                raise ValueError(
                    "KMS_KEY_ARN is required when production canary recovery is enabled"
                )


settings = Settings()
settings.check_unsafe_settings()
