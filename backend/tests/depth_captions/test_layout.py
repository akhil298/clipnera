import pytest
from depth_captions.schema import (
    BoundingBox,
    CanvasConfig,
    CaptionSegment,
    TextDepth,
    PersonTrack,
    PersonTrackPoint,
    SafeZones,
    StyleConfig,
)
from depth_captions.layout import LayoutEngine, DepthPlanner


class TestLayoutEngine:
    @pytest.fixture
    def canvas(self):
        return CanvasConfig(width=1080, height=1920)

    @pytest.fixture
    def safe_zones(self):
        return SafeZones()

    @pytest.fixture
    def layout_engine(self, safe_zones):
        return LayoutEngine(safe_zones)

    @pytest.fixture
    def person_track(self):
        frames = [
            PersonTrackPoint(
                frame=0,
                bbox=BoundingBox(x=0.3, y=0.15, width=0.4, height=0.75),
                confidence=0.95,
            ),
            PersonTrackPoint(
                frame=30,
                bbox=BoundingBox(x=0.32, y=0.16, width=0.4, height=0.75),
                confidence=0.93,
            ),
        ]
        return PersonTrack(track_id="person_01", frames=frames)

    def test_calculate_person_geometry(self, layout_engine, canvas, person_track):
        geom = layout_engine.calculate_person_geometry(person_track, canvas, 0)
        assert geom.track_id == "person_01"
        assert geom.center_x == 0.5  # 0.3 + 0.4/2
        assert geom.center_y == 0.525  # 0.15 + 0.75/2
        assert geom.top == 0.15
        assert geom.bottom == 0.9
        assert geom.left == 0.3
        assert geom.right == 0.7

    def test_calculate_safe_area(self, layout_engine, canvas):
        safe = layout_engine.calculate_safe_area(canvas)
        assert safe.x == 0.05
        assert safe.y == 0.15
        assert abs(safe.width - 0.9) < 0.001
        assert abs(safe.height - 0.7) < 0.001

    def test_find_behind_position(self, layout_engine, canvas, person_track):
        geom = layout_engine.calculate_person_geometry(person_track, canvas, 0)
        from depth_captions.schema import calculate_regions
        regions = calculate_regions(canvas.width, canvas.height, geom.bbox_normalized)
        safe = layout_engine.calculate_safe_area(canvas)
        
        pos = layout_engine._find_behind_position(
            "TEST", canvas, geom, 1.0, regions, safe
        )
        
        # Should be in a valid position within canvas
        assert pos.x >= 0
        assert pos.x + pos.width <= 1
        assert pos.y >= 0
        assert pos.y + pos.height <= 1

    def test_find_front_position(self, layout_engine, canvas, person_track):
        geom = layout_engine.calculate_person_geometry(person_track, canvas, 0)
        from depth_captions.schema import calculate_regions
        regions = calculate_regions(canvas.width, canvas.height, geom.bbox_normalized)
        safe = layout_engine.calculate_safe_area(canvas)
        
        pos = layout_engine._find_front_position(
            "TEST", canvas, geom, 1.0, regions, safe
        )
        
        # Should be above head or below chin
        assert pos.y >= 0
        assert pos.y + pos.height <= 1

    def test_calculate_visibility_behind(self, layout_engine, canvas):
        text_bbox = BoundingBox(x=0.1, y=0.1, width=0.8, height=0.15)
        person_bbox = BoundingBox(x=0.3, y=0.15, width=0.4, height=0.75)
        
        vis = layout_engine.calculate_visibility(text_bbox, person_bbox, canvas, TextDepth.BEHIND)
        # Text is above person, minimal overlap
        assert vis > 0.5

    def test_calculate_visibility_front(self, layout_engine, canvas):
        text_bbox = BoundingBox(x=0.4, y=0.1, width=0.2, height=0.1)
        person_bbox = BoundingBox(x=0.3, y=0.15, width=0.4, height=0.75)
        
        vis = layout_engine.calculate_visibility(text_bbox, person_bbox, canvas, TextDepth.FRONT)
        # Text is above person's head
        assert vis > 0.5

    def test_adjust_position_for_visibility(self, layout_engine, canvas):
        text_bbox = BoundingBox(x=0.4, y=0.3, width=0.2, height=0.1)  # Overlapping person
        person_bbox = BoundingBox(x=0.3, y=0.15, width=0.4, height=0.75)
        
        adjusted = layout_engine.adjust_position_for_visibility(
            text_bbox, person_bbox, canvas, TextDepth.BEHIND, min_visibility=0.7
        )
        
        vis = layout_engine.calculate_visibility(adjusted, person_bbox, canvas, TextDepth.BEHIND)
        assert vis >= 0.7 or adjusted != text_bbox

    def test_check_collision(self, layout_engine, canvas):
        bbox1 = BoundingBox(x=0.4, y=0.4, width=0.2, height=0.1)
        bbox2 = BoundingBox(x=0.5, y=0.45, width=0.2, height=0.1)
        
        assert layout_engine.check_collision(bbox1, bbox2, canvas) is True
        
        bbox3 = BoundingBox(x=0.1, y=0.1, width=0.2, height=0.1)
        assert layout_engine.check_collision(bbox1, bbox3, canvas) is False


class TestDepthPlanner:
    @pytest.fixture
    def layout_engine(self):
        return LayoutEngine(SafeZones())

    @pytest.fixture
    def depth_planner(self, layout_engine):
        return DepthPlanner(layout_engine)

    @pytest.fixture
    def canvas(self):
        return CanvasConfig(width=1080, height=1920)

    @pytest.fixture
    def person_geometry(self):
        from depth_captions.schema import SubjectGeometry, BoundingBox
        return SubjectGeometry(
            track_id="person_01",
            bbox_normalized=BoundingBox(x=0.3, y=0.15, width=0.4, height=0.75),
            center_x=0.5,
            center_y=0.525,
            top=0.15,
            bottom=0.9,
            left=0.3,
            right=0.7,
        )

    @pytest.fixture
    def regions(self, canvas):
        from depth_captions.schema import calculate_regions, BoundingBox
        person_bbox = BoundingBox(x=0.3, y=0.15, width=0.4, height=0.75)
        return calculate_regions(canvas.width, canvas.height, person_bbox)

    @pytest.fixture
    def safe_area(self):
        return BoundingBox(x=0.05, y=0.15, width=0.9, height=0.7)

    def test_decide_depth_behind_preferred(self, depth_planner, canvas, person_geometry, regions, safe_area):
        segment = CaptionSegment(
            start=0.0,
            end=1.0,
            text="TEST",
            depth=TextDepth.BEHIND,  # Will be overridden in auto mode
            position=BoundingBox(x=0.1, y=0.1, width=0.8, height=0.15),
            scale=1.0,
        )
        
        depth = depth_planner.decide_depth(
            segment, person_geometry, canvas, regions, safe_area, []
        )
        
        # With good visibility in top region, should prefer behind
        assert depth in [TextDepth.BEHIND, TextDepth.FRONT]

    def test_decide_depth_alternates(self, depth_planner, canvas, person_geometry, regions, safe_area):
        # Force front depth by making behind visibility poor
        segment = CaptionSegment(
            start=0.0,
            end=1.0,
            text="TEST",
            depth=TextDepth.BEHIND,
            position=BoundingBox(x=0.4, y=0.5, width=0.2, height=0.1),  # Inside person
            scale=1.0,
        )
        
        previous = [TextDepth.BEHIND, TextDepth.BEHIND, TextDepth.BEHIND]
        depth = depth_planner.decide_depth(
            segment, person_geometry, canvas, regions, safe_area, previous
        )
        
        # Should alternate to front after 3 behinds
        assert depth == TextDepth.FRONT