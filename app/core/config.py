from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://voter_user:password@localhost:5432/voter_db"

    # JWT
    SECRET_KEY: str = "change-me"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # App
    APP_ENV: str = "development"
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"

    # Super Admin seed
    SUPER_ADMIN_PHONE: str = "9000000000"
    SUPER_ADMIN_PASSWORD: str = "SuperSecret@123"
    SUPER_ADMIN_NAME: str = "Super Admin"

    # Duplicate detection radius (metres)
    DUPLICATE_RADIUS_METRES: int = 20

    # Uploads - S3
    USE_S3_ENABLED: bool = False
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_S3_BUCKET: str = "voter-app-uploads"
    AWS_S3_REGION: str = "ap-south-1"

    # Uploads - Local (fallback)
    UPLOAD_DIR: str = "uploads"
    UPLOAD_URL_PREFIX: str = "/uploads"
    HOUSEHOLD_IMAGE_LIMIT: int = 5


@lru_cache()
def get_settings() -> Settings:
    return Settings()
