from auth.route import auth as auth_router
from notifications.route import notification as notification_router
from clip.route import clip as clip_router
from workspace.route import router as workspace_router
from user.route import router as user_router
from audio.enhancement.route import audio as audio_router
from audio.extraction.route import extraction as extraction_router
from transcription.route import transcription as transcription_router
from pipeline.route import pipeline as pipeline_router
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from core import get_settings, register_middlewares
from core.exceptions import CustomException
from core.logging_config import setup_logging, get_logger

setup_logging()
settings = get_settings()
log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    # try:
    #     from migrate import run_migrations
    #     await run_migrations()
    #     log.info("Database migrations applied")
    # except Exception as exc:
    #     log.warning(f"Migration skipped: {exc}")
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
app.include_router(auth_router, prefix="/api/v1")
app.include_router(notification_router, prefix="/api/v1")
app.include_router(clip_router, prefix="/api/v1")
app.include_router(workspace_router, prefix="/api/v1")
app.include_router(user_router, prefix="/api/v1")
app.include_router(audio_router, prefix="/api/v1")
app.include_router(extraction_router, prefix="/api/v1")
app.include_router(transcription_router, prefix="/api/v1")
app.include_router(pipeline_router, prefix="/api/v1")


@app.exception_handler(CustomException)
async def custom_exception_handler(request: Request, exc: CustomException):
    log.warning(f"CustomException: {exc.code} - {exc.message}")
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.to_dict(),
    )


@app.get("/health", tags=["health"])
async def health_check():
    return {"status": "ok", "app": settings.APP_NAME, "version": settings.APP_VERSION}
