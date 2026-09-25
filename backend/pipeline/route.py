from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from auth.dependencies import CurrentUserDep
from clip_generation.schema import SocialExportRequest, SocialExportResponse
from clip_generation.service import ClipService
from pipeline.model import PipelineStepType, StepStatus
from pipeline.service import INTERRUPTED_ERROR, PipelineOrchestrator
from pipeline.repository import PipelineRepository
from clip.repository import ClipRepository
from clip.model import ProjectStatus
from core.logging_config import get_logger
from core.database import AsyncSessionLocal
from core.exceptions import CustomException
from subscription.service import SubscriptionService, pro_required

log = get_logger(__name__)

pipeline = APIRouter(prefix="/pipeline", tags=["pipeline"])

# Clip generation plus a burn-in pass so a default run yields captioned clips.
# Re-styling later goes through /subtitle-styling/burn/{clip_id}, which replaces
# the burned track with the style the user picks.
DEFAULT_PIPELINE_STEPS = [
    "audio_extraction",
    "ai_noise_cancellation",
    "transcription",
    "topic_research",
    "visual_analysis",
    "content_classification",
    "highlight_detection",
    "scoring",
    "metadata_generation",
    "aspect_ratio_render",
    "clip_generation",
    # Without this the pipeline produced clips with no captions at all, because
    # nothing else in a default run ever calls the burner.
    "burn_in_export",
]

# Steps the orchestrator can actually run. A request naming anything else --
# the UI has long sent "bounding_box_detection", which has no handler -- would
# otherwise get a step row that stays "pending" forever, leaving a stuck entry
# in the UI and holding overall progress below 100% for the whole run.
RUNNABLE_PIPELINE_STEPS = {
    PipelineStepType.AUDIO_EXTRACTION,
    PipelineStepType.AI_NOISE_CANCELLATION,
    PipelineStepType.TRANSCRIPTION,
    PipelineStepType.TOPIC_RESEARCH,
    PipelineStepType.VISUAL_ANALYSIS,
    PipelineStepType.CONTENT_CLASSIFICATION,
    PipelineStepType.HIGHLIGHT_DETECTION,
    PipelineStepType.SCORING,
    PipelineStepType.METADATA_GENERATION,
    PipelineStepType.ASPECT_RATIO_RENDER,
    PipelineStepType.CLIP_GENERATION,
    PipelineStepType.SUBTITLE_STYLING,
    PipelineStepType.BURN_IN_EXPORT,
    PipelineStepType.DEPTH_CAPTIONS,
}


def _resolve_steps(requested: list[str]) -> list[PipelineStepType]:
    """Map requested step names onto the steps the orchestrator implements."""
    resolved: list[PipelineStepType] = []
    for name in requested:
        try:
            step = PipelineStepType.resolve(name)
        except ValueError:
            log.warning("Ignoring unknown pipeline step requested by client: %s", name)
            continue
        if step not in RUNNABLE_PIPELINE_STEPS:
            log.info("Ignoring pipeline step with no handler: %s", step.value)
            continue
        if step not in resolved:
            resolved.append(step)
    if not resolved:
        raise CustomException(
            message="No runnable pipeline steps were requested.",
            code="NO_RUNNABLE_STEPS",
            status_code=400,
        )
    return resolved


def _apply_entitlements(
    entitlements,
    output_aspect_ratios: list[str],
    watermark_enabled: bool,
    clip_settings: dict | None,
) -> tuple[list[str], bool, dict | None]:
    """Clamp a run request to what the caller's plan permits.

    Enforced here rather than only in the UI, because hiding a control does not
    stop a crafted request. Over-reach is clamped rather than rejected, so a
    downgraded user's existing presets keep working at their new tier instead of
    erroring; an outright unusable request (no permitted ratio) still raises.
    """
    # An empty request means "decide from the content category later", which is
    # not over-reach and must not 403; the renderer clamps its own choice to the
    # plan. Only a request that named ratios, none of them permitted, is refused.
    if not output_aspect_ratios:
        return [], (True if entitlements.watermark_forced else watermark_enabled), _clamp_clip_settings(
            entitlements, clip_settings
        )

    allowed_ratios = permitted_aspect_ratios(entitlements, output_aspect_ratios)

    # A forced watermark cannot be switched off by the client.
    effective_watermark = True if entitlements.watermark_forced else watermark_enabled

    return allowed_ratios, effective_watermark, _clamp_clip_settings(entitlements, clip_settings)


def permitted_aspect_ratios(entitlements, requested: list[str]) -> list[str]:
    """The requested ratios the plan covers; 403 if it covers none of them."""
    allowed_ratios = [r for r in requested if entitlements.allows_aspect_ratio(r)]
    if not allowed_ratios:
        raise CustomException(
            message=(
                f"Your {entitlements.plan} plan supports "
                f"{', '.join(entitlements.aspect_ratios)}. Upgrade to export other formats."
            ),
            code="ASPECT_RATIO_NOT_ENTITLED",
            status_code=403,
        )
    if len(allowed_ratios) != len(requested):
        log.info(
            "Dropped aspect ratios not covered by plan %s: %s",
            entitlements.plan,
            sorted(set(requested) - set(allowed_ratios)),
        )
    return allowed_ratios


def _clamp_clip_settings(entitlements, clip_settings: dict | None) -> dict:
    """Clamp clip count to the plan's cap and refuse styles it does not include."""
    settings = dict(clip_settings or {})
    requested_clips = settings.get("max_clips")
    cap = entitlements.max_clips_per_video
    if not isinstance(requested_clips, int) or requested_clips <= 0:
        settings["max_clips"] = cap
    else:
        settings["max_clips"] = min(requested_clips, cap)

    style = settings.get("caption_style") or settings.get("style_type")
    if style and not entitlements.allows_caption_style(str(style)):
        raise CustomException(
            message=(
                f"The '{style}' caption style requires a paid plan. "
                "Upgrade to unlock the full caption library."
            ),
            code="CAPTION_STYLE_NOT_ENTITLED",
            status_code=403,
        )
    return settings


def _resolve_aspect_ratios(raw: Any) -> list[str]:
    """Validate the requested output formats; empty means "let the pipeline pick".

    An empty list is passed through rather than filled in here, so the renderer
    can choose from the video's content category -- naming every ratio at this
    point rendered four files per clip for content published in one shape. A
    client that does name ratios still gets exactly those.
    """
    from video_processor.geometry import SUPPORTED_ASPECT_RATIOS

    if isinstance(raw, str):
        raw = [item.strip() for item in raw.split(",")]
    if not isinstance(raw, list) or not raw:
        return []

    resolved: list[str] = []
    for item in raw:
        ratio = str(item).strip()
        if ratio in SUPPORTED_ASPECT_RATIOS and ratio not in resolved:
            resolved.append(ratio)
        elif ratio and ratio not in SUPPORTED_ASPECT_RATIOS:
            log.warning("Ignoring unsupported aspect ratio: %s", ratio)
    return resolved


DEFAULT_AUDIO_CONFIG = {
    "ai_denoise": True,
    "noise_suppression_strength": 90,
    "de_reverb": True,
    "vocal_clarity_eq": True,
    "hum_filter": True,
}

_progress_store: dict[str, dict[str, Any]] = {}
_active_orchestrators: dict[str, PipelineOrchestrator] = {}
# The event loop only weakly references tasks; an unreferenced run can be
# garbage-collected mid-flight and vanish without ever recording an outcome.
_background_tasks: set[asyncio.Task] = set()
_progress_lock = asyncio.Lock()
_semaphore = asyncio.Semaphore(10)


def _progress_callback_factory(project_id: str):
    async def callback(message: str, percent: int, _: str | None, step: str | None = None, step_status: str | None = None) -> None:
        async with _progress_lock:
            entry = _progress_store.get(project_id, {"status": "idle", "percent": 0, "message": ""})
            entry["message"] = message
            entry["percent"] = percent
            entry["status"] = "running"
            if step:
                entry["current_step"] = step
            if step_status:
                entry["step_status"] = step_status
            _progress_store[project_id] = entry
    return callback


async def _run_pipeline(orchestrator: PipelineOrchestrator, project_id: str, user: dict | None = None, credit_refund_callback=None) -> None:
    try:
        results = await orchestrator.run()
        if orchestrator.is_cancelled:
            async with _progress_lock:
                entry = _progress_store.get(project_id, {"percent": 0, "message": ""})
                entry.update({"status": "cancelled", "message": "Pipeline cancelled by user", "step_status": "cancelled"})
                _progress_store[project_id] = entry
            return
        async with _progress_lock:
            entry = _progress_store.get(project_id, {"status": "idle", "percent": 0, "message": ""})
            entry.update({"status": "completed", "percent": 100, "message": "Pipeline completed", "step_status": "completed"})
            _progress_store[project_id] = entry

        if user and (user.get("email") or user.get("phone")):
            from notifications.service import NotificationService
            notifier = NotificationService()
            clip_count = None
            gen_result = results.get("clip_generation") or results.get("metadata_generation")
            if gen_result:
                clips = gen_result.get("clips") or []
                if isinstance(clips, list):
                    clip_count = len(clips)
            await notifier.notify_pipeline_complete(
                user_email=user.get("email"),
                user_phone=user.get("phone"),
                project_id=project_id,
                success=True,
                clip_count=clip_count,
            )
    except asyncio.CancelledError:
        # Raised when the server shuts down mid-run. It is not an Exception, so
        # the handler below never saw it and the run stayed "running" forever.
        log.warning(f"Pipeline interrupted: project={project_id}")
        await orchestrator._mark_pipeline_failed(INTERRUPTED_ERROR)
        if credit_refund_callback:
            await credit_refund_callback()
        raise
    except Exception as exc:
        log.error(f"Pipeline failed: project={project_id} error={exc}")
        async with _progress_lock:
            entry = _progress_store.get(project_id, {"status": "idle", "percent": 0, "message": ""})
            entry.update({"status": "error", "percent": 0, "message": str(exc), "step_status": "failed"})
            _progress_store[project_id] = entry

        # orchestrator.run() persists the failure itself, but it can also raise
        # before reaching that point (or while persisting) — make sure the DB
        # reflects the failure so /status does not report a stale running job.
        try:
            await orchestrator._mark_pipeline_failed(str(exc))
        except Exception as mark_exc:
            log.error(f"Could not persist pipeline failure: project={project_id} error={mark_exc}")

        if credit_refund_callback:
            await credit_refund_callback()

        if user:
            from notifications.service import NotificationService
            notifier = NotificationService()
            await notifier.notify_pipeline_complete(
                user_email=user.get("email"),
                user_phone=user.get("phone"),
                project_id=project_id,
                success=False,
                error=str(exc),
            )
    finally:
        _active_orchestrators.pop(project_id, None)


def _launch_pipeline(orchestrator: PipelineOrchestrator, project_id: str, user: dict, credit_refund_callback) -> None:
    _active_orchestrators[project_id] = orchestrator
    task = asyncio.create_task(
        _run_pipeline(orchestrator, project_id, user=user, credit_refund_callback=credit_refund_callback)
    )
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


@pipeline.post("/start/{project_id}")
async def start_pipeline(project_id: str, user: CurrentUserDep, body: dict | None = None):
    async with AsyncSessionLocal() as session:
        clip_repo = ClipRepository(session)
        pipeline_repo = PipelineRepository(session)

        project = await clip_repo.get_project(project_id, user["user_id"])
        if not project:
            raise CustomException(message="Project not found", code="NOT_FOUND", status_code=404)

        if project.status != ProjectStatus.UPLOADED or not project.duration_seconds:
            raise CustomException(
                message="Video download and metadata save are not complete yet. Please wait for the upload to finish.",
                code="VIDEO_NOT_READY",
                status_code=409,
            )

        body = body or {}
        # Subtitles are burned at export time from the style the user picks, so
        # caption steps are deliberately absent from the default run.
        selected_steps = _resolve_steps(body.get("steps", DEFAULT_PIPELINE_STEPS))
        output_aspect_ratios = _resolve_aspect_ratios(body.get("output_aspect_ratios"))
        audio_config = body.get("audio_config", DEFAULT_AUDIO_CONFIG)
        watermark_enabled = body.get("watermark_enabled", True)
        clip_settings = body.get("clip_settings") if isinstance(body.get("clip_settings"), dict) else None

        subscription_service = SubscriptionService.for_session(session)

        # Which AI provider this run uses. Resolved once, here, so the whole
        # run is consistent even if the plan changes while it is in flight.
        entitlements = await subscription_service.get_entitlements(user["user_id"])
        is_pro = entitlements.pro_ai_provider
        log.info(
            "Pipeline provider tier resolved: project=%s user=%s plan=%s is_pro=%s",
            project_id, user["user_id"], entitlements.plan, is_pro,
        )

        output_aspect_ratios, watermark_enabled, clip_settings = _apply_entitlements(
            entitlements, output_aspect_ratios, watermark_enabled, clip_settings
        )

        duration_seconds = project.duration_seconds or 0
        if duration_seconds <= 0:
            raise CustomException(message="Video duration not available. Please wait for download to complete.", code="DURATION_UNAVAILABLE", status_code=400)
        if duration_seconds > entitlements.max_upload_duration_seconds:
            raise CustomException(
                message=(
                    f"This video is {duration_seconds // 60} minutes. Your {entitlements.plan} plan "
                    f"supports up to {entitlements.max_upload_duration_seconds // 60} minutes per video."
                ),
                code="DURATION_NOT_ENTITLED",
                status_code=403,
            )

        credit_cost = subscription_service.calculate_video_credit_cost(duration_seconds)
        try:
            await subscription_service.deduct_credits(
                user_id=user["user_id"],
                amount=credit_cost,
                reason=f"Video processing: {duration_seconds}s",
                reference_id=project_id,
                reference_type="video_project",
            )
        except Exception as exc:
            raise CustomException(message=str(exc), code="INSUFFICIENT_CREDITS", status_code=402)

        async def refund_credits():
            async with AsyncSessionLocal() as refund_session:
                refund_service = SubscriptionService.for_session(refund_session)
                try:
                    await refund_service.refund_credits(
                        user_id=user["user_id"],
                        amount=credit_cost,
                        reason=f"Pipeline failed, refunding credits for project {project_id}",
                        reference_id=project_id,
                        reference_type="video_project_refund",
                    )
                except Exception as refund_exc:
                    log.error(f"Credit refund failed: project={project_id} error={refund_exc}")

        # After the charge, so a refused charge leaves no run that looks in progress.
        try:
            await pipeline_repo.create_pipeline(project_id, selected_steps)
        except Exception:
            await refund_credits()
            raise

        orchestrator = PipelineOrchestrator(
            project_id=project_id,
            user_id=user["user_id"],
            url=project.source_url or "",
            selected_steps=selected_steps,
            audio_config=audio_config,
            progress_callback=_progress_callback_factory(project_id),
            watermark_enabled=watermark_enabled,
            output_aspect_ratios=output_aspect_ratios,
            clip_settings=clip_settings,
            is_pro=is_pro,
        )

        _launch_pipeline(orchestrator, project_id, user, refund_credits)

        return {
            "project_id": project_id,
            "status": "started",
            "selected_steps": [s.value for s in selected_steps],
            "output_aspect_ratios": output_aspect_ratios,
            "watermark_enabled": watermark_enabled,
            "credits_deducted": credit_cost,
            "is_pro": is_pro,
        }


@pipeline.post("/cancel/{project_id}")
async def cancel_pipeline(project_id: str, user: CurrentUserDep):
    async with AsyncSessionLocal() as session:
        project = await ClipRepository(session).get_project(project_id, user["user_id"])
        if not project:
            raise CustomException(message="Project not found", code="NOT_FOUND", status_code=404)

    orchestrator = _active_orchestrators.get(project_id)
    if not orchestrator:
        raise CustomException(message="No active pipeline found", code="PIPELINE_NOT_RUNNING", status_code=409)
    orchestrator.cancel()
    async with _progress_lock:
        entry = _progress_store.get(project_id, {"percent": 0, "message": ""})
        entry.update({"status": "cancelled", "message": "Pipeline cancelled by user", "step_status": "cancelled"})
        _progress_store[project_id] = entry
    return {"project_id": project_id, "status": "cancelled"}


@pipeline.get("/progress/{project_id}")
async def pipeline_progress(project_id: str, user: CurrentUserDep):
    async def event_stream():
        while True:
            async with _progress_lock:
                data = dict(_progress_store.get(project_id, {"status": "idle", "percent": 0, "message": ""}))
            yield f"data: {json.dumps(data)}\n\n"
            if data.get("status") in ("completed", "error", "cancelled"):
                break
            await asyncio.sleep(1)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


def _serialize_step(log_entry) -> dict[str, Any]:
    return {
        "step": log_entry.step,
        "status": log_entry.status,
        "progress_percent": log_entry.progress_percent,
        "message": log_entry.message,
        "artifact_path": log_entry.artifact_path,
        "started_at": log_entry.started_at.isoformat() if log_entry.started_at else None,
        "finished_at": log_entry.finished_at.isoformat() if log_entry.finished_at else None,
    }


def _overall_status(state, steps: list[dict[str, Any]]) -> str:
    if state.error:
        return "error"
    if state.is_completed:
        return "completed"
    if any(s["status"] == "running" for s in steps):
        return "running"
    return "pending"


@pipeline.post("/status/batch")
async def pipeline_status_batch(body: dict[str, Any], user: CurrentUserDep):
    """Status for many projects in one round trip.

    The dashboard previously issued one GET /status/{id} per project on load.
    Those calls share a semaphore and a 15-connection pool, so a user with a
    dozen projects queued them and every other request -- including the ones
    behind a button click -- waited on the pool. This answers the whole list
    with three queries regardless of project count.
    """
    project_ids = body.get("project_ids") or []
    if not isinstance(project_ids, list):
        raise CustomException(message="project_ids must be a list", code="INVALID_BODY", status_code=400)
    project_ids = [str(pid) for pid in project_ids][:200]
    if not project_ids:
        return {"statuses": {}}

    async with AsyncSessionLocal() as session:
        clip_repo = ClipRepository(session)
        pipeline_repo = PipelineRepository(session)

        owned = await clip_repo.list_projects(user["user_id"])
        owned_ids = {p.id for p in owned} & set(project_ids)
        if not owned_ids:
            return {"statuses": {}}

        states = await pipeline_repo.get_latest_pipelines(list(owned_ids))
        logs_by_pipeline = await pipeline_repo.get_step_logs_for_pipelines(
            [state.id for state in states.values()]
        )

        statuses: dict[str, Any] = {}
        for project_id in owned_ids:
            state = states.get(project_id)
            if not state:
                statuses[project_id] = {"project_id": project_id, "status": "not_started", "steps": []}
                continue
            steps = [_serialize_step(entry) for entry in logs_by_pipeline.get(state.id, [])]
            statuses[project_id] = {
                "project_id": project_id,
                "status": _overall_status(state, steps),
                "current_step": state.current_step,
                "is_completed": state.is_completed,
                "error": state.error,
                "steps": steps,
            }
        return {"statuses": statuses}


@pipeline.get("/status/{project_id}")
async def pipeline_status(project_id: str, user: CurrentUserDep):
    async with _semaphore:
        try:
            async with AsyncSessionLocal() as session:
                pipeline_repo = PipelineRepository(session)
                clip_repo = ClipRepository(session)

                project = await clip_repo.get_project(project_id, user["user_id"])
                if not project:
                    return {"project_id": project_id, "status": "not_started", "steps": []}

                state = await pipeline_repo.get_pipeline(project_id)
                if not state:
                    return {"project_id": project_id, "status": "not_started", "steps": []}

                logs = await pipeline_repo.get_step_logs(state.id)
                steps = []
                for log_entry in logs:
                    steps.append({
                        "step": log_entry.step,
                        "status": log_entry.status,
                        "progress_percent": log_entry.progress_percent,
                        "message": log_entry.message,
                        "artifact_path": log_entry.artifact_path,
                        "started_at": log_entry.started_at.isoformat() if log_entry.started_at else None,
                        "finished_at": log_entry.finished_at.isoformat() if log_entry.finished_at else None,
                    })

                if state.error:
                    overall = "error"
                elif state.is_completed:
                    overall = "completed"
                elif any(s["status"] == "running" for s in steps):
                    overall = "running"
                else:
                    overall = "pending"

                return {
                    "project_id": project_id,
                    "status": overall,
                    "current_step": state.current_step,
                    "is_completed": state.is_completed,
                    "error": state.error,
                    "steps": steps,
                }
        except Exception as exc:
            log.error(f"Pipeline status failed: project={project_id} error={exc}")
            return {
                "project_id": project_id,
                "status": "error",
                "error": str(exc),
                "steps": [],
            }


@pipeline.post("/revert/{project_id}/{step}")
async def revert_step(project_id: str, step: str, user: CurrentUserDep):
    async with AsyncSessionLocal() as session:
        pipeline_repo = PipelineRepository(session)
        clip_repo = ClipRepository(session)

        project = await clip_repo.get_project(project_id, user["user_id"])
        if not project:
            raise CustomException(message="Project not found", code="NOT_FOUND", status_code=404)

        try:
            step_enum = PipelineStepType.resolve(step)
        except ValueError:
            raise CustomException(message=f"Invalid step: {step}", code="INVALID_STEP", status_code=400)

        state = await pipeline_repo.get_pipeline(project_id)
        if not state:
            raise CustomException(message="Pipeline not found", code="NOT_FOUND", status_code=404)

        await pipeline_repo.mark_step_reverted(state.id, step_enum)

        if step_enum == PipelineStepType.AI_NOISE_CANCELLATION:
            await pipeline_repo.save_artifact(state.id, step_enum, project.presigned_url or "")

        await pipeline_repo.update_pipeline_current_step(project_id, step_enum)

        return {"project_id": project_id, "step": step, "status": "reverted"}


@pipeline.post("/resume/{project_id}")
async def resume_pipeline(project_id: str, user: CurrentUserDep, body: dict | None = None):
    async with AsyncSessionLocal() as session:
        pipeline_repo = PipelineRepository(session)
        clip_repo = ClipRepository(session)

        project = await clip_repo.get_project(project_id, user["user_id"])
        if not project:
            raise CustomException(message="Project not found", code="NOT_FOUND", status_code=404)

        state = await pipeline_repo.get_pipeline(project_id)
        if not state:
            raise CustomException(message="Pipeline not found", code="NOT_FOUND", status_code=404)

        body = body or {}
        selected_steps = _resolve_steps(body.get("steps", DEFAULT_PIPELINE_STEPS))
        output_aspect_ratios = _resolve_aspect_ratios(body.get("output_aspect_ratios"))
        audio_config = body.get("audio_config", DEFAULT_AUDIO_CONFIG)
        watermark_enabled = body.get("watermark_enabled", True)
        clip_settings = body.get("clip_settings") if isinstance(body.get("clip_settings"), dict) else None

        subscription_service = SubscriptionService.for_session(session)

        entitlements = await subscription_service.get_entitlements(user["user_id"])
        is_pro = entitlements.pro_ai_provider
        output_aspect_ratios, watermark_enabled, clip_settings = _apply_entitlements(
            entitlements, output_aspect_ratios, watermark_enabled, clip_settings
        )

        duration_seconds = project.duration_seconds or 0
        if duration_seconds <= 0:
            raise CustomException(message="Video duration not available.", code="DURATION_UNAVAILABLE", status_code=400)
        if duration_seconds > entitlements.max_upload_duration_seconds:
            raise CustomException(
                message=(
                    f"This video is {duration_seconds // 60} minutes. Your {entitlements.plan} plan "
                    f"supports up to {entitlements.max_upload_duration_seconds // 60} minutes per video."
                ),
                code="DURATION_NOT_ENTITLED",
                status_code=403,
            )

        credit_cost = subscription_service.calculate_video_credit_cost(duration_seconds)
        try:
            await subscription_service.deduct_credits(
                user_id=user["user_id"],
                amount=credit_cost,
                reason=f"Video processing (resume): {duration_seconds}s",
                reference_id=project_id,
                reference_type="video_project_resume",
            )
        except Exception as exc:
            raise CustomException(message=str(exc), code="INSUFFICIENT_CREDITS", status_code=402)

        async def refund_credits():
            async with AsyncSessionLocal() as refund_session:
                refund_service = SubscriptionService.for_session(refund_session)
                try:
                    await refund_service.refund_credits(
                        user_id=user["user_id"],
                        amount=credit_cost,
                        reason=f"Pipeline failed (resume), refunding credits for project {project_id}",
                        reference_id=project_id,
                        reference_type="video_project_refund",
                    )
                except Exception as refund_exc:
                    log.error(f"Credit refund failed: project={project_id} error={refund_exc}")

        # Clients read either field as "failed", so a resumed run that kept them
        # showed as failed throughout, and even after it succeeded.
        state.error = None
        await session.commit()
        await clip_repo.update_project_status(project_id, ProjectStatus.PROCESSING)

        orchestrator = PipelineOrchestrator(
            project_id=project_id,
            user_id=user["user_id"],
            url=project.source_url or "",
            selected_steps=selected_steps,
            audio_config=audio_config,
            progress_callback=_progress_callback_factory(project_id),
            watermark_enabled=watermark_enabled,
            output_aspect_ratios=output_aspect_ratios,
            clip_settings=clip_settings,
            is_pro=is_pro,
            resume=True,
        )

        _launch_pipeline(orchestrator, project_id, user, refund_credits)

        return {
            "project_id": project_id,
            "status": "resumed",
            "selected_steps": [s.value for s in selected_steps],
            "output_aspect_ratios": output_aspect_ratios,
            "watermark_enabled": watermark_enabled,
            "credits_deducted": credit_cost,
            "is_pro": is_pro,
        }


@pipeline.get("/social-platforms")
async def list_social_platforms():
    from clip_generation.model import SocialPlatform, SOCIAL_PLATFORM_DEFAULTS

    platforms = []
    for platform in SocialPlatform:
        defaults = SOCIAL_PLATFORM_DEFAULTS[platform.value]
        platforms.append({
            "platform": platform.value,
            "aspect_ratio": defaults["aspect_ratio"],
            "dimensions": defaults["dimensions"],
            "default_style": defaults["subtitle_style"],
            "max_duration": defaults["max_duration"],
            "emoji_enabled": defaults["emoji_enabled"],
        })
    return {"platforms": platforms}


def _check_export_entitlements(entitlements, request: SocialExportRequest) -> None:
    """Refuse an export the plan does not cover.

    Checked here as well as in the editor, which only hides locked options; the
    endpoint is reachable directly.
    """
    from clip_generation.model import SOCIAL_PLATFORM_DEFAULTS
    from video_processor.geometry import SUPPORTED_ASPECT_RATIOS

    if request.aspect_ratio and request.aspect_ratio not in SUPPORTED_ASPECT_RATIOS:
        raise CustomException(
            message=f"Unsupported aspect ratio: {request.aspect_ratio}",
            code="INVALID_ASPECT_RATIO",
            status_code=400,
        )
    ratios = (
        {request.aspect_ratio}
        if request.aspect_ratio
        else {
            SOCIAL_PLATFORM_DEFAULTS[p.lower()]["aspect_ratio"]
            for p in request.platforms
            if p.lower() in SOCIAL_PLATFORM_DEFAULTS
        }
    )
    if any(not entitlements.allows_aspect_ratio(r) for r in ratios):
        raise CustomException(
            message=(
                f"Your {entitlements.plan} plan supports "
                f"{', '.join(entitlements.aspect_ratios)}. Upgrade to export other formats."
            ),
            code="ASPECT_RATIO_NOT_ENTITLED",
            status_code=403,
        )
    if request.style_type and not entitlements.allows_caption_style(request.style_type):
        raise CustomException(
            message=(
                f"The '{request.style_type}' caption style requires a paid plan. "
                "Upgrade to unlock the full caption library."
            ),
            code="CAPTION_STYLE_NOT_ENTITLED",
            status_code=403,
        )
    if request.hook_transition and not entitlements.allows_hook_transition(request.hook_transition.mode):
        raise pro_required("all_hook_transitions")


@pipeline.post("/export/{project_id}", response_model=SocialExportResponse)
async def export_clips_for_social(project_id: str, request: SocialExportRequest, user: CurrentUserDep):
    async with AsyncSessionLocal() as session:
        clip_repo = ClipRepository(session)
        project = await clip_repo.get_project(project_id, user["user_id"])
        if not project:
            raise CustomException(message="Project not found", code="NOT_FOUND", status_code=404)
        subscription_service = SubscriptionService.for_session(session)
        entitlements = await subscription_service.get_entitlements(user["user_id"])
        _check_export_entitlements(entitlements, request)
        # Each exported clip counts toward the daily export limit.
        await subscription_service.consume_daily_quota(
            user["user_id"], "exports", len(request.clip_ids) if request.clip_ids else max(1, request.max_clips or 1)
        )

    # A forced watermark cannot be switched off by the client.
    watermark_enabled = request.watermark_enabled or entitlements.watermark_forced

    service = ClipService()
    result = await service.export_clips_for_social(
        project_id=project_id,
        user_id=user["user_id"],
        platforms=request.platforms,
        clip_ids=request.clip_ids,
        aspect_ratio=request.aspect_ratio,
        style_type=request.style_type,
        custom_config=request.custom_config,
        max_clips=request.max_clips,
        max_duration_override=request.max_duration,
        enable_emoji=request.enable_emoji,
        watermark_enabled=watermark_enabled,
        burn_subtitles=request.burn_subtitles,
        animation_speed=request.animation_speed,
        hook_transition=request.hook_transition,
    )
    return result
