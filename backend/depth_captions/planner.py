from __future__ import annotations

import json
import asyncio
from typing import Any, Optional
from pydantic import ValidationError

from core.logging_config import get_logger
from core.exceptions import CustomException
from clients.ai import get_text_client
from depth_captions.schema import (
    EditPlan,
    CaptionSegment,
    CanvasConfig,
    StyleConfig,
    TranscriptSegment,
    PersonTrack,
    BoundingBox,
    GeometryRegions,
    SafeZones,
    DepthMode,
    TextDepth,
    AnimationType,
    StylePreset,
    STYLE_PRESETS,
    calculate_regions,
)

log = get_logger(__name__)


class LLMPlanner:
    def __init__(self) -> None:
        self._groq = get_text_client()

    async def generate_edit_plan(
        self,
        transcript_segments: list[TranscriptSegment],
        canvas: CanvasConfig,
        style: StyleConfig,
        subject_tracks: dict[str, PersonTrack],
        depth_mode: DepthMode,
        safe_zones: SafeZones,
        video_metadata: dict[str, Any],
    ) -> EditPlan:
        log.info("Generating edit plan with LLM")
        
        prompt = self._build_prompt(
            transcript_segments, canvas, style, subject_tracks, 
            depth_mode, safe_zones, video_metadata
        )
        
        try:
            response = await self._groq.chat([{"role": "user", "content": prompt}], max_tokens=2000)
            plan_data = self._parse_llm_response(response)
            
            edit_plan = EditPlan(
                canvas=canvas,
                style=style,
                segments=plan_data["segments"],
                depth_mode=depth_mode,
                safe_zones=safe_zones,
                subject_tracks=subject_tracks,
            )
            
            return self._validate_and_repair(edit_plan, canvas, subject_tracks, safe_zones)
            
        except Exception as e:
            log.warning(f"LLM planning failed: {e}, using fallback")
            return self._fallback_plan(
                transcript_segments, canvas, style, subject_tracks, 
                depth_mode, safe_zones
            )

    def _build_prompt(
        self,
        transcript_segments: list[TranscriptSegment],
        canvas: CanvasConfig,
        style: StyleConfig,
        subject_tracks: dict[str, PersonTrack],
        depth_mode: DepthMode,
        safe_zones: SafeZones,
        video_metadata: dict[str, Any],
    ) -> str:
        person_bbox = None
        for track in subject_tracks.values():
            if track.frames:
                bbox = track.frames[0].bbox
                person_bbox = {
                    "x": bbox.x,
                    "y": bbox.y,
                    "width": bbox.width,
                    "height": bbox.height,
                }
                break
        
        regions = None
        if person_bbox:
            regions = calculate_regions(canvas.width, canvas.height, BoundingBox(**person_bbox))
        
        transcript_text = "\n".join([
            f"[{seg.start:.2f}-{seg.end:.2f}] {seg.speaker or 'Speaker'}: {seg.text}"
            for seg in transcript_segments
        ])
        
        safe_area = {
            "top": safe_zones.top,
            "bottom": safe_zones.bottom,
            "left": safe_zones.left,
            "right": safe_zones.right,
        }
        
        prompt = f"""You are a professional video editor creating depth captions for a short-form video.

VIDEO PROPERTIES:
- Canvas: {canvas.width}x{canvas.height}
- Duration: {video_metadata.get('duration', 30):.1f}s
- FPS: {video_metadata.get('fps', 30)}

SUBJECT POSITION (normalized 0-1):
{json.dumps(person_bbox, indent=2) if person_bbox else "No subject detected"}

SAFE AREA (normalized 0-1):
{json.dumps(safe_area, indent=2)}

REGIONS:
{json.dumps({
    "top": {"x": regions.top_region.x, "y": regions.top_region.y, "w": regions.top_region.width, "h": regions.top_region.height},
    "person": {"x": regions.person_zone.x, "y": regions.person_zone.y, "w": regions.person_zone.width, "h": regions.person_zone.height},
    "bottom": {"x": regions.bottom_region.x, "y": regions.bottom_region.y, "w": regions.bottom_region.width, "h": regions.bottom_region.height},
}) if regions else "N/A"}

TRANSCRIPT:
{transcript_text}

STYLE PRESET:
- Font: {style.font_family}
- Weight: {style.font_weight}
- Uppercase: {style.uppercase}
- Default scale: {style.default_scale}
- Animation in: {style.animation_in.value}
- Animation out: {style.animation_out.value}
- Font color: {style.font_color}
- Stroke: {style.stroke_color} ({style.stroke_width}px)

DEPTH MODE: {depth_mode.value}

RULES:
1. Output ONLY valid JSON matching the schema below
2. Each word/phrase gets its own segment with timing
3. Depth must be "behind" or "front"
4. Position must be within safe area
5. Scale between 0.5 and 2.0
6. Rotation between -8 and +8 degrees
7. Opacity between 0 and 1
8. Animation must be one of: {", ".join([a.value for a in AnimationType])}
9. For "behind" depth: place text in top/bottom regions, NOT over person
10. For "front" depth: place text near person but not covering face
11. Prefer "behind" when text is readable around person
12. Use large typography for emphasis words
13. Never place text outside canvas or safe zones

SCHEMA:
{{
  "segments": [
    {{
      "start": float,
      "end": float,
      "text": "string",
      "depth": "behind" | "front",
      "position": {{"x": float, "y": float, "width": float, "height": float}},
      "scale": float,
      "rotation": float,
      "opacity": float,
      "animation_in": "string",
      "animation_out": "string",
      "subject_id": "string"
    }}
  ]
}}

Return ONLY the JSON object."""
        return prompt

    def _parse_llm_response(self, response: str) -> dict[str, Any]:
        # Extract JSON from response
        start = response.find("{")
        end = response.rfind("}") + 1
        if start >= 0 and end > start:
            json_str = response[start:end]
            return json.loads(json_str)
        raise ValueError("No valid JSON found in LLM response")

    def _validate_and_repair(
        self,
        edit_plan: EditPlan,
        canvas: CanvasConfig,
        subject_tracks: dict[str, PersonTrack],
        safe_zones: SafeZones,
    ) -> EditPlan:
        # Validate each segment
        valid_segments = []
        safe_area = BoundingBox(
            x=safe_zones.left,
            y=safe_zones.top,
            width=1.0 - safe_zones.left - safe_zones.right,
            height=1.0 - safe_zones.top - safe_zones.bottom,
        )
        
        for segment in edit_plan.segments:
            # Clamp position to safe area
            pos = segment.position
            pos.x = max(safe_area.x, min(pos.x, safe_area.x + safe_area.width - pos.width))
            pos.y = max(safe_area.y, min(pos.y, safe_area.y + safe_area.height - pos.height))
            
            # Clamp scale
            segment.scale = max(0.5, min(segment.scale, 2.0))
            
            # Clamp rotation
            segment.rotation = max(-8.0, min(segment.rotation, 8.0))
            
            # Clamp opacity
            segment.opacity = max(0.0, min(segment.opacity, 1.0))
            
            # Validate depth
            if segment.depth not in [TextDepth.BEHIND, TextDepth.FRONT]:
                segment.depth = TextDepth.BEHIND
            
            # Validate animation
            try:
                AnimationType(segment.animation_in)
            except ValueError:
                segment.animation_in = AnimationType.SCALE_UP
            
            try:
                AnimationType(segment.animation_out)
            except ValueError:
                segment.animation_out = AnimationType.FADE
            
            # Validate subject_id
            if segment.subject_id and segment.subject_id not in subject_tracks:
                segment.subject_id = list(subject_tracks.keys())[0] if subject_tracks else None
            
            valid_segments.append(segment)
        
        edit_plan.segments = valid_segments
        return edit_plan

    def _fallback_plan(
        self,
        transcript_segments: list[TranscriptSegment],
        canvas: CanvasConfig,
        style: StyleConfig,
        subject_tracks: dict[str, PersonTrack],
        depth_mode: DepthMode,
        safe_zones: SafeZones,
    ) -> EditPlan:
        log.info("Using fallback plan generation")
        
        person_bbox = None
        subject_id = None
        for track_id, track in subject_tracks.items():
            if track.frames:
                person_bbox = track.frames[0].bbox
                subject_id = track_id
                break
        
        if not person_bbox:
            person_bbox = BoundingBox(x=0.3, y=0.15, width=0.4, height=0.75)
            subject_id = "person_01"
        
        regions = calculate_regions(canvas.width, canvas.height, person_bbox)
        safe_area = BoundingBox(
            x=safe_zones.left,
            y=safe_zones.top,
            width=1.0 - safe_zones.left - safe_zones.right,
            height=1.0 - safe_zones.top - safe_zones.bottom,
        )
        
        segments = []
        for seg in transcript_segments:
            words = seg.text.split()
            for i, word in enumerate(words):
                word_start = seg.start + (i / len(words)) * (seg.end - seg.start)
                word_end = seg.start + ((i + 1) / len(words)) * (seg.end - seg.start)
                
                depth = TextDepth.BEHIND if i % 2 == 0 else TextDepth.FRONT
                if depth_mode == DepthMode.BEHIND:
                    depth = TextDepth.BEHIND
                elif depth_mode == DepthMode.FRONT:
                    depth = TextDepth.FRONT
                
                if depth == TextDepth.BEHIND:
                    position = BoundingBox(
                        x=0.1,
                        y=regions.top_region.y + regions.top_region.height / 2 - 0.075,
                        width=0.8,
                        height=0.15,
                    )
                else:
                    position = BoundingBox(
                        x=person_bbox.x + person_bbox.width / 2 - 0.4,
                        y=person_bbox.y - 0.15,
                        width=0.8,
                        height=0.15,
                    )
                
                segments.append(CaptionSegment(
                    start=word_start,
                    end=word_end,
                    text=word.upper() if style.uppercase else word,
                    depth=depth,
                    position=position,
                    scale=style.default_scale,
                    rotation=0.0,
                    opacity=0.95,
                    animation_in=style.animation_in,
                    animation_out=style.animation_out,
                    subject_id=subject_id,
                ))
        
        return EditPlan(
            canvas=canvas,
            style=style,
            segments=segments,
            depth_mode=depth_mode,
            safe_zones=safe_zones,
            subject_tracks=subject_tracks,
        )


class PlanValidator:
    @staticmethod
    def validate(edit_plan: EditPlan) -> tuple[bool, list[str]]:
        errors = []
        
        # Check canvas
        if edit_plan.canvas.width <= 0 or edit_plan.canvas.height <= 0:
            errors.append("Invalid canvas dimensions")
        
        # Check segments
        for i, segment in enumerate(edit_plan.segments):
            if segment.start >= segment.end:
                errors.append(f"Segment {i}: start >= end")
            
            if segment.start < 0:
                errors.append(f"Segment {i}: negative start time")
            
            # Check position bounds
            pos = segment.position
            if pos.x < 0 or pos.x + pos.width > 1:
                errors.append(f"Segment {i}: x position out of bounds")
            if pos.y < 0 or pos.y + pos.height > 1:
                errors.append(f"Segment {i}: y position out of bounds")
            
            # Check scale
            if segment.scale < 0.5 or segment.scale > 2.0:
                errors.append(f"Segment {i}: scale out of range")
            
            # Check rotation
            if segment.rotation < -8 or segment.rotation > 8:
                errors.append(f"Segment {i}: rotation out of range")
            
            # Check opacity
            if segment.opacity < 0 or segment.opacity > 1:
                errors.append(f"Segment {i}: opacity out of range")
            
            # Check depth
            if segment.depth not in [TextDepth.BEHIND, TextDepth.FRONT]:
                errors.append(f"Segment {i}: invalid depth")
            
            # Check animation
            try:
                AnimationType(segment.animation_in)
            except ValueError:
                errors.append(f"Segment {i}: invalid animation_in")
            
            try:
                AnimationType(segment.animation_out)
            except ValueError:
                errors.append(f"Segment {i}: invalid animation_out")
        
        return len(errors) == 0, errors

    @staticmethod
    def repair(edit_plan: EditPlan, canvas: CanvasConfig) -> EditPlan:
        # Auto-repair common issues
        for segment in edit_plan.segments:
            if segment.start >= segment.end:
                segment.end = segment.start + 0.5
            
            pos = segment.position
            pos.x = max(0, min(pos.x, 1 - pos.width))
            pos.y = max(0, min(pos.y, 1 - pos.height))
            
            segment.scale = max(0.5, min(segment.scale, 2.0))
            segment.rotation = max(-8.0, min(segment.rotation, 8.0))
            segment.opacity = max(0.0, min(segment.opacity, 1.0))
        
        return edit_plan