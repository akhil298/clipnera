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
from depth_captions.route import depth_captions as depth_captions_router
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from core import get_settings, register_middlewares
from core.exceptions import CustomException
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
    yield
    log.info("Shutting down")


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
app.include_router(depth_captions_router, prefix="/api/v1")


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
async def health_check():
    return {"status": "ok", "app": settings.APP_NAME, "version": settings.APP_VERSION}
