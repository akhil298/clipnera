from __future__ import annotations

import math
from typing import Any, Optional

from core.logging_config import get_logger
from depth_captions.schema import (
    BoundingBox,
    CanvasConfig,
    CaptionSegment,
    PersonTrack,
    GeometryRegions,
    SubjectGeometry,
    SafeZones,
    calculate_regions,
    TextDepth,
)

log = get_logger(__name__)


class LayoutEngine:
    def __init__(self, safe_zones: SafeZones | None = None) -> None:
        self.safe_zones = safe_zones or SafeZones()

    def calculate_person_geometry(
        self,
        track: PersonTrack,
        canvas: CanvasConfig,
        frame_index: int,
    ) -> SubjectGeometry:
        closest = min(track.frames, key=lambda f: abs(f.frame - frame_index))
        bbox = closest.bbox
        
        return SubjectGeometry(
            track_id=track.track_id,
            bbox_normalized=bbox,
            center_x=(bbox.x + bbox.width / 2),
            center_y=(bbox.y + bbox.height / 2),
            top=bbox.y,
            bottom=bbox.y + bbox.height,
            left=bbox.x,
            right=bbox.x + bbox.width,
        )

    def get_regions(self, canvas: CanvasConfig, person_bbox: BoundingBox) -> GeometryRegions:
        return calculate_regions(canvas.width, canvas.height, person_bbox)

    def calculate_safe_area(self, canvas: CanvasConfig) -> BoundingBox:
        return BoundingBox(
            x=self.safe_zones.left,
            y=self.safe_zones.top,
            width=1.0 - self.safe_zones.left - self.safe_zones.right,
            height=1.0 - self.safe_zones.top - self.safe_zones.bottom,
        )

    def find_best_position(
        self,
        text: str,
        canvas: CanvasConfig,
        person_geometry: SubjectGeometry,
        style_scale: float,
        depth: TextDepth,
        regions: GeometryRegions,
        safe_area: BoundingBox,
    ) -> BoundingBox:
        if depth == TextDepth.BEHIND:
            return self._find_behind_position(
                text, canvas, person_geometry, style_scale, regions, safe_area
            )
        else:
            return self._find_front_position(
                text, canvas, person_geometry, style_scale, regions, safe_area
            )

    def _find_behind_position(
        self,
        text: str,
        canvas: CanvasConfig,
        person_geometry: SubjectGeometry,
        style_scale: float,
        regions: GeometryRegions,
        safe_area: BoundingBox,
    ) -> BoundingBox:
        # Try top region first
        top_center_x = 0.5
        top_y = regions.top_region.y + regions.top_region.height / 2
        
        # Check if top region is within safe area
        if (top_y >= safe_area.y and 
            top_y + 0.1 <= safe_area.y + safe_area.height):
            return BoundingBox(
                x=top_center_x - 0.4,
                y=top_y - 0.075,
                width=0.8,
                height=0.15,
            )
        
        # Try bottom region
        bottom_y = regions.bottom_region.y + regions.bottom_region.height / 2
        if (bottom_y >= safe_area.y and 
            bottom_y + 0.1 <= safe_area.y + safe_area.height):
            return BoundingBox(
                x=0.5 - 0.4,
                y=bottom_y - 0.075,
                width=0.8,
                height=0.15,
            )
        
        # Fallback: center of safe area
        return BoundingBox(
            x=safe_area.x + safe_area.width / 2 - 0.4,
            y=safe_area.y + safe_area.height / 2 - 0.075,
            width=0.8,
            height=0.15,
        )

    def _find_front_position(
        self,
        text: str,
        canvas: CanvasConfig,
        person_geometry: SubjectGeometry,
        style_scale: float,
        regions: GeometryRegions,
        safe_area: BoundingBox,
    ) -> BoundingBox:
        # For front text, place near person but not covering face
        face_top = person_geometry.top + person_geometry.bbox_normalized.height * 0.15
        face_bottom = person_geometry.top + person_geometry.bbox_normalized.height * 0.45
        
        # Try above head
        above_y = person_geometry.top - 0.1
        if above_y >= safe_area.y:
            return BoundingBox(
                x=person_geometry.center_x - 0.4,
                y=above_y - 0.075,
                width=0.8,
                height=0.15,
            )
        
        # Try below chin
        below_y = face_bottom + 0.1
        if below_y + 0.15 <= safe_area.y + safe_area.height:
            return BoundingBox(
                x=person_geometry.center_x - 0.4,
                y=below_y,
                width=0.8,
                height=0.15,
            )
        
        # Fallback to safe area center
        return BoundingBox(
            x=safe_area.x + safe_area.width / 2 - 0.4,
            y=safe_area.y + safe_area.height / 2 - 0.075,
            width=0.8,
            height=0.15,
        )

    def calculate_visibility(
        self,
        text_bbox: BoundingBox,
        person_bbox: BoundingBox,
        canvas: CanvasConfig,
        depth: TextDepth,
    ) -> float:
        text_left = text_bbox.x * canvas.width
        text_right = (text_bbox.x + text_bbox.width) * canvas.width
        text_top = text_bbox.y * canvas.height
        text_bottom = (text_bbox.y + text_bbox.height) * canvas.height
        
        person_left = person_bbox.x * canvas.width
        person_right = (person_bbox.x + person_bbox.width) * canvas.width
        person_top = person_bbox.y * canvas.height
        person_bottom = (person_bbox.y + person_bbox.height) * canvas.height
        
        # Calculate overlap
        overlap_left = max(text_left, person_left)
        overlap_right = min(text_right, person_right)
        overlap_top = max(text_top, person_top)
        overlap_bottom = min(text_bottom, person_bottom)
        
        if overlap_left >= overlap_right or overlap_top >= overlap_bottom:
            overlap_area = 0
        else:
            overlap_area = (overlap_right - overlap_left) * (overlap_bottom - overlap_top)
        
        text_area = text_bbox.width * text_bbox.height * canvas.width * canvas.height
        
        if text_area == 0:
            return 0.0
        
        overlap_ratio = overlap_area / text_area
        
        if depth == TextDepth.BEHIND:
            # Behind text: want low overlap (text visible around person)
            return 1.0 - overlap_ratio
        else:
            # Front text: overlap doesn't matter as much, but avoid face
            face_top = person_top + (person_bottom - person_top) * 0.15
            face_bottom = person_top + (person_bottom - person_top) * 0.45
            face_left = person_left + (person_right - person_left) * 0.25
            face_right = person_left + (person_right - person_left) * 0.75
            
            face_overlap_left = max(text_left, face_left)
            face_overlap_right = min(text_right, face_right)
            face_overlap_top = max(text_top, face_top)
            face_overlap_bottom = min(text_bottom, face_bottom)
            
            if face_overlap_left >= face_overlap_right or face_overlap_top >= face_overlap_bottom:
                face_overlap = 0
            else:
                face_overlap = (face_overlap_right - face_overlap_left) * (face_overlap_bottom - face_overlap_top)
            
            face_ratio = face_overlap / text_area if text_area > 0 else 0
            return 1.0 - face_ratio * 0.5  # Penalize face coverage but not as harshly

    def adjust_position_for_visibility(
        self,
        text_bbox: BoundingBox,
        person_bbox: BoundingBox,
        canvas: CanvasConfig,
        depth: TextDepth,
        min_visibility: float = 0.5,
        max_attempts: int = 10,
    ) -> BoundingBox:
        current = text_bbox
        for attempt in range(max_attempts):
            visibility = self.calculate_visibility(current, person_bbox, canvas, depth)
            if visibility >= min_visibility:
                return current
            
            # Try shifting
            if depth == TextDepth.BEHIND:
                # Move away from person center
                person_cx = (person_bbox.x + person_bbox.width / 2)
                person_cy = (person_bbox.y + person_bbox.height / 2)
                text_cx = current.x + current.width / 2
                text_cy = current.y + current.height / 2
                
                dx = text_cx - person_cx
                dy = text_cy - person_cy
                
                # Normalize and push
                dist = math.hypot(dx, dy)
                if dist > 0:
                    push = 0.05
                    current = BoundingBox(
                        x=min(max(current.x + dx/dist * push, 0), 1 - current.width),
                        y=min(max(current.y + dy/dist * push, 0), 1 - current.height),
                        width=current.width,
                        height=current.height,
                    )
            else:
                # For front text, move down
                current = BoundingBox(
                    x=current.x,
                    y=min(current.y + 0.05, 1 - current.height),
                    width=current.width,
                    height=current.height,
                )
        
        return current

    def check_collision(
        self,
        bbox1: BoundingBox,
        bbox2: BoundingBox,
        canvas: CanvasConfig,
        padding: float = 0.02,
    ) -> bool:
        left1 = (bbox1.x - padding) * canvas.width
        right1 = (bbox1.x + bbox1.width + padding) * canvas.width
        top1 = (bbox1.y - padding) * canvas.height
        bottom1 = (bbox1.y + bbox1.height + padding) * canvas.height
        
        left2 = (bbox2.x - padding) * canvas.width
        right2 = (bbox2.x + bbox2.width + padding) * canvas.width
        top2 = (bbox2.y - padding) * canvas.height
        bottom2 = (bbox2.y + bbox2.height + padding) * canvas.height
        
        return not (right1 <= left2 or left1 >= right2 or bottom1 <= top2 or top1 >= bottom2)


class DepthPlanner:
    def __init__(self, layout_engine: LayoutEngine) -> None:
        self.layout_engine = layout_engine

    def decide_depth(
        self,
        segment: CaptionSegment,
        person_geometry: SubjectGeometry,
        canvas: CanvasConfig,
        regions: GeometryRegions,
        safe_area: BoundingBox,
        previous_depths: list[TextDepth],
    ) -> TextDepth:
        # If explicit depth is set, use it
        if segment.depth != TextDepth.BEHIND or hasattr(segment, '_explicit_depth'):
            return segment.depth
        
        # Auto mode: decide based on visibility
        test_bbox = self.layout_engine.find_best_position(
            segment.text, canvas, person_geometry, segment.scale,
            TextDepth.BEHIND, regions, safe_area
        )
        
        behind_visibility = self.layout_engine.calculate_visibility(
            test_bbox, person_geometry.bbox_normalized, canvas, TextDepth.BEHIND
        )
        
        test_bbox_front = self.layout_engine.find_best_position(
            segment.text, canvas, person_geometry, segment.scale,
            TextDepth.FRONT, regions, safe_area
        )
        
        front_visibility = self.layout_engine.calculate_visibility(
            test_bbox_front, person_geometry.bbox_normalized, canvas, TextDepth.FRONT
        )
        
        # Prefer behind if visibility is good
        if behind_visibility > 0.6:
            return TextDepth.BEHIND
        elif front_visibility > 0.7:
            return TextDepth.FRONT
        else:
            # Alternate to avoid monotony
            behind_count = sum(1 for d in previous_depths[-5:] if d == TextDepth.BEHIND)
            if behind_count >= 3:
                return TextDepth.FRONT
            return TextDepth.BEHIND