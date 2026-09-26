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
    # "auto" picks per plan and per step (see clients.ai.STEP_MODELS). Naming a
    # provider pins every step to it, which is what local work and A/B runs
    # want -- and costs Opus prices on every call if left at "anthropic".
    AI_PROVIDER: str = "auto"

    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-opus-5"
    # Thinking depth for steps without their own setting: low | medium | high | xhigh | max.
    ANTHROPIC_EFFORT: str = "medium"
    # Most a pipeline run may spend on AI, per minute of source video. At 80%
    # the remaining calls drop to low effort; at 100% they stop and the
    # heuristic fallbacks take over, so a video never ends up without clips.
    # 0 disables the cap.
    AI_BUDGET_PER_SOURCE_MINUTE_PRO: float = 0.015
    AI_BUDGET_PER_SOURCE_MINUTE_FREE: float = 0.002
    XAI_API_KEY: str = ""
    XAI_MODEL: str = "grok-2-mini"
    GROQ_API_KEY: str = ""
    # llama-3.1-8b-instant and llama-3.3-70b-versatile were decommissioned on
    # 2026-08-16 and are Enterprise-only, so they are no longer usable defaults.
    GROQ_MODEL: str = "openai/gpt-oss-20b"
    # Speech-to-text: "auto" uses Groq's hosted Whisper when GROQ_API_KEY is
    # set (no GPU needed) and falls back to local faster-whisper; "local"
    # always transcribes on this machine.
    TRANSCRIPTION_PROVIDER: str = "auto"
    GROQ_WHISPER_MODEL: str = "whisper-large-v3-turbo"
    # Noise cancellation is skipped when the extracted audio's estimated
    # signal-to-noise ratio is at least this many dB (studio-clean speech).
    NOISE_CANCEL_SKIP_SNR_DB: float = 30.0
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.0-flash"

    # Pins every clip to these shapes regardless of content. Left empty -- the
    # default -- the content category decides (see CATEGORY_ASPECT_RATIOS), so
    # a gaming clip is cut 9:16 only instead of in all four shapes.
    DEFAULT_OUTPUT_ASPECT_RATIOS: str = ""
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

    # Manual UPI payments: users pay this VPA, upload proof, and an admin verifies.
    UPI_ID: str = ""
    UPI_PAYEE_NAME: str = "Clipnera"
    PAYMENT_SUBMISSIONS_PER_HOUR: int = 5

    EMAIL_SENDER: str = "no-reply@clipnera.com"
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_PHONE_NUMBER: str = ""

    TRANSCRIPTION_OUTPUT_DIR: str = "./transcription_outputs"
    HF_TOKEN: str = ""
    WATERMARK_ENABLED: bool = True
    WATERMARK_PATH: str = "./backend/static/watermark.png"

    # yt-dlp cookies. A browser name ("chrome", "firefox") reads them live from
    # that browser and wins over the file; for servers, update_ec2.sh exports
    # them locally and copies them to YOUTUBE_COOKIES_PATH.
    YOUTUBE_COOKIES_BROWSER: str = ""
    YOUTUBE_COOKIES_PATH: str = "~/.clipnera/youtube_cookies.txt"

    # Connected publishing platforms (social/). OAuth callbacks land on the
    # frontend, so redirect URIs are built from PUBLIC_APP_URL and must match
    # each platform's developer console exactly.
    PUBLIC_APP_URL: str = "http://localhost:3000"
    PUBLIC_API_URL: str = "http://localhost:8000"
    # AES-256-GCM key ring for stored platform tokens: "<version>:<base64 32-byte key>"
    # pairs, comma-separated. New tokens use SOCIAL_TOKEN_ACTIVE_KEY_VERSION; older
    # versions stay listed until `python -m social.rotate_keys` has re-encrypted them.
    SOCIAL_TOKEN_ENCRYPTION_KEYS: str = ""
    SOCIAL_TOKEN_ACTIVE_KEY_VERSION: int = 1
    YOUTUBE_CLIENT_ID: str = ""
    YOUTUBE_CLIENT_SECRET: str = ""
    TIKTOK_CLIENT_KEY: str = ""
    TIKTOK_CLIENT_SECRET: str = ""
    INSTAGRAM_APP_ID: str = ""
    INSTAGRAM_APP_SECRET: str = ""
    X_CLIENT_ID: str = ""
    X_CLIENT_SECRET: str = ""
    # X bills every post; publishing to X stops for the month once this is spent.
    X_MONTHLY_BUDGET_USD: float = 25.0


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
