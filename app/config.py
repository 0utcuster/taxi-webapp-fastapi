# app/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, AliasChoices


class Settings(BaseSettings):
    # Настройки pydantic: читаем .env, не падаем на лишние ключи
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        case_sensitive=False,
    )

    # База данных и токен бота
    DATABASE_URL: str = "postgresql+psycopg://village:postgres@127.0.0.1:5433/village"
    BOT_TOKEN: str | None = None
    BOT_USERNAME: str | None = None

    # Админы
    ADMIN_TG_ID: int | None = None              # одиночный ID (для совместимости)
    ADMIN_TG_IDS: str | None = None             # несколько через запятую
    ADMIN_PASSWORD: str | None = Field(
        default=None,
        validation_alias=AliasChoices("ADMIN_PASSWORD", "admin_password"),
    )

    # Безопасность и куки
    SECRET_KEY: str = "dev-secret"
    COOKIE_NAME: str = "access_token"
    COOKIE_SECURE: bool = False
    COOKIE_SAMESITE: str = "lax"

    # JWT
    JWT_TTL_SEC: int = 60 * 60 * 24 * 7
    JWT_ALG: str = "HS256"

    # CORS
    ALLOWED_ORIGINS: str = "*"


settings = Settings()