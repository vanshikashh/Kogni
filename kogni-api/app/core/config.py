from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql://kogni:kogni@localhost:5432/kogni"

    # Auth
    SECRET_KEY: str = "change-me-in-production-use-openssl-rand-hex-32"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    # Redis / Celery
    REDIS_URL: str = "redis://localhost:6379/0"

    # App
    APP_ENV: str = "development"
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "chrome-extension://",
    ]

    class Config:
        env_file = ".env"


settings = Settings()
