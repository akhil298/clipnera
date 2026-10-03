from analytics.route import analytics as analytics_router
from auth.route import auth as auth_router
from notifications.route import notification as notification_router
from clip.route import clip as clip_router
from workspace.route import router as workspace_router
from user.route import router as user_router
from audio.enhancement.route import audio as audio_router
from audio.extraction.route import extraction as extraction_router
from transcription.route import transcription as transcription_router
from pipeline.route import pipeline as pipeline_router
from pipeline.service import fail_interrupted_pipelines
from brand_kit.route import brand_kit as brand_kit_router
from clip_generation.route import clip_generation as clip_generation_router
from subtitle_styling.route import subtitle_styling as subtitle_styling_router
from subscription.route import router as subscription_router
from payment.route import payments as payments_router, admin_payments as admin_payments_router
from admin.route import admin as admin_router
from depth_captions.route import depth_captions as depth_captions_router
from hook_transitions.route import hook_transitions as hook_transitions_router
from feature_flags.engine import flags
from feature_flags.route import (
    features as features_router, admin_features as admin_features_router, flags_router,
    admin_flags as admin_flags_router, admin_config as admin_config_router, admin_segments as admin_segments_router,
)
from usage.route import usage as usage_router, admin_usage as admin_usage_router
from feedback.route import admin_quality as admin_quality_router
from social.route import social as social_router, social_webhooks as social_webhooks_router, admin_social as admin_social_router
from social.worker import running_in_background as social_worker
from uploads.route import uploads as uploads_router
from broll.route import admin_broll as admin_broll_router, broll as broll_router
from reels.route import reels_router
from creator_intro.route import creator_intro_router
from edit_engine.route import edits as edits_router, admin_music as admin_music_router
from editor.route import editor as editor_router
from video_processor.ffmpeg_service import FFmpegService
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from core import get_settings, register_middlewares
from core.exceptions import CustomException
from core.rate_limit import no_rate_limit
from core.logging_config import setup_logging, get_logger

setup_logging()
settings = get_settings()
log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    try:
        await fail_interrupted_pipelines()
    except Exception as exc:
        log.error(f"Could not recover interrupted pipelines: {exc}", exc_info=True)
    try:
        await FFmpegService.require_caption_support()
    except CustomException as exc:
        log.error(f"{exc.message} Exports will fail until FFmpeg with libass is installed.")
    # Flag snapshot, LISTEN for changes and the 15 s poll; checks then cost no queries.
    await flags.start()
    try:
        # Publishes posts and ends connections past their 7-day lifetime.
        async with social_worker():
            yield
            log.info("Shutting down")
    finally:
        await flags.stop()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    debug=settings.APP_DEBUG,
    lifespan=lifespan,
    docs_url="/docs" if settings.APP_DEBUG else None,
    redoc_url="/redoc" if settings.APP_DEBUG else None,
)

register_middlewares(app)
Path(settings.CLIP_OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
app.mount("/static/clips", StaticFiles(directory=settings.CLIP_OUTPUT_DIR), name="clips")
app.include_router(auth_router, prefix="/api/v1")
app.include_router(notification_router, prefix="/api/v1")
app.include_router(analytics_router, prefix="/api/v1")
app.include_router(clip_router, prefix="/api/v1")
app.include_router(clip_generation_router, prefix="/api/v1")
app.include_router(subtitle_styling_router, prefix="/api/v1")
app.include_router(workspace_router, prefix="/api/v1")
app.include_router(user_router, prefix="/api/v1")
app.include_router(audio_router, prefix="/api/v1")
app.include_router(extraction_router, prefix="/api/v1")
app.include_router(transcription_router, prefix="/api/v1")
app.include_router(pipeline_router, prefix="/api/v1")
app.include_router(brand_kit_router, prefix="/api/v1")
app.include_router(subscription_router, prefix="/api/v1")
app.include_router(payments_router, prefix="/api/v1")
app.include_router(admin_payments_router, prefix="/api/v1")
app.include_router(admin_router, prefix="/api/v1")
app.include_router(usage_router, prefix="/api/v1")
app.include_router(admin_usage_router, prefix="/api/v1")
app.include_router(admin_quality_router, prefix="/api/v1")
app.include_router(depth_captions_router, prefix="/api/v1")
app.include_router(hook_transitions_router, prefix="/api/v1")
app.include_router(features_router, prefix="/api/v1")
app.include_router(admin_features_router, prefix="/api/v1")
app.include_router(flags_router, prefix="/api/v1")
app.include_router(admin_flags_router, prefix="/api/v1")
app.include_router(admin_config_router, prefix="/api/v1")
app.include_router(admin_segments_router, prefix="/api/v1")
app.include_router(social_router, prefix="/api/v1")
app.include_router(social_webhooks_router, prefix="/api/v1")
app.include_router(admin_social_router, prefix="/api/v1")
app.include_router(uploads_router, prefix="/api/v1")
app.include_router(admin_broll_router, prefix="/api/v1")
app.include_router(broll_router, prefix="/api/v1")
app.include_router(reels_router, prefix="/api/v1")
app.include_router(creator_intro_router, prefix="/api/v1")
app.include_router(edits_router, prefix="/api/v1")
app.include_router(admin_music_router, prefix="/api/v1")
app.include_router(editor_router, prefix="/api/v1")


@app.exception_handler(CustomException)
async def custom_exception_handler(request: Request, exc: CustomException):
    log.warning(f"CustomException: {exc.code} - {exc.message}")
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.to_dict(),
    )


@app.exception_handler(TimeoutError)
async def timeout_error_handler(request: Request, exc: TimeoutError):
    log.error(f"Database timeout: {exc}")
    return JSONResponse(
        status_code=503,
        content={"error": "SERVICE_UNAVAILABLE", "message": "Database connection timeout. Please try again later."},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    log.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "INTERNAL_ERROR", "message": "An unexpected error occurred."},
    )


@app.get("/health", tags=["health"])
@no_rate_limit
async def health_check():
    return {"status": "ok", "app": settings.APP_NAME, "version": settings.APP_VERSION}
