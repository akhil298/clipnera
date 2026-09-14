import pytest
from depth_captions.schema import (
    EditPlan,
    CaptionSegment,
    CanvasConfig,
    StyleConfig,
    BoundingBox,
    TextDepth,
    AnimationType,
    SafeZones,
    StylePreset,
    STYLE_PRESETS,
    DepthMode,
)
from depth_captions.planner import PlanValidator, LLMPlanner


class TestPlanValidator:
    @pytest.fixture
    def valid_plan(self):
        style = STYLE_PRESETS[StylePreset.GIANT_EDITORIAL]
        return EditPlan(
            canvas=CanvasConfig(width=1080, height=1920),
            style=style,
            segments=[
                CaptionSegment(
                    start=0.0,
                    end=1.0,
                    text="HELLO",
                    depth=TextDepth.BEHIND,
                    position=BoundingBox(x=0.1, y=0.1, width=0.8, height=0.15),
                    scale=1.2,
                    rotation=2.0,
                    opacity=0.95,
                    animation_in=AnimationType.SCALE_UP,
                    animation_out=AnimationType.FADE,
                ),
                CaptionSegment(
                    start=1.0,
                    end=2.0,
                    text="WORLD",
                    depth=TextDepth.FRONT,
                    position=BoundingBox(x=0.1, y=0.7, width=0.8, height=0.15),
                    scale=1.0,
                    rotation=0.0,
                    opacity=1.0,
                    animation_in=AnimationType.POP,
                    animation_out=AnimationType.FADE,
                ),
            ],
            depth_mode=DepthMode.AUTO,
            safe_zones=SafeZones(),
        )

    def test_validate_valid_plan(self, valid_plan):
        valid, errors = PlanValidator.validate(valid_plan)
        assert valid is True
        assert len(errors) == 0

    def test_validate_invalid_timing(self):
        style = STYLE_PRESETS[StylePreset.GIANT_EDITORIAL]
        plan = EditPlan(
            canvas=CanvasConfig(width=1080, height=1920),
            style=style,
            segments=[
                CaptionSegment(
                    start=0.0,
                    end=1.0,
                    text="TEST",
                    position=BoundingBox(x=0.1, y=0.1, width=0.8, height=0.15),
                ),
            ],
        )
        plan.segments[0].start = 2.0
        plan.segments[0].end = 1.0
        valid, errors = PlanValidator.validate(plan)
        assert valid is False
        assert any("start >= end" in e for e in errors)

    def test_validate_position_out_of_bounds(self):
        style = STYLE_PRESETS[StylePreset.GIANT_EDITORIAL]
        plan = EditPlan(
            canvas=CanvasConfig(width=1080, height=1920),
            style=style,
            segments=[
                CaptionSegment(
                    start=0.0,
                    end=1.0,
                    text="TEST",
                    position=BoundingBox(x=0.1, y=0.1, width=0.8, height=0.15),
                ),
            ],
        )
        plan.segments[0].position.x = 1.5
        valid, errors = PlanValidator.validate(plan)
        assert valid is False
        assert any("out of bounds" in e for e in errors)

    def test_validate_scale_out_of_range(self):
        style = STYLE_PRESETS[StylePreset.GIANT_EDITORIAL]
        plan = EditPlan(
            canvas=CanvasConfig(width=1080, height=1920),
            style=style,
            segments=[
                CaptionSegment(
                    start=0.0,
                    end=1.0,
                    text="TEST",
                    position=BoundingBox(x=0.1, y=0.1, width=0.8, height=0.15),
                    scale=1.0,
                ),
            ],
        )
        plan.segments[0].scale = 3.0
        valid, errors = PlanValidator.validate(plan)
        assert valid is False
        assert any("scale out of range" in e for e in errors)

    def test_validate_rotation_out_of_range(self):
        style = STYLE_PRESETS[StylePreset.GIANT_EDITORIAL]
        plan = EditPlan(
            canvas=CanvasConfig(width=1080, height=1920),
            style=style,
            segments=[
                CaptionSegment(
                    start=0.0,
                    end=1.0,
                    text="TEST",
                    position=BoundingBox(x=0.1, y=0.1, width=0.8, height=0.15),
                    rotation=0.0,
                ),
            ],
        )
        plan.segments[0].rotation = 10.0
        valid, errors = PlanValidator.validate(plan)
        assert valid is False
        assert any("rotation out of range" in e for e in errors)

    def test_validate_invalid_depth(self):
        style = STYLE_PRESETS[StylePreset.GIANT_EDITORIAL]
        plan = EditPlan(
            canvas=CanvasConfig(width=1080, height=1920),
            style=style,
            segments=[
                CaptionSegment(
                    start=0.0,
                    end=1.0,
                    text="TEST",
                    position=BoundingBox(x=0.1, y=0.1, width=0.8, height=0.15),
                    depth=TextDepth.BEHIND,
                ),
            ],
        )
        plan.segments[0].depth = "invalid_depth"  # type: ignore
        valid, errors = PlanValidator.validate(plan)
        assert valid is False
        assert any("invalid depth" in e for e in errors)

    def test_validate_invalid_animation(self):
        style = STYLE_PRESETS[StylePreset.GIANT_EDITORIAL]
        plan = EditPlan(
            canvas=CanvasConfig(width=1080, height=1920),
            style=style,
            segments=[
                CaptionSegment(
                    start=0.0,
                    end=1.0,
                    text="TEST",
                    position=BoundingBox(x=0.1, y=0.1, width=0.8, height=0.15),
                    animation_in=AnimationType.SCALE_UP,
                ),
            ],
        )
        plan.segments[0].animation_in = "invalid_animation"  # type: ignore
        valid, errors = PlanValidator.validate(plan)
        assert valid is False
        assert any("invalid animation_in" in e for e in errors)

    def test_repair_fixes_timing(self):
        style = STYLE_PRESETS[StylePreset.GIANT_EDITORIAL]
        plan = EditPlan(
            canvas=CanvasConfig(width=1080, height=1920),
            style=style,
            segments=[
                CaptionSegment(
                    start=0.0,
                    end=1.0,
                    text="TEST",
                    position=BoundingBox(x=0.1, y=0.1, width=0.8, height=0.15),
                ),
            ],
        )
        plan.segments[0].start = 2.0
        plan.segments[0].end = 1.0
        repaired = PlanValidator.repair(plan, CanvasConfig(width=1080, height=1920))
        assert repaired.segments[0].end > repaired.segments[0].start

    def test_repair_clamps_position(self):
        style = STYLE_PRESETS[StylePreset.GIANT_EDITORIAL]
        plan = EditPlan(
            canvas=CanvasConfig(width=1080, height=1920),
            style=style,
            segments=[
                CaptionSegment(
                    start=0.0,
                    end=1.0,
                    text="TEST",
                    position=BoundingBox(x=0.1, y=0.1, width=0.8, height=0.15),
                ),
            ],
        )
        plan.segments[0].position.x = 1.5
        plan.segments[0].position.y = -0.1
        repaired = PlanValidator.repair(plan, CanvasConfig(width=1080, height=1920))
        pos = repaired.segments[0].position
        assert 0 <= pos.x <= 1 - pos.width
        assert 0 <= pos.y <= 1 - pos.height


class TestLLMPlanner:
    @pytest.fixture
    def planner(self):
        return LLMPlanner()

    def test_build_prompt_structure(self, planner):
        from depth_captions.schema import (
            TranscriptSegment, TranscriptWord, PersonTrack, PersonTrackPoint,
            CanvasConfig, StyleConfig, SafeZones, BoundingBox
        )
        
        transcript = [
            TranscriptSegment(
                start=0.0,
                end=2.0,
                text="Hello world",
                speaker="SPEAKER_01",
                words=[
                    TranscriptWord(start=0.0, end=1.0, text="Hello", speaker="SPEAKER_01"),
                    TranscriptWord(start=1.0, end=2.0, text="world", speaker="SPEAKER_01"),
                ],
            ),
        ]
        
        canvas = CanvasConfig(width=1080, height=1920)
        style = STYLE_PRESETS[StylePreset.GIANT_EDITORIAL]
        
        frames = [PersonTrackPoint(frame=0, bbox=BoundingBox(x=0.3, y=0.15, width=0.4, height=0.75), confidence=0.95)]
        tracks = {"person_01": PersonTrack(track_id="person_01", frames=frames)}
        
        safe_zones = SafeZones()
        video_metadata = {"duration": 30, "fps": 30, "width": 1080, "height": 1920}
        
        prompt = planner._build_prompt(transcript, canvas, style, tracks, DepthMode.AUTO, safe_zones, video_metadata)
        
        assert "VIDEO PROPERTIES" in prompt
        assert "SUBJECT POSITION" in prompt
        assert "SAFE AREA" in prompt
        assert "TRANSCRIPT" in prompt
        assert "STYLE PRESET" in prompt
        assert "DEPTH MODE" in prompt
        assert "SCHEMA" in prompt
        assert "Hello world" in prompt

    def test_parse_llm_response_valid(self, planner):
        response = '''
        Here is the plan:
        {
          "segments": [
            {"start": 0.0, "end": 1.0, "text": "TEST", "depth": "behind", "position": {"x": 0.1, "y": 0.1, "width": 0.8, "height": 0.15}, "scale": 1.0, "rotation": 0, "opacity": 0.95, "animation_in": "scale_up", "animation_out": "fade", "subject_id": "person_01"}
          ]
        }
        '''
        result = planner._parse_llm_response(response)
        assert "segments" in result
        assert len(result["segments"]) == 1
        assert result["segments"][0]["text"] == "TEST"

    def test_parse_llm_response_no_json(self, planner):
        with pytest.raises(ValueError):
            planner._parse_llm_response("No JSON here")