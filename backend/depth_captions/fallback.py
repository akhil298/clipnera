from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Optional

from core.logging_config import get_logger
from video_processor.ffmpeg_service import FFmpegService
from depth_captions.schema import (
    DepthCaptionRequest,
    DepthCaptionJobResponse,
    DepthCaptionJobStatus,
    TranscriptSegment,
    EditPlan,
    CanvasConfig,
    StyleConfig,
    CaptionSegment,
    TextDepth,
    BoundingBox,
    SafeZones,
    StylePreset,
    STYLE_PRESETS,
    DepthMode,
)

log = get_logger(__name__)


class FallbackRenderer:
    def __init__(self) -> None:
        self._ffmpeg = FFmpegService()

    async def render_fallback_captions(
        self,
        request: DepthCaptionRequest,
        transcript_segments: list[TranscriptSegment],
        video_path: str,
        job_id: str,
        output_dir: Path,
        error_reason: str,
    ) -> DepthCaptionJobResponse:
        log.warning(f"Using fallback captions for job {job_id}: {error_reason}")
        
        output_path = output_dir / f"fallback_{job_id}.mp4"
        
        # Use existing subtitle styling service
        from subtitle_styling.service import SubtitleStylingService
        styling = SubtitleStylingService()
        
        # Convert transcript segments to format expected by styling service
        segments_for_styling = []
        for seg in transcript_segments:
            segments_for_styling.append({
                "start": seg.start,
                "end": seg.end,
                "text": seg.text,
                "speaker": seg.speaker,
                "words": [w.model_dump() for w in seg.words] if seg.words else [],
            })
        
        # Determine clip boundaries
        clip_start = min((s.start for s in transcript_segments), default=0)
        clip_end = max((s.end for s in transcript_segments), default=30)
        
        try:
            burned_path = await styling.burn_subtitles(
                video_path=video_path,
                clip_start=clip_start,
                clip_end=clip_end,
                style_type="simple",
                transcript_segments=segments_for_styling,
            )
            
            # Copy to output directory
            import shutil
            shutil.copy2(burned_path, output_path)
            
            # Upload to S3
            from clients.services.s3 import S3
            from core.config import get_settings
            
            settings = get_settings()
            s3 = S3()
            bucket = settings.S3_BUCKET_NAME
            s3_key = f"depth_captions/fallback_{job_id}.mp4"
            
            try:
                s3.create_bucket(bucket)
            except Exception:
                pass
            
            with open(output_path, "rb") as f:
                file_bytes = f.read()
            s3.put_object(bucket, s3_key, file_bytes)
            presigned_url = s3.generate_presigned_url(bucket, s3_key, expires_in=3600)
            
            return DepthCaptionJobResponse(
                job_id=job_id,
                status=DepthCaptionJobStatus.COMPLETED,
                progress=100,
                stage="completed_fallback",
                output_url=presigned_url,
                error=f"Fallback used: {error_reason}",
            )
            
        except Exception as e:
            log.error(f"Fallback rendering also failed: {e}")
            return DepthCaptionJobResponse(
                job_id=job_id,
                status=DepthCaptionJobStatus.FAILED,
                progress=0,
                stage="failed",
                error=f"Both depth captions and fallback failed: {error_reason}; {e}",
                retryable=True,
            )


class SimplifiedDepthRenderer:
    """Render simplified depth effect using only bounding boxes (no segmentation)"""
    
    def __init__(self) -> None:
        self._ffmpeg = FFmpegService()

    async def render_with_bbox_depth(
        self,
        edit_plan: EditPlan,
        video_path: str,
        subject_tracks: dict[str, PersonTrack],
        output_path: Path,
    ) -> str:
        """Create depth effect using simple bounding box masking"""
        log.info("Rendering simplified depth effect with bounding boxes")
        
        filter_graph = self._build_bbox_filter_graph(edit_plan, subject_tracks)
        
        encoder_args = await self._ffmpeg._get_encoder_args()
        
        cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-filter_complex", filter_graph,
            *encoder_args,
            "-c:a", "aac", "-b:a", "128k",
            "-movflags", "+faststart",
            str(output_path),
        ]
        
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        _, stderr = await proc.communicate()
        
        if proc.returncode != 0:
            err = stderr.decode("utf-8", errors="ignore")[-500:]
            raise RuntimeError(f"Simplified depth render failed: {err}")
        
        return str(output_path)

    def _build_bbox_filter_graph(
        self,
        edit_plan: EditPlan,
        subject_tracks: dict[str, PersonTrack],
    ) -> str:
        parts = []
        
        # Create bounding box mask for each track
        track_idx = 1
        for track_id, track in subject_tracks.items():
            if not track.frames:
                continue
            
            # Use first frame's bbox as approximation
            bbox = track.frames[0].bbox
            x = int(bbox.x * edit_plan.canvas.width)
            y = int(bbox.y * edit_plan.canvas.height)
            w = int(bbox.width * edit_plan.canvas.width)
            h = int(bbox.height * edit_plan.canvas.height)
            
            # Create mask from bbox
            parts.append(
                f"[0:v]split=2[base{track_idx}][mask{track_idx}]"
            )
            parts.append(
                f"[mask{track_idx}]drawbox=x={x}:y={y}:w={w}:h={h}:color=white:t=fill,"
                f"format=gray[mask{track_idx}_alpha]"
            )
        
        # Apply text with depth
        for i, segment in enumerate(edit_plan.segments):
            font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
            font_size = int(120 * segment.scale)
            x = int(segment.position.x * edit_plan.canvas.width)
            y = int(segment.position.y * edit_plan.canvas.height)
            
            font_color = self._color_to_ffmpeg(edit_plan.style.font_color, segment.opacity)
            stroke_color = self._color_to_ffmpeg(edit_plan.style.stroke_color, 1.0)
            
            if segment.depth == TextDepth.BEHIND:
                # Text behind: use first track's mask
                if len(subject_tracks) > 0:
                    track_id = list(subject_tracks.keys())[0]
                    track_idx = list(subject_tracks.keys()).index(track_id) + 1
                    
                    parts.append(
                        f"[base{track_idx}][mask{track_idx}_alpha]alphamerge[fg{track_idx}]"
                    )
                    parts.append(
                        f"[base{track_idx}]drawtext="
                        f"fontfile={font_path}:"
                        f"text='{segment.text}':"
                        f"fontsize={font_size}:"
                        f"fontcolor={font_color}:"
                        f"bordercolor={stroke_color}:"
                        f"borderw={edit_plan.style.stroke_width}:"
                        f"x={x}:"
                        f"y={y}:"
                        f"enable='between(t,{segment.start},{segment.end})'"
                        f"[text{i}]"
                    )
                    parts.append(f"[fg{track_idx}][text{i}]overlay=enable='between(t,{segment.start},{segment.end})'[out{i}]")
                else:
                    parts.append(
                        f"[0:v]drawtext="
                        f"fontfile={font_path}:"
                        f"text='{segment.text}':"
                        f"fontsize={font_size}:"
                        f"fontcolor={font_color}:"
                        f"bordercolor={stroke_color}:"
                        f"borderw={edit_plan.style.stroke_width}:"
                        f"x={x}:"
                        f"y={y}:"
                        f"enable='between(t,{segment.start},{segment.end})'"
                        f"[out{i}]"
                    )
            else:
                # Front text: just overlay
                if i == 0:
                    prev = "0:v"
                else:
                    prev = f"out{i-1}"
                
                parts.append(
                    f"[{prev}]drawtext="
                    f"fontfile={font_path}:"
                    f"text='{segment.text}':"
                    f"fontsize={font_size}:"
                    f"fontcolor={font_color}:"
                    f"bordercolor={stroke_color}:"
                    f"borderw={edit_plan.style.stroke_width}:"
                    f"x={x}:"
                    f"y={y}:"
                    f"enable='between(t,{segment.start},{segment.end})'"
                    f"[out{i}]"
                )
        
        final = f"out{len(edit_plan.segments)-1}" if edit_plan.segments else "0:v"
        parts.append(f"[{final}]format=yuv420p[out]")
        
        return ";".join(parts)

    def _color_to_ffmpeg(self, color: str, opacity: float) -> str:
        c = color.lstrip("#")
        if len(c) == 6:
            r, g, b = c[0:2], c[2:4], c[4:6]
        elif len(c) == 8:
            r, g, b = c[0:2], c[2:4], c[4:6]
            opacity = int(c[6:8], 16) / 255
        else:
            r, g, b = "FF", "FF", "FF"
        a = int(opacity * 255)
        return f"0x{a:02X}{r}{g}{b}"


class QualityBasedFallback:
    """Decide fallback strategy based on quality metrics"""
    
    @staticmethod
    def should_fallback(quality: Any) -> bool:
        if hasattr(quality, 'overall'):
            return quality.overall < 0.5
        return False

    @staticmethod
    def get_fallback_tier(quality: Any) -> str:
        if hasattr(quality, 'overall'):
            overall = quality.overall
            if overall >= 0.90:
                return "premium_depth"
            elif overall >= 0.75:
                return "standard_depth"
            elif overall >= 0.50:
                return "simplified_depth"
            else:
                return "normal_captions"
        return "normal_captions"

    @staticmethod
    def create_simplified_plan(edit_plan: EditPlan) -> EditPlan:
        """Create a simplified edit plan for lower quality modes"""
        simplified_segments = []
        
        for segment in edit_plan.segments:
            # Reduce complexity
            simplified = CaptionSegment(
                start=segment.start,
                end=segment.end,
                text=segment.text,
                depth=TextDepth.FRONT,  # Front is safer without good masks
                position=segment.position,
                scale=min(segment.scale, 1.2),
                rotation=0.0,  # No rotation for simplicity
                opacity=0.9,
                animation_in=segment.animation_in,
                animation_out=segment.animation_out,
                subject_id=segment.subject_id,
            )
            simplified_segments.append(simplified)
        
        return EditPlan(
            canvas=edit_plan.canvas,
            style=edit_plan.style,
            segments=simplified_segments,
            depth_mode=DepthMode.FRONT,
            safe_zones=edit_plan.safe_zones,
            subject_tracks=edit_plan.subject_tracks,
        )


class ErrorRecovery:
    @staticmethod
    async def recover_from_segmentation_failure(
        request: DepthCaptionRequest,
        transcript_segments: list[TranscriptSegment],
        video_path: str,
        job_id: str,
        output_dir: Path,
    ) -> DepthCaptionJobResponse:
        fallback = FallbackRenderer()
        return await fallback.render_fallback_captions(
            request, transcript_segments, video_path, job_id, output_dir,
            "Segmentation failed"
        )

    @staticmethod
    async def recover_from_matting_failure(
        edit_plan: EditPlan,
        video_path: str,
        subject_tracks: dict[str, PersonTrack],
        job_id: str,
        output_dir: Path,
    ) -> str:
        """Try simplified depth with bounding boxes"""
        renderer = SimplifiedDepthRenderer()
        output_path = output_dir / f"simplified_{job_id}.mp4"
        return await renderer.render_with_bbox_depth(
            edit_plan, video_path, subject_tracks, output_path
        )

    @staticmethod
    async def recover_from_render_failure(
        request: DepthCaptionRequest,
        transcript_segments: list[TranscriptSegment],
        video_path: str,
        job_id: str,
        output_dir: Path,
        error: str,
    ) -> DepthCaptionJobResponse:
        fallback = FallbackRenderer()
        return await fallback.render_fallback_captions(
            request, transcript_segments, video_path, job_id, output_dir,
            f"Render failed: {error}"
        )