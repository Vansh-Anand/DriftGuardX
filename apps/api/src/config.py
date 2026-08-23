import os
from typing import Literal

from pydantic import BaseModel, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class RuntimeSecurityConfig(BaseModel):
    mode: str = "development"
    allow_mock_verifiers: bool = True
    allow_fake_encoders: bool = True

    @classmethod
    def load(cls):
        mode = os.getenv("DGX_MODE", "development")
        if mode == "production":
            return cls(mode=mode, allow_mock_verifiers=False, allow_fake_encoders=False)
        return cls(mode=mode, allow_mock_verifiers=True, allow_fake_encoders=True)

class Settings(BaseSettings):
    environment: Literal["local", "test", "staging", "prod"] = "local"

    # Core API Settings
    api_title: str = "DriftGuard-X API"
    api_version: str = "0.19.0"

    # Postgres
    database_url: SecretStr = Field(default=SecretStr("postgresql+asyncpg://postgres:postgres@localhost:5432/driftguard"))

    # Redis
    redis_url: SecretStr = Field(default=SecretStr("redis://localhost:6379/0"))

    # Security (Must be provided in staging/prod)
    auth_mode: Literal["mock", "oidc"] = "mock"
    oidc_issuer: str | None = None
    oidc_audience: str | None = None
    oidc_jwks_uri: str | None = None
    kms_key_arn: str | None = None

    # Feature Flags
    enable_canary: bool = False
    use_real_rag_pipeline: bool = False
    llm_api_key: SecretStr | None = None

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    def check_unsafe_settings(self):
        """Validates that unsafe settings are not used in production."""
        if self.environment in ["staging", "prod"]:
            if self.auth_mode == "mock":
                raise ValueError("Unsafe auth_mode 'mock' detected in production environment!")
            if not self.oidc_issuer or not self.oidc_audience or not self.oidc_jwks_uri:
                raise ValueError("OIDC parameters must be set in production mode!")
            if "localhost" in self.database_url.get_secret_value():
                raise ValueError("Localhost database URL detected in production environment!")

settings = Settings()
settings.check_unsafe_settings()
