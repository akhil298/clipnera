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
from pipeline.service import PipelineOrchestrator
from pipeline.repository import PipelineRepository
from clip.repository import ClipRepository
from core.logging_config import get_logger
from core.database import AsyncSessionLocal
from core.exceptions import CustomException
from subscription.service import SubscriptionService
from subscription.repository import PlanRepository, UserSubscriptionRepository, PaymentTransactionRepository, CreditLedgerRepository

log = get_logger(__name__)

pipeline = APIRouter(prefix="/pipeline", tags=["pipeline"])

_progress_store: dict[str, dict[str, Any]] = {}
_progress_lock = asyncio.Lock()


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
    except Exception as exc:
        log.error(f"Pipeline failed: project={project_id} error={exc}")
        async with _progress_lock:
            entry = _progress_store.get(project_id, {"status": "idle", "percent": 0, "message": ""})
            entry.update({"status": "error", "percent": 0, "message": str(exc), "step_status": "failed"})
            _progress_store[project_id] = entry
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
        raise


@pipeline.post("/start/{project_id}")
async def start_pipeline(project_id: str, user: CurrentUserDep, body: dict | None = None):
    async with AsyncSessionLocal() as session:
        clip_repo = ClipRepository(session)
        pipeline_repo = PipelineRepository(session)

        project = await clip_repo.get_project(project_id, user["user_id"])
        if not project:
            raise CustomException(message="Project not found", code="NOT_FOUND", status_code=404)

        body = body or {}
        default_steps = [
            "download",
            "audio_extraction",
            "ai_noise_cancellation",
            "transcription",
            "topic_research",
            "visual_analysis",
            "content_classification",
            "highlight_detection",
            "bounding_box_detection",
            "scoring",
            "metadata_generation",
            "aspect_ratio_render",
            "clip_generation",
        ]
        selected_steps = [PipelineStepType.resolve(s) for s in body.get("steps", default_steps)]
        output_aspect_ratios = body.get("output_aspect_ratios")
        if isinstance(output_aspect_ratios, str):
            output_aspect_ratios = [item.strip() for item in output_aspect_ratios.split(",") if item.strip()]
        if not output_aspect_ratios:
            from core.config import get_settings
            output_aspect_ratios = [item.strip() for item in get_settings().DEFAULT_OUTPUT_ASPECT_RATIOS.split(",") if item.strip()]
        audio_config = body.get("audio_config", {
            "ai_denoise": True,
            "noise_suppression_strength": 90,
            "de_reverb": True,
            "vocal_clarity_eq": True,
            "hum_filter": True,
        })
        watermark_enabled = body.get("watermark_enabled", True)

        await pipeline_repo.create_pipeline(project_id, selected_steps)

        plan_repo = PlanRepository(session)
        sub_repo = UserSubscriptionRepository(session)
        tx_repo = PaymentTransactionRepository(session)
        ledger_repo = CreditLedgerRepository(session)
        subscription_service = SubscriptionService(plan_repo, sub_repo, tx_repo, ledger_repo)

        duration_seconds = project.duration_seconds or 0
        if duration_seconds <= 0:
            raise CustomException(message="Video duration not available. Please wait for metadata extraction.", code="DURATION_UNAVAILABLE", status_code=400)

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
                refund_plan_repo = PlanRepository(refund_session)
                refund_sub_repo = UserSubscriptionRepository(refund_session)
                refund_tx_repo = PaymentTransactionRepository(refund_session)
                refund_ledger_repo = CreditLedgerRepository(refund_session)
                refund_service = SubscriptionService(refund_plan_repo, refund_sub_repo, refund_tx_repo, refund_ledger_repo)
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

        orchestrator = PipelineOrchestrator(
            project_id=project_id,
            user_id=user["user_id"],
            url=project.source_url or "",
            selected_steps=selected_steps,
            audio_config=audio_config,
            progress_callback=_progress_callback_factory(project_id),
            watermark_enabled=watermark_enabled,
            output_aspect_ratios=output_aspect_ratios,
        )

        asyncio.create_task(_run_pipeline(orchestrator, project_id, user=user, credit_refund_callback=refund_credits))

        return {
            "project_id": project_id,
            "status": "started",
            "selected_steps": [s.value for s in selected_steps],
            "output_aspect_ratios": output_aspect_ratios,
            "watermark_enabled": watermark_enabled,
            "credits_deducted": credit_cost,
        }


@pipeline.get("/progress/{project_id}")
async def pipeline_progress(project_id: str, user: CurrentUserDep):
    async def event_stream():
        while True:
            async with _progress_lock:
                data = dict(_progress_store.get(project_id, {"status": "idle", "percent": 0, "message": ""}))
            yield f"data: {json.dumps(data)}\n\n"
            if data.get("status") in ("completed", "error"):
                break
            await asyncio.sleep(1)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@pipeline.get("/status/{project_id}")
async def pipeline_status(project_id: str, user: CurrentUserDep):
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

            return {
                "project_id": project_id,
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
        default_steps = [
            "download",
            "audio_extraction",
            "ai_noise_cancellation",
            "transcription",
            "topic_research",
            "visual_analysis",
            "content_classification",
            "highlight_detection",
            "bounding_box_detection",
            "scoring",
            "metadata_generation",
            "aspect_ratio_render",
            "clip_generation",
        ]
        selected_steps = [PipelineStepType.resolve(s) for s in body.get("steps", default_steps)]
        output_aspect_ratios = body.get("output_aspect_ratios")
        if isinstance(output_aspect_ratios, str):
            output_aspect_ratios = [item.strip() for item in output_aspect_ratios.split(",") if item.strip()]
        if not output_aspect_ratios:
            from core.config import get_settings
            output_aspect_ratios = [item.strip() for item in get_settings().DEFAULT_OUTPUT_ASPECT_RATIOS.split(",") if item.strip()]
        audio_config = body.get("audio_config", {
            "ai_denoise": True,
            "noise_suppression_strength": 90,
            "de_reverb": True,
            "vocal_clarity_eq": True,
            "hum_filter": True,
        })
        watermark_enabled = body.get("watermark_enabled", True)

        plan_repo = PlanRepository(session)
        sub_repo = UserSubscriptionRepository(session)
        tx_repo = PaymentTransactionRepository(session)
        ledger_repo = CreditLedgerRepository(session)
        subscription_service = SubscriptionService(plan_repo, sub_repo, tx_repo, ledger_repo)

        duration_seconds = project.duration_seconds or 0
        if duration_seconds <= 0:
            raise CustomException(message="Video duration not available.", code="DURATION_UNAVAILABLE", status_code=400)

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
                refund_plan_repo = PlanRepository(refund_session)
                refund_sub_repo = UserSubscriptionRepository(refund_session)
                refund_tx_repo = PaymentTransactionRepository(refund_session)
                refund_ledger_repo = CreditLedgerRepository(refund_session)
                refund_service = SubscriptionService(refund_plan_repo, refund_sub_repo, refund_tx_repo, refund_ledger_repo)
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

        orchestrator = PipelineOrchestrator(
            project_id=project_id,
            user_id=user["user_id"],
            url=project.source_url or "",
            selected_steps=selected_steps,
            audio_config=audio_config,
            progress_callback=_progress_callback_factory(project_id),
            watermark_enabled=watermark_enabled,
            output_aspect_ratios=output_aspect_ratios,
            resume=True,
        )

        asyncio.create_task(_run_pipeline(orchestrator, project_id, user=user, credit_refund_callback=refund_credits))

        return {
            "project_id": project_id,
            "status": "resumed",
            "selected_steps": [s.value for s in selected_steps],
            "output_aspect_ratios": output_aspect_ratios,
            "watermark_enabled": watermark_enabled,
            "credits_deducted": credit_cost,
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


@pipeline.post("/export/{project_id}")
async def export_clips_for_social(project_id: str, request: SocialExportRequest, user: CurrentUserDep):
    async with AsyncSessionLocal() as session:
        clip_repo = ClipRepository(session)
        project = await clip_repo.get_project(project_id, user["user_id"])
        if not project:
            raise CustomException(message="Project not found", code="NOT_FOUND", status_code=404)

    service = ClipService()
    result = await service.export_clips_for_social(
        project_id=project_id,
        user_id=user["user_id"],
        platforms=request.platforms,
        style_type=request.style_type,
        custom_config=request.custom_config,
        max_clips=request.max_clips,
        max_duration_override=request.max_duration,
        enable_emoji=request.enable_emoji,
        watermark_enabled=request.watermark_enabled,
        burn_subtitles=request.burn_subtitles,
    )
    return result
