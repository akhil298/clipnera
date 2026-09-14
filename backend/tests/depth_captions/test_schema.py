import pytest
from depth_captions.schema import (
    DepthMode,
    AnimationType,
    TextDepth,
    StylePreset,
    BoundingBox,
    PersonTrackPoint,
    PersonTrack,
    CanvasConfig,
    StyleConfig,
    STYLE_PRESETS,
    CaptionSegment,
    EditPlan,
    DepthCaptionRequest,
    SafeZones,
    calculate_regions,
    GeometryRegions,
)


class TestSchemaValidation:
    def test_bounding_box_normalized(self):
        bbox = BoundingBox(x=0.1, y=0.2, width=0.3, height=0.4)
        assert bbox.x == 0.1
        assert bbox.y == 0.2
        assert bbox.width == 0.3
        assert bbox.height == 0.4

    def test_bounding_box_out_of_bounds_raises(self):
        with pytest.raises(ValueError):
            BoundingBox(x=1.5, y=0.2, width=0.3, height=0.4)
        with pytest.raises(ValueError):
            BoundingBox(x=-0.1, y=0.2, width=0.3, height=0.4)

    def test_caption_segment_end_after_start(self):
        with pytest.raises(ValueError):
            CaptionSegment(
                start=2.0,
                end=1.0,
                text="test",
                position=BoundingBox(x=0, y=0, width=1, height=1),
            )

    def test_caption_segment_valid(self):
        seg = CaptionSegment(
            start=1.0,
            end=2.0,
            text="TEST",
            depth=TextDepth.BEHIND,
            position=BoundingBox(x=0.1, y=0.1, width=0.8, height=0.2),
            scale=1.2,
            rotation=3.0,
        )
        assert seg.start == 1.0
        assert seg.end == 2.0
        assert seg.depth == TextDepth.BEHIND
        assert seg.scale == 1.2
        assert seg.rotation == 3.0

    def test_caption_segment_scale_bounds(self):
        with pytest.raises(ValueError):
            CaptionSegment(
                start=1.0,
                end=2.0,
                text="test",
                position=BoundingBox(x=0, y=0, width=1, height=1),
                scale=3.0,  # > 2.0
            )
        with pytest.raises(ValueError):
            CaptionSegment(
                start=1.0,
                end=2.0,
                text="test",
                position=BoundingBox(x=0, y=0, width=1, height=1),
                scale=0.3,  # < 0.5
            )

    def test_caption_segment_rotation_bounds(self):
        with pytest.raises(ValueError):
            CaptionSegment(
                start=1.0,
                end=2.0,
                text="test",
                position=BoundingBox(x=0, y=0, width=1, height=1),
                rotation=10.0,  # > 8
            )
        with pytest.raises(ValueError):
            CaptionSegment(
                start=1.0,
                end=2.0,
                text="test",
                position=BoundingBox(x=0, y=0, width=1, height=1),
                rotation=-10.0,  # < -8
            )

    def test_edit_plan_validation(self):
        plan = EditPlan(
            canvas=CanvasConfig(width=1080, height=1920),
            style=STYLE_PRESETS[StylePreset.GIANT_EDITORIAL],
            segments=[
                CaptionSegment(
                    start=0.0,
                    end=1.0,
                    text="HELLO",
                    position=BoundingBox(x=0.1, y=0.1, width=0.8, height=0.2),
                ),
                CaptionSegment(
                    start=1.0,
                    end=2.0,
                    text="WORLD",
                    position=BoundingBox(x=0.1, y=0.4, width=0.8, height=0.2),
                ),
            ],
        )
        assert len(plan.segments) == 2
        assert plan.canvas.width == 1080
        assert plan.depth_mode == DepthMode.AUTO

    def test_style_presets_exist(self):
        assert StylePreset.GIANT_EDITORIAL in STYLE_PRESETS
        assert StylePreset.KINETIC_BOLD in STYLE_PRESETS
        assert StylePreset.MINIMAL in STYLE_PRESETS
        assert len(STYLE_PRESETS) == 10

    def test_depth_mode_values(self):
        assert DepthMode.BEHIND == "behind"
        assert DepthMode.FRONT == "front"
        assert DepthMode.AUTO == "auto"
        assert DepthMode.GIANT_EDITORIAL == "giant_editorial"

    def test_animation_type_values(self):
        assert AnimationType.NONE == "none"
        assert AnimationType.FADE == "fade"
        assert AnimationType.SCALE_UP == "scale_up"
        assert AnimationType.POP == "pop"


class TestGeometryCalculations:
    def test_calculate_regions(self):
        canvas_width = 1080
        canvas_height = 1920
        person_bbox = BoundingBox(x=0.3, y=0.15, width=0.4, height=0.75)
        
        regions = calculate_regions(canvas_width, canvas_height, person_bbox)
        
        assert isinstance(regions, GeometryRegions)
        # Top region: from top to person top
        assert regions.top_region.y == 0
        assert regions.top_region.height == person_bbox.y
        # Person zone
        assert regions.person_zone.x == person_bbox.x
        assert regions.person_zone.y == person_bbox.y
        assert regions.person_zone.width == person_bbox.width
        assert regions.person_zone.height == person_bbox.height
        # Bottom region: from person bottom to bottom
        assert regions.bottom_region.y == person_bbox.y + person_bbox.height
        assert regions.bottom_region.height == 1 - (person_bbox.y + person_bbox.height)

    def test_safe_zones_default(self):
        safe = SafeZones()
        assert safe.top == 0.15
        assert safe.bottom == 0.15
        assert safe.left == 0.05
        assert safe.right == 0.05


class TestDepthCaptionRequest:
    def test_default_request(self):
        req = DepthCaptionRequest(
            project_id="proj_123",
            clip_id="clip_456",
        )
        assert req.style == StylePreset.GIANT_EDITORIAL
        assert req.depth_mode == DepthMode.AUTO
        assert req.language == "en"

    def test_custom_request(self):
        req = DepthCaptionRequest(
            project_id="proj_123",
            clip_id="clip_456",
            style=StylePreset.KINETIC_BOLD,
            depth_mode=DepthMode.BEHIND,
            language="es",
        )
        assert req.style == StylePreset.KINETIC_BOLD
        assert req.depth_mode == DepthMode.BEHIND
        assert req.language == "es"