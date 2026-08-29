from functools import lru_cache
from typing import List, Union
from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application Settings configuration powered by Pydantic Settings.
    Reads configuration values from environment variables and/or .env file.
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Project Information
    PROJECT_NAME: str = "MARGA Backend API"
    VERSION: str = "1.0.0"
    DESCRIPTION: str = "Backend service foundation for Project MARGA"
    API_V1_STR: str = "/api/v1"

    # Environment
    ENVIRONMENT: str = "development"  # development | staging | production
    DEBUG: bool = True

    # Server Configuration
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # CORS Configuration
    # Accepts a list of origins or a comma-separated string from environment variables
    BACKEND_CORS_ORIGINS: Union[List[str], str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ]

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, list):
            return v
        return []

    # Logging Configuration
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


@lru_cache()
def get_settings() -> Settings:
    """
    Returns a cached singleton instance of application settings.
    Ensures .env is read once rather than on every request.
    """
    return Settings()


# Global settings instance for easy direct access when needed outside of DI
settings = get_settings()
