import io
import os
from typing import Literal
from urllib.parse import urlparse

from dotenv import dotenv_values
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from enum import Enum

# Servers keep no .env on disk: the service sets this to the S3 object holding
# their settings (an env file), read once per process with the machine's IAM
# role. Variables already in the environment win over the file.
CONFIG_S3_URI_VAR = "CLIPNERA_CONFIG_S3_URI"


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
    # How "auto" routes text steps. "openai": every step of every plan runs on
    # OPENAI_MODEL (Groq and Anthropic stay configured as fallbacks). "tiered":
    # the per-step policy in clients.ai.STEP_MODELS, Groq for free and
    # OpenAI for Pro. Switch back to "tiered" when OpenAI credits run out.
    LLM_ROUTING: Literal["openai", "tiered"] = "openai"
    # Exact models for single steps of Pro runs, "provider:model[:effort]", over the
    # routing above: the judgement steps run on GPT-6 Astra, the rest stay on OPENAI_MODEL.
    # {} puts every step back on the routing.
    LLM_PRO_STEP_MODELS: dict[str, str] = {
        "highlight_detection": "openai:gpt-6-astra-1:medium",
        "director": "openai:gpt-6-astra-1:medium",
        "motion_planning": "openai:gpt-6-astra-1:medium",
        "beat_planning": "openai:gpt-6-astra-1:medium",
    }

    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_ENDPOINT: str = ""
    # Reasoning effort for OpenAI reasoning models (gpt-5, o-series); models
    # without reasoning (gpt-4.1-mini, gpt-4o-mini) never receive it.
    OPENAI_REASONING_EFFORT: str = "high"
    # More deployments on OPENAI_ENDPOINT the studio's AI chat may pick, besides OPENAI_MODEL.
    OPENAI_MODELS: list[str] = ["gpt-5.6-sol-1", "gpt-6.1-sol-1", "gpt-6-astra-1"]
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-opus-5-5"
    # Thinking depth for steps without their own setting: low | medium | high | xhigh | max.
    ANTHROPIC_EFFORT: str = "high"
    # Models for the AI editor's roles (clients.ai.roles). "openai": every role on
    # OPENAI_MODEL. "anthropic": Haiku, Sonnet or Opus by role. "mixed": the
    # judgement roles (director, critic, judge) on Opus, the rest on OpenAI.
    LLM_PROFILE: Literal["openai", "anthropic", "mixed"] = "openai"
    # Per-role pins over the profile, as JSON: {"director": "anthropic:claude-opus-5-5"}.
    LLM_ROLE_MODELS: dict[str, str] = {}
    # Providers tried in order when a role's call fails on a rate limit, 5xx or timeout.
    # OpenAI only: a failed call errors instead of moving to another provider.
    LLM_FALLBACK: list[str] = ["openai"]
    # AI-editor credits (brain/credits.py) per Clipnera credit: a 30-credit plan costs 3 credits at 10.
    AI_CREDIT_RATE: int = 10
    # Evals (backend/evals): "record" saves every role call's reply as a cassette keyed by the
    # request's hash, "replay" answers from them with no API call. "live" in production.
    LLM_MODE: Literal["live", "record", "replay"] = "live"
    LLM_CASSETTE_DIR: str = "evals/cassettes"
    # Most a pipeline run may spend on AI, per minute of source video. At 80%
    # the remaining calls drop to low effort; at 100% they stop and the
    # heuristic fallbacks take over, so a video never ends up without clips.
    # 0 disables the cap.
    # Graphic beats for Pro clips (backend/beats): planned after clip generation,
    # rendered with headless Chrome at export. CHROME_PATH names the browser
    # binary (the renderer also looks in the usual places); MOTION_KIT_DIR the
    # clean asset kit (default backend/static/motion/kit).
    BEATS_ENABLED: bool = True
    CHROME_PATH: str = ""
    MOTION_KIT_DIR: str = ""
    # Image deployment at OPENAI_ENDPOINT that scripts/generate_kit_images.py makes the kit's own images with.
    IMAGE_MODEL: str = ""
    # Pro is sized for GPT-6 Astra ($10/$50 per Mtok) on the judgement steps.
    AI_BUDGET_PER_SOURCE_MINUTE_PRO: float = 0.06
    AI_BUDGET_PER_SOURCE_MINUTE_FREE: float = 0.002
    # Credits charged per minute of source video, rounded up per video with a
    # minimum of one credit.
    CREDITS_PER_VIDEO_MINUTE: float = 2.0
    # Each output ratio picked beyond the first adds this share of the base
    # cost. Rendering is a small part of a run next to transcription and AI
    # analysis, so an extra ratio costs a fraction, not a whole run.
    EXTRA_ASPECT_RATIO_CREDIT_SHARE: float = 0.5
    # Bonus credits refunded (a failed run) after their grant expired stay
    # spendable this many more days instead of being lost.
    BONUS_REFUND_GRACE_DAYS: int = 3
    XAI_API_KEY: str = ""
    XAI_MODEL: str = "grok-2-mini"
    GROQ_API_KEY: str = ""
    # llama-3.1-8b-instant and llama-3.3-70b-versatile were decommissioned on
    # 2026-08-16 and are Enterprise-only, so they are no longer usable defaults.
    GROQ_MODEL: str = "openai/gpt-oss-20b"
    # Reasoning effort asked of Groq's reasoning models: low | medium | high.
    # A call gets the highest effort up to this whose thinking allowance fits
    # the account's per-minute token limit (read from Groq's response
    # headers), so the free tier's 8K TPM still runs at low.
    GROQ_REASONING_EFFORT: str = "high"
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
    # SES identities are per region; empty means AWS_REGION.
    SES_REGION: str = ""
    LOCALSTACK_ENDPOINT: str = ""
    S3_BUCKET_NAME: str = "clipnera-videos"
    # Direct browser-to-S3 video uploads. S3 allows 5 MB-5 GB parts and at
    # most 10,000 of them; parts grow past the minimum only for huge files.
    UPLOAD_MIN_PART_BYTES: int = 16 * 1024 * 1024
    UPLOAD_MAX_BYTES: int = 10 * 1024 * 1024 * 1024
    UPLOAD_URL_TTL_SECONDS: int = 6 * 3600

    # Background jobs. "inprocess" runs them in the API process; "postgres"
    # queues them in the database and "sqs" sends them to SQS_JOBS_QUEUE_URL,
    # both for `python -m jobs.worker` processes to run.
    JOB_QUEUE_BACKEND: Literal["inprocess", "postgres", "sqs"] = "inprocess"
    SQS_JOBS_QUEUE_URL: str = ""
    JOB_WORKER_CONCURRENCY: int = 2
    # A running job's message is hidden this long and re-hidden every third of
    # it, so a crashed worker's job reappears within this window.
    JOB_VISIBILITY_TIMEOUT_SECONDS: int = 300
    # Postgres queue: a job whose handler keeps raising (or whose worker keeps
    # dying) is given up after this many attempts.
    JOB_MAX_ATTEMPTS: int = 3
    # Sleeping worker machine (EC2). The API starts WORKER_INSTANCE_ID while
    # jobs are waiting; a worker with WORKER_IDLE_SHUTDOWN_SECONDS > 0 powers
    # its machine off after that long with nothing to run. Both off by default.
    WORKER_INSTANCE_ID: str = ""
    WORKER_IDLE_SHUTDOWN_SECONDS: int = 0
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
    # Generated photos for reel inserts when no public-domain photo shows the thing said: "" (off), "gemini" (the
    # Gemini image model on GEMINI_API_KEY; needs billing on that Google project) or "openai" (IMAGE_MODEL at
    # OPENAI_ENDPOINT). Every image made is kept in the asset registry and reused.
    REEL_IMAGE_PROVIDER: Literal["", "gemini", "openai"] = ""
    GEMINI_IMAGE_MODEL: str = "gemini-2.5-flash-image"
    REEL_MAX_GENERATED_IMAGES: int = 3
    # Reels one premium edit may cut from a long video: one per strong moment, up to this many (each charged).
    REEL_MAX_REELS_FREE: int = 1
    REEL_MAX_REELS_PRO: int = 5

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
    # Speaker diarization runs in a child process, so torch and pyannote's
    # memory goes back to the OS when it ends. A run that takes longer than
    # this is stopped and the transcript keeps going without speaker labels.
    DIARIZATION_TIMEOUT_SECONDS: int = 600
    # Torch threads for that child; 0 means every core but one.
    DIARIZATION_THREADS: int = 0

    # yt-dlp cookies. A browser name ("chrome", "firefox") reads them live from
    # that browser and wins over the file; for the API machine, deploy.sh
    # exports them locally and copies them to YOUTUBE_COOKIES_PATH.
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


def load_remote_env() -> None:
    """Copy the env file at $CLIPNERA_CONFIG_S3_URI into os.environ, if set."""
    uri = os.environ.get(CONFIG_S3_URI_VAR)
    if not uri:
        return
    import boto3

    location = urlparse(uri)
    body = boto3.client("s3").get_object(Bucket=location.netloc, Key=location.path.lstrip("/"))["Body"].read()
    for key, value in dotenv_values(stream=io.StringIO(body.decode("utf-8"))).items():
        if value is not None:
            os.environ.setdefault(key, value)


@lru_cache
def get_settings() -> BaseConfig:
    load_remote_env()
    env = BaseConfig().ENVIRONMENT
    return CONFIG_MAP[env]()
