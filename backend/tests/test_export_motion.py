"""The export draws what the Timeline holds: speed, moving framing, layers and every library sound."""

from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path

import pytest

from brain import library
from brain.render_adapter import preview_size, to_reel
from edit_engine.keyframes import curve, moves
from edit_engine.render import framing_filters, render, tempo
from editor.timeline import Timeline


def _value(expr: str, var: str, at: float) -> float:
    """Evaluate one of our FFmpeg expressions in Python (if/lt/min/max are all it uses)."""
    names = {"if_": lambda c, a, b: a if c else b, "lt": lambda a, b: a < b, "min": min, "max": max, "v": at}
    return eval(expr.replace("if(", "if_(").replace(var, "v"), {"__builtins__": {}}, names)  # noqa: S307


def test_a_keyframed_value_moves_with_the_ease_of_the_point_it_moves_towards():
    points = [(1.0, 1.0, "linear"), (2.0, 2.0, "in"), (3.0, 1.5, "out")]
    expr = curve(points, "TIME")
    assert [round(_value(expr, "TIME", t), 4) for t in (0.0, 1.0, 1.5, 2.0, 2.5, 3.0, 9.0)] == [1.0, 1.0, 1.25, 2.0, 1.625, 1.5, 1.5]
    assert moves(points) and not moves([(0.0, 1.2, "linear"), (1.0, 1.2, "linear")]) and not moves(None)


def test_tempo_chains_atempo_within_its_range():
    assert tempo(1.0) == ""
    assert tempo(0.5) == "atempo=0.5000,"
    assert tempo(0.25) == "atempo=0.5000,atempo=0.5000,"
    assert tempo(4.0) == "atempo=2.0000,atempo=2.0000,"


def test_a_moving_zoom_is_drawn_frame_by_frame_and_a_held_one_is_cropped_once():
    held = framing_filters({"zoom": 1.2, "crop_x": 0.4}, (1080, 1920))
    assert held[0].startswith("crop=") and "zoompan" not in "".join(held)
    moving = framing_filters({"zoom": 1.1, "motion": {"zoom": [(0.0, 1.0, "linear"), (1.0, 1.5, "in_out")]}}, (1080, 1920))
    assert moving[1] == "scale=2160:3840" and moving[2].startswith("zoompan=z='(") and "s=1080x1920" in moving[2]


def _timeline() -> Timeline:
    return Timeline.model_validate({
        "fps": 30, "width": 1920, "height": 1080,
        "assets": {
            "a1": {"id": "a1", "kind": "video", "key": "k/a.mp4", "frames": 300, "has_audio": True},
            "b1": {"id": "b1", "kind": "video", "key": "k/b.mp4", "frames": 300},
            "i1": {"id": "i1", "kind": "image", "key": "k/i.png", "frames": 1},
        },
        "tracks": [
            {"id": "v1", "kind": "video", "extra": {"role": "main"}, "items": [
                # 1 s of footage at half speed: 2 s on the timeline, zooming in over its first second.
                {"type": "clip", "id": "c1", "at": 0, "asset": "a1", "src_in": 0, "src_out": 30, "speed": 0.5,
                 "keyframes": {"scale": [{"f": 0, "v": 1}, {"f": 30, "v": 1.4, "ease": "out"}]}},
            ]},
            {"id": "o1", "kind": "overlay", "items": [
                {"type": "clip", "id": "br", "at": 15, "asset": "b1", "src_in": 30, "src_out": 45,
                 "transition_in": {"type": "fade", "frames": 6}},
                {"type": "clip", "id": "pip", "at": 30, "asset": "i1", "src_in": 0, "src_out": 30,
                 "transform": {"x": 0.8, "y": 0.25, "scale": 0.3}},
            ]},
            {"id": "g1", "kind": "graphic", "items": [
                {"type": "graphic", "id": "fl", "at": 45, "dur": 2, "extra": {"solid": "#FFFFFF"}},
                {"type": "graphic", "id": "gr", "at": 30, "dur": 30, "extra": {"graphic": "light_leak"}},
            ]},
            {"id": "a2", "kind": "audio", "items": [{"type": "sfx", "id": "s1", "at": 15, "name": "ding", "dur": 15, "gain_db": -3}]},
        ],
    })


def test_the_compiled_timeline_carries_speed_motion_layers_and_library_sounds():
    compiled, order = to_reel(_timeline(), {})
    shot = compiled["picture"][0]
    assert shot["speed"] == 0.5 and shot["motion"] == {"zoom": [(0.0, 1.0, "linear"), (1.0, 1.4, "out")]}
    assert compiled["voice"][0]["speed"] == 0.5 and compiled["duration"] == 2.0
    kinds = [(layer["kind"], layer["at"], layer["dur"]) for layer in compiled["layers"]]
    assert kinds == [("video", 0.5, 0.5), ("image", 1.0, 1.0), ("graphic", 1.0, 1.0), ("solid", 1.5, 0.067)]
    broll, pip = compiled["layers"][:2]
    assert broll["fade_in"] == 0.2 and broll["in"] == 1.0 and broll["scale"] == 1.0
    assert pip["scale"] == 0.3 and (pip["x"], pip["y"]) == (0.8, 0.25)
    assert compiled["layers"][2]["path"] == str(library.graphics()["light_leak"].video)
    assert compiled["sfx"] == [{"name": "ding", "path": str(library.SFX_DIR / library.sounds()["ding"].file), "at": 0.5, "gain_db": -3.0}]
    assert order == ["a1", "b1", "i1"]


def test_the_check_render_keeps_the_edits_shape():
    assert preview_size(_timeline()) == (640, 360)
    assert preview_size(Timeline.model_validate({"width": 1080, "height": 1920})) == (360, 640)


def _ffmpeg(*args: str) -> None:
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args], check=True)


@pytest.mark.skipif(subprocess.run(["which", "ffmpeg"], capture_output=True).returncode != 0, reason="needs ffmpeg")
def test_a_slowed_zooming_shot_with_layers_and_sounds_renders_at_its_length(tmp_path: Path):
    footage, image = tmp_path / "a.mp4", tmp_path / "i.png"
    _ffmpeg("-f", "lavfi", "-i", "testsrc2=s=1280x720:r=30:d=3", "-f", "lavfi", "-i", "sine=f=220:d=3",
            "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", "-shortest", str(footage))
    _ffmpeg("-f", "lavfi", "-i", "color=c=red:s=400x400:d=1", "-frames:v", "1", str(image))
    compiled, order = to_reel(_timeline(), {}, size=(640, 360))
    sources = {i: {"a1": footage, "b1": footage, "i1": image}[a] for i, a in enumerate(order)}
    out = asyncio.run(render(compiled, sources, None, watermark=False, work=tmp_path))
    probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=width,height",
                            "-of", "csv=p=0", str(out)], capture_output=True, text=True, check=True).stdout.split()
    assert probe[0] == "640,360" and abs(float(probe[-1]) - 2.0) < 0.2
