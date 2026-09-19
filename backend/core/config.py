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

    DATABASE_URL: str = ""
    REDIS_URL: str = "redis://localhost:6379/0"

    SECRET_KEY: str = ""
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7

    # Text provider for the pipeline: "auto" | "groq" | "anthropic".
    # "auto" decides per user -- pro plans get Anthropic (1M context,
    # schema-enforced JSON), free plans get Groq's free tier. Naming a provider
    # pins every run to it, which is what local work and A/B runs want.
    AI_PROVIDER: str = "auto"

    # Emails always treated as paid, whatever the subscription table says.
    # For founders, staff and demo accounts. Comma-separated, case-insensitive.
    # These users cost real money per run, so keep the list short and explicit.
    PRO_OVERRIDE_EMAILS: str = "akhilakhi298@gmail.com"

    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-opus-5"
    # Thinking depth and token spend: low | medium | high | xhigh | max.
    ANTHROPIC_EFFORT: str = "high"
    XAI_API_KEY: str = ""
    XAI_MODEL: str = "grok-2-mini"
    GROQ_API_KEY: str = ""
    # llama-3.1-8b-instant and llama-3.3-70b-versatile were decommissioned on
    # 2026-08-16 and are Enterprise-only, so they are no longer usable defaults.
    GROQ_MODEL: str = "openai/gpt-oss-20b"
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.0-flash"

    DEFAULT_OUTPUT_ASPECT_RATIOS: str = "9:16,1:1,4:5,16:9"
    CLIP_OUTPUT_DIR: str = "./generated_clips"
    FRAME_ANALYSIS_INTERVAL: float = 5.0
    CANDIDATE_FRAME_INTERVAL: float = 2.0
    CANDIDATE_MAX_FRAMES: int = 8

    AWS_REGION: str = "us-east-1"
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    LOCALSTACK_ENDPOINT: str = ""
    S3_BUCKET_NAME: str = "clipnera-videos"

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
    WATERMARK_ENABLED: bool = True
    WATERMARK_PATH: str = "./backend/static/watermark.png"


class DevelopmentConfig(BaseConfig):
    model_config = SettingsConfigDict(
        env_file=".env",
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
