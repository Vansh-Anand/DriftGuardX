from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, SecretStr
from typing import Literal

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
    jwt_secret_key: SecretStr = Field(default=SecretStr("dev-unsafe-secret"))
    kms_key_arn: str | None = None
    
    # Feature Flags
    enable_canary: bool = False
    
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
    
    def check_unsafe_settings(self):
        """Validates that unsafe settings are not used in production."""
        if self.environment in ["staging", "prod"]:
            if self.jwt_secret_key.get_secret_value() == "dev-unsafe-secret":
                raise ValueError("Unsafe jwt_secret_key detected in production environment!")
            if "localhost" in self.database_url.get_secret_value():
                raise ValueError("Localhost database URL detected in production environment!")

settings = Settings()
settings.check_unsafe_settings()
