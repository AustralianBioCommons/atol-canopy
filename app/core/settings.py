from typing import List, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings.

    These settings can be configured using environment variables.
    """

    # Base
    PROJECT_NAME: str = "atol-canopy"
    API_V1_STR: str = "/api/v1"
    DEBUG: bool = False

    # Database
    POSTGRES_SERVER: Optional[str] = None
    POSTGRES_USER: Optional[str] = None
    POSTGRES_PASSWORD: Optional[str] = None
    POSTGRES_DB: Optional[str] = None
    POSTGRES_PORT: Optional[str] = None

    # Security
    JWT_SECRET_KEY: Optional[str] = None
    JWT_ALGORITHM: Optional[str] = None
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 150  # 150 minutes TODO change to 15 min for prod
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7  # 7 days

    DATABASE_URI: Optional[str] = None

    # CORS
    BACKEND_CORS_ORIGINS: List[str] = []

    # Environment
    ENVIRONMENT: Optional[str] = None  # Options: "dev", "prod"
    APP_VERSION: str = "dev"

    # Model config
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.DATABASE_URI and all(
            [
                self.POSTGRES_USER,
                self.POSTGRES_PASSWORD,
                self.POSTGRES_SERVER,
                self.POSTGRES_PORT,
                self.POSTGRES_DB,
            ]
        ):
            self.DATABASE_URI = (
                f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
                f"@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
            )

        # Default permissive CORS for non-prod only when unset
        if not self.BACKEND_CORS_ORIGINS and self.ENVIRONMENT != "prod":
            self.BACKEND_CORS_ORIGINS = ["*"]

        # Fail fast on missing critical settings
        if not self.JWT_SECRET_KEY or not self.JWT_ALGORITHM:
            raise ValueError("JWT_SECRET_KEY and JWT_ALGORITHM must be set")
        if not self.DATABASE_URI:
            raise ValueError("DATABASE_URI must be set (or derived from POSTGRES_* settings)")
        if self.ENVIRONMENT == "prod" and self.BACKEND_CORS_ORIGINS == ["*"]:
            raise ValueError("BACKEND_CORS_ORIGINS cannot be ['*'] in production")


settings = Settings()
