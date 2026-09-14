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
)
from depth_captions.compositor import Compositor, FilterGraphBuilder, ASSCompositor


class TestCompositor:
    @pytest.fixture
    def edit_plan(self):
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
                    animation_in=AnimationType.POP,
                    animation_out=AnimationType.FADE,
                ),
            ],
        )

    def test_build_simple_text_graph(self, edit_plan):
        compositor = Compositor()
        graph = compositor._build_simple_text_graph(edit_plan)
        
        assert "drawtext" in graph
        assert "HELLO" in graph
        assert "WORLD" in graph
        assert "enable='between(t,0.0,1.0)'" in graph
        assert "enable='between(t,1.0,2.0)'" in graph
        assert "format=yuv420p" in graph

    def test_build_filter_graph_with_mattes(self, edit_plan):
        compositor = Compositor()
        from pathlib import Path
        matte_dir = Path("/tmp/mattes")
        
        graph = compositor._build_filter_graph(edit_plan, matte_dir)
        
        assert "drawtext" in graph
        assert "HELLO" in graph
        assert "WORLD" in graph
        # When matte dir is empty, it falls back to simple text graph
        assert "enable='between(t,0.0,1.0)'" in graph

    def test_color_to_ffmpeg(self, edit_plan):
        compositor = Compositor()
        
        # Test with opacity
        color = compositor._color_to_ffmpeg("#FFFFFF", 0.5)
        assert color.startswith("0x")
        assert len(color) == 10  # 0x + 8 hex chars
        
        # Test without opacity (full)
        color = compositor._color_to_ffmpeg("#FF0000", 1.0)
        assert "FF" in color


class TestFilterGraphBuilder:
    @pytest.fixture
    def edit_plan(self):
        style = STYLE_PRESETS[StylePreset.GIANT_EDITORIAL]
        return EditPlan(
            canvas=CanvasConfig(width=1080, height=1920),
            style=style,
            segments=[
                CaptionSegment(
                    start=0.0,
                    end=1.0,
                    text="TEST",
                    depth=TextDepth.BEHIND,
                    position=BoundingBox(x=0.1, y=0.1, width=0.8, height=0.15),
                    scale=1.0,
                ),
            ],
        )

    def test_build_depth_composition(self, edit_plan):
        builder = FilterGraphBuilder()
        graph = builder.build_depth_composition(edit_plan, num_matte_inputs=1)
        
        assert "split=2" in graph
        assert "alphamerge" in graph
        assert "drawtext" in graph
        assert "overlay" in graph
        assert "format=yuv420p" in graph


class TestASSCompositor:
    @pytest.fixture
    def edit_plan(self):
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
                    position=BoundingBox(x=0.5, y=0.5, width=0.8, height=0.15),
                    scale=1.2,
                ),
            ],
        )

    def test_generate_ass(self, edit_plan, tmp_path):
        compositor = ASSCompositor()
        ass_path = tmp_path / "test.ass"
        
        compositor._generate_ass(edit_plan, ass_path)
        
        assert ass_path.exists()
        content = ass_path.read_text(encoding="utf-8")
        
        assert "[Script Info]" in content
        assert "[V4+ Styles]" in content
        assert "[Events]" in content
        assert "HELLO" in content
        assert "Style: Default" in content
        assert "Dialogue:" in content

    def test_format_ass_time(self, edit_plan):
        compositor = ASSCompositor()
        
        assert compositor._format_ass_time(0.0) == "0:00:00.00"
        assert compositor._format_ass_time(1.5) == "0:00:01.50"
        assert compositor._format_ass_time(65.25) == "0:01:05.25"
        assert compositor._format_ass_time(3661.75) == "1:01:01.75"

    def test_color_to_ass(self, edit_plan):
        compositor = ASSCompositor()
        
        # White
        color = compositor._color_to_ass("#FFFFFF")
        assert color == "&HFFFFFFFF"
        
        # Red (ASS uses AABBGGRR format)
        color = compositor._color_to_ass("#FF0000")
        assert color == "&HFF0000FF"
        
        # With alpha
        color = compositor._color_to_ass("#FF000080")
        assert color.startswith("&H80")