from typing import Literal

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

    # Text provider for the pipeline: "auto" | "groq" | "anthropic" | "openai".
    # "auto" picks per plan and per step (see clients.ai.STEP_MODELS): Pro runs
    # on OpenAI, free on Groq. Naming a provider pins every step of every plan
    # to it, which is what local work and A/B runs want -- and bills free users'
    # runs to that provider if left pinned in production.
    AI_PROVIDER: str = "auto"

    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_ENDPOINT: str = ""
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-opus-5-5"
    # Thinking depth for steps without their own setting: low | medium | high | xhigh | max.
    ANTHROPIC_EFFORT: str = "medium"
    # Most a pipeline run may spend on AI, per minute of source video. At 80%
    # the remaining calls drop to low effort; at 100% they stop and the
    # heuristic fallbacks take over, so a video never ends up without clips.
    # 0 disables the cap.
    AI_BUDGET_PER_SOURCE_MINUTE_PRO: float = 0.015
    AI_BUDGET_PER_SOURCE_MINUTE_FREE: float = 0.002
    # Credits charged per minute of source video, rounded up per video with a
    # minimum of one credit.
    CREDITS_PER_VIDEO_MINUTE: float = 2.0
    # Each output ratio picked beyond the first adds this share of the base
    # cost. Rendering is a small part of a run next to transcription and AI
    # analysis, so an extra ratio costs a fraction, not a whole run.
    EXTRA_ASPECT_RATIO_CREDIT_SHARE: float = 0.5
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
    GROQ_WHISPER_MODEL: str = "whisper-large-v3"
    # Noise cancellation is skipped when the extracted audio's estimated
    # signal-to-noise ratio is at least this many dB (studio-clean speech).
    NOISE_CANCEL_SKIP_SNR_DB: float = 30.0
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.0-flash"
    # Visual timeline (backend/visual_timeline/): a Gemini pass that tells the
    # AI director what is on screen. Skipped without GEMINI_API_KEY.
    VISUAL_TIMELINE_ENABLED: bool = True
    VISUAL_TIMELINE_MODEL: str = "gemini-3.1-flash-lite"
    VISUAL_TIMELINE_MEDIA_RESOLUTION: Literal[
        "MEDIA_RESOLUTION_LOW", "MEDIA_RESOLUTION_MEDIUM", "MEDIA_RESOLUTION_HIGH"
    ] = "MEDIA_RESOLUTION_MEDIUM"

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
    # Direct browser-to-S3 video uploads. S3 allows 5 MB-5 GB parts and at
    # most 10,000 of them; parts grow past the minimum only for huge files.
    UPLOAD_MIN_PART_BYTES: int = 16 * 1024 * 1024
    UPLOAD_MAX_BYTES: int = 10 * 1024 * 1024 * 1024
    UPLOAD_URL_TTL_SECONDS: int = 6 * 3600

    # Background jobs. "inprocess" runs them in the API process; "sqs" sends
    # them to SQS_JOBS_QUEUE_URL for `python -m jobs.worker` processes.
    JOB_QUEUE_BACKEND: Literal["inprocess", "sqs"] = "inprocess"
    SQS_JOBS_QUEUE_URL: str = ""
    JOB_WORKER_CONCURRENCY: int = 2
    # A running job's message is hidden this long and re-hidden every third of
    # it, so a crashed worker's job reappears within this window.
    JOB_VISIBILITY_TIMEOUT_SECONDS: int = 300
    # Clips cut (and burned) at once. 0 sizes it to the host's cores.
    CLIP_CUT_CONCURRENCY: int = 3

    # B-roll library. Pixabay stays off until its API caching terms are confirmed.
    BROLL_SOURCES: str = "pexels,nasa,wikimedia"
    PEXELS_API_KEY: str = ""
    PIXABAY_API_KEY: str = ""
    BROLL_S3_PREFIX: str = "broll"
    BROLL_MAX_DOWNLOAD_BYTES: int = 300 * 1024 * 1024
    BROLL_MIN_SHORT_SIDE: int = 720
    BROLL_MIN_SHOT_SECONDS: float = 2.0
    # "none" ranks by text only; "gemini" adds semantic similarity.
    EMBEDDINGS_PROVIDER: Literal["none", "gemini"] = "none"
    GEMINI_EMBEDDING_MODEL: str = "gemini-embedding-001"
    # Charged per clip that gets cutaways; covers the planner call and render.
    BROLL_CREDITS_PER_CLIP: int = 5

    # Reels from images. TTS: "none" (use an uploaded voiceover or captions only),
    # "groq" (English; accept Orpheus's terms in the Groq console) or "openai".
    TTS_PROVIDER: Literal["none", "groq", "openai"] = "none"
    OPENAI_TTS_MODEL: str = "gpt-4o-mini-tts"
    REEL_BASE_CREDITS: int = 10
    REEL_MAX_IMAGES_FREE: int = 5
    REEL_MAX_IMAGES_PRO: int = 30

    # Reels from raw footage (edit_engine/). Credits, per the margin notes in
    # edit_engine/pricing.py: base + 1 per EDIT_OUTPUT_SECONDS_PER_CREDIT seconds
    # of output + 1 per raw minute analysed; x1.5 while the Opus director is on.
    EDIT_BASE_CREDITS: int = 6
    EDIT_OUTPUT_SECONDS_PER_CREDIT: int = 3
    EDIT_OPUS_CREDIT_MULTIPLIER: float = 1.5
    # A re-render after edits reuses the analysis and plan: this share of the price.
    EDIT_RERENDER_SHARE: float = 0.25
    EDIT_MAX_RAW_SECONDS_FREE: int = 180
    EDIT_MAX_RAW_SECONDS_PRO: int = 1800
    EDIT_MAX_FILES_FREE: int = 10
    EDIT_MAX_FILES_PRO: int = 40
    EDIT_MAX_OUTPUT_SECONDS_FREE: int = 45
    EDIT_MAX_OUTPUT_SECONDS_PRO: int = 90
    # Director calls per reel after the first (each is a paid LLM call).
    EDIT_MAX_REPLANS: int = 3
    EDIT_MAX_CHAT_EDITS_FREE: int = 5
    EDIT_MAX_CHAT_EDITS_PRO: int = 30

    # AI-generated B-roll (Pro): Veo on the Gemini API, reusing GEMINI_API_KEY.
    VEO_MODEL: str = "veo-3.1-lite-generate-preview"
    VEO_RESOLUTION: Literal["720p", "1080p"] = "720p"
    VEO_SECONDS: Literal[4, 6, 8] = 8
    # 8 s of Lite 720p costs $0.40; 120 credits keeps ~60% margin at $0.0079 a credit.
    VEO_SCENE_CREDITS: int = 120

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

    TRANSCRIPTION_OUTPUT_DIR: str = "./transcription_outputs"
    HF_TOKEN: str = ""

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
