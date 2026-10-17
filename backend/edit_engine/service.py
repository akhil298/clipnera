"""Footage reels: create, upload, analyse, change the plan, chat, render; and the music library."""

from __future__ import annotations

import asyncio
import hashlib
import json
import mimetypes
import tempfile
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from clients.ai import ModelChoice, get_text_client
from clients.ai.roles import selectable_models
from clients.services.s3 import S3
from core.config import get_settings
from core.exceptions import CustomException
from core.logging_config import get_logger
from edit_engine import jobs, reference
from edit_engine.compiler import compile_timeline, summary
from edit_engine.director import parse
from edit_engine.limits import limits_for
from edit_engine.looks import LOOKS
from edit_engine.model import EditProject, EditStatus, MusicStatus, MusicTrack
from edit_engine.music import ALLOWED_LICENCES, MOODS, SOURCES, credit_line, pick_track, validate_licence
from edit_engine.perception import probe_media
from edit_engine.schema import (
    EditChange, EditCreateRequest, EditLimitsResponse, EditLine, EditMusicResponse, EditPicture, EditPlanResponse,
    EditReferenceResponse, EditResponse, EditSourceResponse, EditSourcesCompleteRequest, EditSourcesInitRequest, EditSourcesInitResponse,
    EditChatRequest, EditSourceFile, EditSummary, EditText, EditTimelineMusic, EditTimelineResponse, EditUpload, EditVoicePiece, EditWord,
    MusicTrackResponse,
)
from edit_engine.script import SCRIPT_MODES
from feature_flags.registry import REEL_EDITOR_OPUS
from feature_flags.service import FeatureFlagService
from jobs.queue import Job, get_queue
from subscription.entitlements import Entitlements
from subscription.service import InsufficientCreditsError, SubscriptionService
from usage.context import llm_scope
from subtitle_styling.templates import DEFAULT_STYLE

log = get_logger(__name__)

URL_TTL_SECONDS = 3600
_KINDS = {"video": "video", "image": "image", "audio": "voice"}
_EXTENSIONS = {
    "video/mp4": ".mp4", "video/quicktime": ".mov", "video/webm": ".webm",
    "image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp",
    "audio/mpeg": ".mp3", "audio/wav": ".wav", "audio/x-wav": ".wav", "audio/mp4": ".m4a", "audio/x-m4a": ".m4a",
    "audio/webm": ".webm",
}
MAX_IMAGE_BYTES = 20 * 1024 * 1024
MAX_MUSIC_BYTES = 30 * 1024 * 1024
TARGETS = (0, 15, 30, 45, 60, 90)
PROGRESS = {EditStatus.RENDERING: "Rendering your reel"}
CHAT_SYSTEM = """You turn a creator's request about their reel into edits. Return JSON only: {"changes": [{"op": "...", "value": "..."}]}.
Allowed ops and values:
- set_hook: the new hook text (at most 6 words)
- set_look: one of LOOKS
- set_music: "none", or a mood from MOODS
- set_length: one of 0 (auto), 15, 30, 45, 60, 90
- remove_line / restore_line: a sentence id from the plan
- remove_pop: the sentence id of a pop-up
- set_caption_style: a caption style id
Use at most 5 changes. If nothing fits the request, return {"changes": []}."""


def _credit_text(music_credit: str | None) -> str | None:
    """The attribution the last render's music needs, if any."""
    return (json.loads(music_credit).get("credit_text") or None) if music_credit else None


class EditService:
    def __init__(self, session: AsyncSession, s3: S3 | None = None) -> None:
        self._session = session
        self._s3 = s3 or S3()
        self._settings = get_settings()
        self._subscriptions = SubscriptionService.for_session(session)

    # --- lifecycle ------------------------------------------------------------

    async def limits(self, user_id: str) -> EditLimitsResponse:
        limits = limits_for(await self._subscriptions.get_entitlements(user_id))
        return EditLimitsResponse(
            max_raw_seconds=limits.max_raw_seconds, max_files=limits.max_files, max_output_seconds=limits.max_output_seconds,
            output_height=limits.size[1], opus_director=await FeatureFlagService(self._session).is_enabled(REEL_EDITOR_OPUS),
        )

    async def create(self, user_id: str, request: EditCreateRequest) -> EditResponse:
        entitlements = await self._subscriptions.get_entitlements(user_id)
        self._check_caption_style(entitlements, request.caption_style)
        if request.target_seconds > limits_for(entitlements).max_output_seconds:
            raise CustomException(message="Your plan makes reels up to "
                                  f"{limits_for(entitlements).max_output_seconds} seconds long.", code="PRO_REQUIRED", status_code=403)
        self._check_model(entitlements, request.ai_model)
        if request.reference_url and not reference.is_supported_link(request.reference_url):
            raise CustomException(message="Paste a YouTube or Shorts link, or upload the reference reel instead.",
                                  code="INVALID_BODY", status_code=400)
        edit = EditProject(
            user_id=user_id, title=request.title.strip(), script=(request.script or "").strip() or None,
            script_mode=request.script_mode, intent=(request.intent or "").strip() or None, language=request.language.lower(),
            caption_style=request.caption_style, target_seconds=request.target_seconds, autopilot=request.autopilot,
            ai_model=request.ai_model, ai_effort=request.ai_effort if request.ai_model else None,
            reference_url=request.reference_url,
        )
        self._session.add(edit)
        await self._session.commit()
        return await self.response(edit)

    async def list(self, user_id: str) -> list[EditSummary]:
        rows = (await self._session.execute(
            select(EditProject).where(EditProject.user_id == user_id).order_by(EditProject.created_at.desc()).limit(100)
        )).scalars().all()
        return [EditSummary(id=r.id, title=r.title, status=r.status.value, duration_s=r.duration_s, created_at=r.created_at)
                for r in rows]

    async def get(self, user_id: str, edit_id: str) -> EditResponse:
        return await self.response(await self._edit(user_id, edit_id))

    async def init_sources(self, user_id: str, edit_id: str, request: EditSourcesInitRequest) -> EditSourcesInitResponse:
        edit = await self._edit(user_id, edit_id, statuses=(EditStatus.DRAFT, EditStatus.FAILED))
        limits = limits_for(await self._subscriptions.get_entitlements(user_id))
        sources = json.loads(edit.sources)
        footage = [f for f in request.files if not f.reference]
        self._check_reference(sources, [f for f in request.files if f.reference])
        if sum(1 for s in sources if s["kind"] != "reference") + len(footage) > limits.max_files:
            raise CustomException(message=f"Your plan allows up to {limits.max_files} files per reel.", code="FILE_LIMIT", status_code=403)
        declared = sum(s.get("duration") or 0 for s in sources if s["kind"] == "video")
        declared += sum(f.duration_s or 0 for f in footage if f.content_type.startswith("video/"))
        if declared > limits.max_raw_seconds:
            raise CustomException(message=f"Your plan edits up to {limits.max_raw_seconds // 60} minutes of footage per reel.",
                                  code="FOOTAGE_LIMIT", status_code=403)
        voices = sum(1 for s in sources if s["kind"] == "voice") + sum(1 for f in request.files if f.content_type.startswith("audio/"))
        if voices > 1:
            raise CustomException(message="Upload one voiceover", code="INVALID_BODY", status_code=400)
        uploads = []
        for file in request.files:
            if file.content_type.startswith("image/") and file.size_bytes > MAX_IMAGE_BYTES:
                raise CustomException(message=f"{file.filename} is over 20 MB", code="UPLOAD_TOO_LARGE", status_code=413)
            key = f"edits/{user_id}/{edit.id}/{uuid4().hex}{_EXTENSIONS[file.content_type]}"
            url = self._s3.presign_put(self._settings.S3_BUCKET_NAME, key, file.content_type, URL_TTL_SECONDS)
            uploads.append(EditUpload(key=key, url=url, content_type=file.content_type))
            kind = "reference" if file.reference else _KINDS[file.content_type.split("/")[0]]
            sources.append({"key": key, "kind": kind, "name": file.filename[:255],
                            "content_type": file.content_type, "duration": file.duration_s or 0.0, "uploaded": False})
        edit.sources = json.dumps(sources, ensure_ascii=False)
        await self._session.commit()
        return EditSourcesInitResponse(uploads=uploads)

    async def complete_sources(self, user_id: str, edit_id: str, request: EditSourcesCompleteRequest) -> EditResponse:
        edit = await self._edit(user_id, edit_id, statuses=(EditStatus.DRAFT, EditStatus.FAILED))
        sources = json.loads(edit.sources)
        by_key = {s["key"]: s for s in sources}
        for key in request.keys:
            if key not in by_key:
                raise CustomException(message="Unknown upload", code="INVALID_BODY", status_code=400)
            await asyncio.to_thread(self._s3.object_size, self._settings.S3_BUCKET_NAME, key)  # raises if missing
            by_key[key]["uploaded"] = True
        edit.sources = json.dumps(sources, ensure_ascii=False)
        await self._session.commit()
        return await self.response(edit)

    async def analyze(self, user_id: str, edit_id: str) -> EditResponse:
        """Analyse the footage and plan the reel in the background; poll until status is planned."""
        edit = await self._edit(user_id, edit_id, statuses=(EditStatus.DRAFT, EditStatus.FAILED))
        sources = [s for s in json.loads(edit.sources) if s.get("uploaded")]
        if not any(s["kind"] in ("video", "image") for s in sources):
            raise CustomException(message="Add at least one video or photo", code="INVALID_BODY", status_code=400)
        # A retry after a failed analysis is on us: only a new reel counts toward the daily limit.
        if edit.status == EditStatus.DRAFT:
            await self._subscriptions.consume_daily_quota(user_id, "auto_edits")
        edit.sources = json.dumps(sources, ensure_ascii=False)
        edit.status, edit.error, edit.analysis = EditStatus.ANALYZING, None, json.dumps({"progress": "Waiting to start"})
        await self._session.commit()
        await get_queue().enqueue(Job(jobs.ANALYZE_JOB, {"edit_id": edit.id, "user_id": user_id}))
        return await self.response(edit)

    async def replan(self, user_id: str, edit_id: str) -> EditResponse:
        """Run the director again (a paid call), keeping the analysis."""
        edit = await self._edit(user_id, edit_id, statuses=(EditStatus.PLANNED, EditStatus.DONE))
        await self._queue_plan(edit, user_id)
        return await self.response(edit)

    async def _queue_plan(self, edit: EditProject, user_id: str) -> None:
        """Queue a director call; each one after the first is capped, since each is a paid AI call."""
        if edit.replans >= self._settings.EDIT_MAX_REPLANS:
            raise CustomException(message="You've re-planned this reel as many times as it allows. Edit the plan instead.",
                                  code="REPLAN_LIMIT", status_code=429)
        analysis = json.loads(edit.analysis)
        edit.replans += 1
        edit.status, edit.error = EditStatus.ANALYZING, None
        edit.analysis = json.dumps({**analysis, "progress": "Planning the edit"}, ensure_ascii=False)
        await self._session.commit()
        await get_queue().enqueue(Job(jobs.PLAN_JOB, {"edit_id": edit.id, "user_id": user_id}))

    async def render(self, user_id: str, edit_id: str) -> EditResponse:
        edit = await self._edit(user_id, edit_id, statuses=(EditStatus.PLANNED, EditStatus.DONE))
        try:
            credits = await jobs.charge_render(self._subscriptions, user_id, edit)
        except InsufficientCreditsError:
            credits = jobs.price(edit)
            raise CustomException(
                message=f"This render needs {credits} credits. Your plan is saved: top up, or come back when your credits renew.",
                code="INSUFFICIENT_CREDITS", status_code=402, extra={"required": credits},
            )
        edit.status, edit.error, edit.credits_charged = EditStatus.RENDERING, None, edit.credits_charged + credits
        await self._session.commit()
        await get_queue().enqueue(Job(jobs.RENDER_JOB, {"edit_id": edit.id, "user_id": user_id, "credits": credits}))
        return await self.response(edit)

    # --- changing the plan ----------------------------------------------------

    async def apply_changes(self, user_id: str, edit_id: str, changes: list[EditChange]) -> EditResponse:
        """Edit the plan without another AI call and recompile the timeline (free)."""
        edit = await self._edit(user_id, edit_id, statuses=(EditStatus.PLANNED, EditStatus.DONE))
        entitlements = await self._subscriptions.get_entitlements(user_id)
        plan, analysis = json.loads(edit.plan), json.loads(edit.analysis)
        spoken = {s["id"] for s in (analysis.get("sentences") or []) + (analysis.get("voice_sentences") or [])}
        replan = False
        for change in changes:
            value = (change.value or "").strip()
            if change.op == "set_script_mode":
                if value not in SCRIPT_MODES:
                    raise CustomException(message="Unknown script mode", code="INVALID_BODY", status_code=400)
                edit.script_mode, replan = value, True
            elif change.op in ("restore_line", "remove_line"):
                if value not in spoken:
                    raise CustomException(message="No such line", code="INVALID_BODY", status_code=400)
                restore = change.op == "restore_line"
                plan["removed"] = [i for i in plan.get("removed", []) if i != value] + ([] if restore else [value])
                plan["restored"] = [i for i in plan.get("restored", []) if i != value] + ([value] if restore else [])
            elif change.op == "set_hook":
                plan["hook"] = " ".join(value.split()[:8])[:60]
            elif change.op == "set_music":
                plan["music"] = await self._music_for(value, plan, edit.id)
            elif change.op == "set_look":
                if value not in LOOKS:
                    raise CustomException(message="Unknown look", code="INVALID_BODY", status_code=400)
                plan["look"] = value
            elif change.op == "set_caption_style":
                self._check_caption_style(entitlements, value)
                plan["caption_style"] = edit.caption_style = value
            elif change.op == "set_length":
                if not value.isdigit() or int(value) not in TARGETS or int(value) > limits_for(entitlements).max_output_seconds:
                    raise CustomException(message="That length isn't available on your plan", code="INVALID_BODY", status_code=400)
                edit.target_seconds = int(value)
            elif change.op == "remove_pop":
                plan["pops"] = [p for p in plan.get("pops", []) if p["sentence"] != value]
            elif change.op == "skip_missing_lines":
                plan["skip_missing"] = value == "true"
        if replan:
            await self._queue_plan(edit, user_id)
            return await self.response(edit)
        timeline = compile_timeline(analysis, plan, size=limits_for(entitlements).size, target_seconds=edit.target_seconds,
                                    max_seconds=limits_for(entitlements).max_output_seconds)
        edit.plan = json.dumps(plan, ensure_ascii=False)
        edit.timeline = json.dumps(timeline, ensure_ascii=False)
        edit.duration_s = timeline["duration"]
        await self._session.commit()
        return await self.response(edit)

    async def _music_for(self, value: str, plan: dict[str, Any], seed: str) -> dict[str, Any] | None:
        if value in ("", "none"):
            return None
        if value in MOODS:
            tracks = list((await self._session.execute(
                select(MusicTrack).where(MusicTrack.status == MusicStatus.LIVE))).scalars())
            track = pick_track(tracks, value, plan.get("energy", "medium"), seed + value)
        else:
            track = await self._session.get(MusicTrack, value)
        if track is None or track.status != MusicStatus.LIVE:
            raise CustomException(message="That track isn't available", code="NOT_FOUND", status_code=404)
        return jobs.track_choice(track)

    async def chat(self, user_id: str, edit_id: str, request: EditChatRequest) -> EditResponse:
        """A request in the creator's words, turned into plan changes by a small model, or the one they picked."""
        edit = await self._edit(user_id, edit_id, statuses=(EditStatus.PLANNED, EditStatus.DONE))
        entitlements = await self._subscriptions.get_entitlements(user_id)
        if edit.chat_edits >= limits_for(entitlements).max_chat_edits:
            raise CustomException(message="You've used this reel's chat edits. You can still change the plan directly.",
                                  code="CHAT_LIMIT", status_code=429)
        if request.ai_model:
            self._check_model(entitlements, request.ai_model)
            edit.ai_model, edit.ai_effort = request.ai_model, request.ai_effort
        plan, analysis = json.loads(edit.plan), json.loads(edit.analysis)
        prompt = self._chat_context(plan, analysis, request.message)
        picked = ModelChoice("openai", edit.ai_model, edit.ai_effort) if edit.ai_model else None
        with llm_scope(user_id=user_id, project_id=edit.id, step="reel_chat"):
            reply = await get_text_client(is_pro=entitlements.pro_ai_provider, step="reel_chat", choice=picked).chat(
                [{"role": "system", "content": CHAT_SYSTEM.replace("LOOKS", ", ".join(LOOKS)).replace("MOODS", ", ".join(MOODS))},
                 {"role": "user", "content": prompt}], temperature=0.2, max_tokens=400, json_mode=True,
            )
        changes = []
        for raw in (parse(reply).get("changes") or [])[:5]:
            try:
                changes.append(EditChange(op=raw.get("op"), value=None if raw.get("value") is None else str(raw["value"])))
            except (ValueError, AttributeError):
                continue
        edit.chat_edits += 1
        await self._session.commit()
        if not changes:
            raise CustomException(message="I couldn't turn that into an edit. Try naming what to change, like the hook or the music.",
                                  code="NO_CHANGES", status_code=422)
        return await self.apply_changes(user_id, edit_id, [c for c in changes if c.op != "set_script_mode"])

    @staticmethod
    def _chat_context(plan: dict[str, Any], analysis: dict[str, Any], message: str) -> str:
        sentences = analysis.get("voice_sentences") if plan.get("mode") == "voiceover" else analysis.get("sentences")
        removed = set(plan.get("removed") or [])
        lines = [f"HOOK: {plan.get('hook', '')}", f"LOOK: {plan.get('look')}", f"MUSIC MOOD: {plan.get('music_mood')}",
                 "POP-UPS: " + "; ".join(f"{p['sentence']}: {p['text']}" for p in plan.get("pops") or []), "LINES:"]
        lines += [f"{s['id']}{' (removed)' if s['id'] in removed else ''}: {s['text'][:120]}" for s in (sentences or [])[:120]]
        return "\n".join(lines) + f"\n\nREQUEST: {message}"

    # --- helpers ----------------------------------------------------------------

    @staticmethod
    def _check_model(entitlements: Entitlements, model: str | None) -> None:
        if model is None:
            return
        if model not in selectable_models():
            raise CustomException(message=f"The AI can't use {model}.", code="UNKNOWN_MODEL", status_code=422)
        if not entitlements.pro_ai_provider:
            raise CustomException(message="Picking the AI model is on Pro.", code="PRO_REQUIRED", status_code=403,
                                  extra={"feature": "ai_model"})

    @staticmethod
    def _check_reference(sources: list[dict[str, Any]], files: list[EditSourceFile]) -> None:
        """One reference reel per reel: a video short enough to study."""
        if not files:
            return
        if len(files) + sum(1 for s in sources if s["kind"] == "reference") > 1:
            raise CustomException(message="Add one reference reel", code="INVALID_BODY", status_code=400)
        if not files[0].content_type.startswith("video/"):
            raise CustomException(message="The reference reel must be a video", code="INVALID_BODY", status_code=400)
        if (files[0].duration_s or 0) > reference.MAX_SECONDS:
            raise CustomException(message=f"Use a reference reel under {reference.MAX_SECONDS // 60} minutes",
                                  code="INVALID_BODY", status_code=400)

    @staticmethod
    def _check_caption_style(entitlements: Entitlements, style: str) -> None:
        if not entitlements.allows_caption_style(style):
            raise CustomException(message="That caption style is on Pro.", code="PRO_REQUIRED", status_code=403,
                                  extra={"feature": "caption_style"})

    async def _edit(self, user_id: str, edit_id: str, statuses: tuple[EditStatus, ...] | None = None) -> EditProject:
        edit = await self._session.get(EditProject, edit_id)
        if edit is None or edit.user_id != user_id:
            raise CustomException(message="Reel not found", code="NOT_FOUND", status_code=404)
        if statuses is not None and edit.status not in statuses:
            busy = edit.status in (EditStatus.ANALYZING, EditStatus.RENDERING)
            raise CustomException(message="The reel is busy; wait for it to finish" if busy else "The reel isn't ready for that yet",
                                  code="REEL_BUSY" if busy else "REEL_NOT_READY", status_code=409)
        return edit

    def _url(self, key: str | None) -> str | None:
        return self._s3.generate_presigned_url(self._settings.S3_BUCKET_NAME, key, URL_TTL_SECONDS) if key else None

    async def response(self, edit: EditProject) -> EditResponse:
        sources = json.loads(edit.sources)
        analysis = json.loads(edit.analysis or "{}")
        plan = json.loads(edit.plan or "{}")
        timeline = json.loads(edit.timeline or "{}")
        entitlements = await self._subscriptions.get_entitlements(edit.user_id)
        limits = limits_for(entitlements)
        has_plan = bool(plan) and bool(timeline)
        return EditResponse(
            id=edit.id, title=edit.title, status=edit.status.value,
            progress=PROGRESS.get(edit.status) or (analysis.get("progress") if edit.status == EditStatus.ANALYZING else None),
            script=edit.script, script_mode=edit.script_mode, intent=edit.intent, language=edit.language,
            caption_style=edit.caption_style, target_seconds=edit.target_seconds, autopilot=edit.autopilot,
            ai_model=edit.ai_model, ai_effort=edit.ai_effort, reference_url=edit.reference_url,
            reference=EditReferenceResponse(**analysis["reference"]) if analysis.get("reference") else None,
            reference_error=analysis.get("reference_error"),
            sources=[self._source_response(s) for s in sources if s.get("uploaded")],
            raw_seconds=edit.raw_seconds, duration_s=edit.duration_s,
            plan=await self._plan_response(plan, analysis, timeline) if has_plan else None,
            timeline=self._timeline_response(timeline) if has_plan else None,
            credits_estimate=jobs.price(edit) if has_plan else 0, credits_charged=edit.credits_charged, renders=edit.renders,
            replans_left=max(0, self._settings.EDIT_MAX_REPLANS - edit.replans),
            chat_edits_left=max(0, limits.max_chat_edits - edit.chat_edits),
            output_url=self._url(edit.output_key), music_credit=_credit_text(edit.music_credit), error=edit.error,
            created_at=edit.created_at,
        )

    def _source_response(self, source: dict[str, Any]) -> EditSourceResponse:
        playable = source.get("proxy_key") if source["kind"] == "video" else source["key"]
        return EditSourceResponse(key=source["key"], kind=source["kind"], name=source.get("name") or "",
                                  duration_s=float(source.get("duration") or 0.0), url=self._url(playable))

    async def _plan_response(self, plan: dict[str, Any], analysis: dict[str, Any], timeline: dict[str, Any]) -> EditPlanResponse:
        lines = plan.get("script_lines") or []
        by_id = {s["id"]: s for s in analysis.get("sentences") or []}
        removed_ids = list(dict.fromkeys([*(plan.get("unscripted") or []), *(plan.get("removed") or [])]))
        removed = [EditLine(id=i, text=by_id[i]["text"]) for i in removed_ids
                   if i in by_id and i not in (plan.get("restored") or [])]
        music = plan.get("music")
        track = await self._session.get(MusicTrack, music["track_id"]) if music else None
        counts = summary(timeline)
        return EditPlanResponse(
            content_type=plan.get("content_type", "vlog"), layout=timeline.get("layout", "talking"),
            script_mode=plan.get("mode", "none"),
            script_lines_found=sum(1 for line in lines if line["sentences"]), script_lines_total=len(lines),
            missing_lines=[line["text"] for line in lines if not line["sentences"]] if plan.get("mode") == "spoken" else [],
            skip_missing=bool(plan.get("skip_missing")), removed_lines=removed,
            hook=plan.get("hook", ""), title=plan.get("title", ""), look=plan.get("look", "natural"),
            caption_style=plan.get("caption_style", DEFAULT_STYLE),
            music=EditMusicResponse(id=track.id, title=track.title, artist=track.artist, licence=track.licence,
                                    credit_text=track.credit_text, url=self._url(track.audio_key)) if track else None,
            music_mood=plan.get("music_mood", ""), broll_count=counts["broll"],
            # Every cutaway comes from the creator's own footage and photos for now.
            own_broll_count=counts["broll"], pop_count=counts["pops"],
            director_model=plan.get("director_model", ""), caption=plan.get("caption", ""), hashtags=plan.get("hashtags") or [],
        )

    @staticmethod
    def _timeline_response(timeline: dict[str, Any]) -> EditTimelineResponse:
        def picture(item: dict[str, Any]) -> EditPicture:
            video = item["kind"] == "video"
            return EditPicture(kind=item["kind"], at=item["at"], dur=(item["out"] - item["in"]) if video else item["dur"],
                               src=item.get("src"), source_start=item.get("in"), source_end=item.get("out"),
                               zoom=item.get("zoom"), crop_x=item.get("crop_x"), text=item.get("text"))

        music = timeline.get("music")
        return EditTimelineResponse(
            duration=timeline["duration"], width=timeline["width"], height=timeline["height"], look=timeline.get("look", "natural"),
            picture=[picture(p) for p in timeline["picture"]],
            voice=[EditVoicePiece(src=v["src"], source_start=v["in"], source_end=v["out"], at=v["at"]) for v in timeline["voice"]],
            voiceover_src=(timeline.get("voiceover") or {}).get("src"),
            texts=[EditText(**t) for t in timeline["texts"]], words=[EditWord(**w) for w in timeline["words"]],
            music=EditTimelineMusic(**music) if music else None,
        )


class MusicLibraryService:
    """Admin intake of free-licence tracks; a track goes live only with a complete licence record."""

    def __init__(self, session: AsyncSession, s3: S3 | None = None) -> None:
        self._session = session
        self._s3 = s3 or S3()
        self._bucket = get_settings().S3_BUCKET_NAME

    async def add(self, admin_id: str, audio: bytes, filename: str, fields: dict[str, Any]) -> MusicTrackResponse:
        if not audio or len(audio) > MAX_MUSIC_BYTES:
            raise CustomException(message="Upload an audio file under 30 MB", code="INVALID_BODY", status_code=400)
        if fields["source"] not in SOURCES or fields["mood"] not in MOODS:
            raise CustomException(message="Unknown source or mood", code="INVALID_BODY", status_code=400)
        needs_credit = ALLOWED_LICENCES.get(fields["licence"], ("", False))[1]
        credit = fields.get("credit_text") or (credit_line(fields["title"], fields["artist"], fields["licence"], fields["source_url"])
                                               if needs_credit else "")
        deed = validate_licence(fields["licence"], fields["commercial_ok"], fields["edit_ok"], credit)
        digest = hashlib.sha256(audio).hexdigest()
        if await self._session.scalar(select(MusicTrack.id).where(MusicTrack.audio_sha256 == digest)):
            raise CustomException(message="This track is already in the library", code="DUPLICATE", status_code=409)
        snapshot = await self._snapshot(fields["source_url"])
        suffix = Path(filename).suffix.lower() or ".mp3"
        audio_key, snapshot_key = f"music/{digest}{suffix}", f"music/licences/{digest}.html"
        with tempfile.NamedTemporaryFile(suffix=suffix) as tmp:
            tmp.write(audio)
            tmp.flush()
            info = await probe_media(tmp.name)
            if not info.has_audio or info.duration < 5:
                raise CustomException(message="That file has no usable audio", code="INVALID_BODY", status_code=400)
            content_type = mimetypes.guess_type(filename)[0] or "audio/mpeg"
            await asyncio.to_thread(self._s3.upload_file, self._bucket, audio_key, tmp.name, content_type)
        await asyncio.to_thread(self._s3.put_object, self._bucket, snapshot_key, snapshot, ContentType="text/html")
        track = MusicTrack(
            title=fields["title"], artist=fields["artist"], source=fields["source"], source_url=fields["source_url"],
            source_id=fields["source_id"], licence=fields["licence"], licence_url=deed, credit_text=credit,
            commercial_ok=True, edit_ok=True, snapshot_key=snapshot_key, audio_key=audio_key, audio_sha256=digest,
            duration_s=info.duration, bpm=fields.get("bpm"), mood=fields["mood"], energy=fields["energy"], added_by=admin_id,
        )
        self._session.add(track)
        await self._session.commit()
        return self._response(track, 0)

    @staticmethod
    async def _snapshot(url: str) -> bytes:
        """The track page as it is today: our record of the licence it was offered under."""
        try:
            async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
                response = await client.get(url)
                response.raise_for_status()
                return response.content
        except httpx.HTTPError as exc:
            raise CustomException(message=f"Couldn't save a copy of the track page ({exc.__class__.__name__}). "
                                  "Check the source URL.", code="SNAPSHOT_FAILED", status_code=400)

    async def list(self) -> list[MusicTrackResponse]:
        tracks = (await self._session.execute(select(MusicTrack).order_by(MusicTrack.created_at.desc()))).scalars().all()
        return [self._response(t, await self._used_by(t.id)) for t in tracks]

    async def set_status(self, track_id: str, status: str) -> MusicTrackResponse:
        track = await self._session.get(MusicTrack, track_id)
        if track is None:
            raise CustomException(message="Track not found", code="NOT_FOUND", status_code=404)
        track.status = MusicStatus(status)
        await self._session.commit()
        return self._response(track, await self._used_by(track.id))

    async def _used_by(self, track_id: str) -> int:
        """Rendered reels that carry this track: the ones to re-render if it is pulled."""
        return int(await self._session.scalar(
            select(func.count()).select_from(EditProject).where(EditProject.music_credit.contains(track_id))) or 0)

    @staticmethod
    def _response(track: MusicTrack, used_by: int) -> MusicTrackResponse:
        return MusicTrackResponse(
            id=track.id, title=track.title, artist=track.artist, source=track.source, source_url=track.source_url,
            licence=track.licence, licence_url=track.licence_url, credit_text=track.credit_text, mood=track.mood,
            energy=track.energy, bpm=track.bpm, duration_s=track.duration_s, status=track.status.value, used_by=used_by,
            created_at=track.created_at,
        )
