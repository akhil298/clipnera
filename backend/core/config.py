from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from enum import Enum


class Environment(str, Enum):
    DEVELOPMENT = "development"
    TESTING = "testing"
    PRODUCTION = "production"


class BaseConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    APP_NAME: str = "Clipnera"
    APP_VERSION: str = "0.1.0"
    ENVIRONMENT: Environment = Environment.DEVELOPMENT
    APP_DEBUG: bool = True

    HOST: str = "0.0.0.0"
    PORT: int = 8000

    DATABASE_URL: str = "postgresql+asyncpg://postgres:password@localhost:5432/clipneras"
    REDIS_URL: str = "redis://localhost:6379/0"

    SECRET_KEY: str = "dev-secret-key-change-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7

    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o"
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-sonnet-4-20250514"
    XAI_API_KEY: str = ""
    XAI_MODEL: str = "grok-4"
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.5-flash"

    AWS_REGION: str = "us-east-1"
    AWS_ACCESS_KEY_ID: str = "test"
    AWS_SECRET_ACCESS_KEY: str = "test"
    LOCALSTACK_ENDPOINT: str = "http://localhost:4566"

    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    MICROSOFT_CLIENT_ID: str = ""
    MICROSOFT_CLIENT_SECRET: str = ""
    MICROSOFT_TENANT_ID: str = "common"

    EMAIL_SENDER: str = "no-reply@clipnera.com"
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_PHONE_NUMBER: str = ""

    TRANSCRIPTION_OUTPUT_DIR: str = "./transcription_outputs"
    HF_TOKEN: str = ""


class DevelopmentConfig(BaseConfig):
    model_config = SettingsConfigDict(
        env_file=".env.development",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )
    APP_DEBUG: bool = True


class TestingConfig(BaseConfig):
    model_config = SettingsConfigDict(
        env_file=".env.testing",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )
    APP_DEBUG: bool = True
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/clipnera_test"
    REDIS_URL: str = "redis://localhost:6379/1"


class ProductionConfig(BaseConfig):
    model_config = SettingsConfigDict(
        env_file=".env.production",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )
    APP_DEBUG: bool = False


CONFIG_MAP = {
    Environment.DEVELOPMENT: DevelopmentConfig,
    Environment.TESTING: TestingConfig,
    Environment.PRODUCTION: ProductionConfig,
}


@lru_cache
def get_settings() -> BaseConfig:
    env = BaseConfig().ENVIRONMENT
    return CONFIG_MAP[env]()
