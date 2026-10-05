from __future__ import annotations

import json
import shutil
import subprocess

import pytest

from clip_generation.hook import Hook, on_output_timeline
from hook_transitions.catalog import (
    EFFECTS,
    FRAMING_EFFECTS,
    IMPACT_EFFECTS,
    IMPACT_SOUNDS,
    IMPACTS,
    MAX_EFFECTS,
    PHRASES,
    PRESET_LIST,
    PRESETS,
    SOUNDS,
    SOURCES,
    TEXT_STYLES,
    get_catalog,
)
from hook_transitions.graph import (
    EFFECT_BUILDERS,
    SOUND_BUILDERS,
    SOURCE_BUILDERS,
    BridgePlan,
    MediaInfo,
    timeline_graph,
)
from hook_transitions.resolver import ClipContext, detect_intents, hook_text_from, resolve_transition
from hook_transitions.schema import HookTransitionConfig
from hook_transitions.text import TEXT_STYLE_DEFS, bridge_ass

MEDIA = MediaInfo(width=540, height=960, fps=30.0, duration=8.0, has_audio=True)


class TestCatalog:
    def test_over_one_hundred_presets(self):
        assert len(PRESETS) >= 100
        assert len(PRESETS) == len(PRESET_LIST), "duplicate preset ids"

    def test_every_part_has_a_builder(self):
        assert set(SOURCES) == set(SOURCE_BUILDERS)
        assert set(EFFECTS) == set(EFFECT_BUILDERS)
        assert set(SOUNDS) == set(SOUND_BUILDERS)
        assert set(IMPACTS) == set(IMPACT_EFFECTS)
        assert set(TEXT_STYLES) == set(TEXT_STYLE_DEFS)
        assert all(effect in EFFECTS for effects in IMPACT_EFFECTS.values() for effect in effects)

    @pytest.mark.parametrize("preset", PRESET_LIST, ids=lambda p: p.id)
    def test_preset_is_valid(self, preset):
        assert preset.source in SOURCES
        assert all(effect in EFFECTS for effect in preset.effects)
        assert len(preset.effects) <= MAX_EFFECTS
        assert len(FRAMING_EFFECTS.intersection(preset.effects)) <= 1
        assert preset.sound in SOUNDS
        assert preset.impact in IMPACTS
        assert preset.impact_sound is None or preset.impact_sound in IMPACT_SOUNDS
        assert preset.text in (None, "auto") or preset.text in PHRASES
        assert preset.text_style in TEXT_STYLES
        # Every preset must also load through the public config schema.
        HookTransitionConfig(mode="preset", preset_id=preset.id)

    def test_catalog_payload(self):
        catalog = get_catalog()
        assert len(catalog["presets"]) == len(PRESETS)
        assert catalog["default_preset"] in PRESETS
        assert not any(s["id"] in ("hook_rewind", "hook_echo") for s in catalog["impact_sounds"])


class TestConfigValidation:
    def test_unknown_ids_rejected(self):
        for bad in ({"source": "nope"}, {"sound": "nope"}, {"effects": ["nope"]}, {"preset_id": "nope"}):
            with pytest.raises(ValueError):
                HookTransitionConfig(**{"mode": "custom", "source": "rewind", **bad})

    def test_two_framing_effects_rejected(self):
        with pytest.raises(ValueError):
            HookTransitionConfig(mode="custom", source="rewind", effects=["zoom_in", "shake"])

    def test_too_many_effects_rejected(self):
        with pytest.raises(ValueError):
            HookTransitionConfig(mode="custom", source="rewind", effects=["glitch", "vhs", "blur", "invert", "sepia"])

    def test_mode_requirements(self):
        with pytest.raises(ValueError):
            HookTransitionConfig(mode="preset")
        with pytest.raises(ValueError):
            HookTransitionConfig(mode="custom")

    def test_duration_bounds(self):
        with pytest.raises(ValueError):
            HookTransitionConfig(mode="auto", duration=5.0)


class TestResolver:
    def test_off_renders_nothing(self):
        assert resolve_transition({"mode": "off"}, ClipContext("c1")) is None

    def test_none_config_is_auto(self):
        spec = resolve_transition(None, ClipContext("c1", "comedy", "wait what happened here"))
        assert spec is not None and spec.preset_id in PRESETS

    def test_auto_is_stable_per_clip(self):
        context = ClipContext("clip-42", "podcast_interview", "Why did nobody tell me this?")
        assert resolve_transition(None, context) == resolve_transition(None, context)

    def test_auto_varies_across_clips(self):
        picks = {resolve_transition(None, ClipContext(f"clip-{i}", "gaming", "no way that just happened")).preset_id
                 for i in range(30)}
        assert len(picks) > 1

    def test_auto_prefers_presets_for_the_category(self):
        for i in range(20):
            preset = PRESETS[resolve_transition(None, ClipContext(f"g-{i}", "gaming", "")).preset_id]
            assert not preset.fits or "gaming" in preset.fits

    def test_question_hook_gets_an_answering_line(self):
        intents = detect_intents("Why do most startups fail?", "unknown")
        assert intents[0] == "question"
        spec = resolve_transition({"mode": "custom", "source": "blur_card", "text_id": "auto"},
                                  ClipContext("q", "unknown", "Why do most startups fail?"))
        assert spec.text in {p.text for p in PHRASES.values() if "question" in p.intents}

    def test_preset_parts_can_be_overridden(self):
        spec = resolve_transition(
            {"mode": "preset", "preset_id": "viral_rewind", "sound": "boom", "custom_text": "  Part   2 "},
            ClipContext("c"),
        )
        base = PRESETS["viral_rewind"]
        assert spec.source == base.source and spec.sound == "boom" and spec.text == "Part 2"

    def test_explicit_no_impact_sound_wins(self):
        spec = resolve_transition({"mode": "preset", "preset_id": "viral_rewind", "impact_sound": "none"}, ClipContext("c"))
        assert spec.impact_sound is None
        spec = resolve_transition({"mode": "preset", "preset_id": "viral_rewind"}, ClipContext("c"))
        assert spec.impact_sound == PRESETS["viral_rewind"].impact_sound

    def test_hook_text_from_transcript(self):
        transcript = [{"start": 0, "end": 3, "words": [
            {"start": 0.0, "end": 0.5, "word": "before"},
            {"start": 1.0, "end": 1.4, "word": "we"},
            {"start": 1.5, "end": 2.0, "word": "lost"},
        ]}]
        assert hook_text_from(transcript, 0.9, 2.1) == "we lost"


class TestTimeline:
    def test_gap_shifts_only_the_clip(self):
        items = [{"start": 51.0, "end": 51.5, "text": "hook"}, {"start": 40.5, "end": 41.0, "text": "clip"}]
        origin, placed = on_output_timeline(items, 40.0, 60.0, Hook(50.0, 52.0), gap=0.8)
        # The hook line plays twice: as the teaser, then where it is spoken.
        positions = [(i["text"], round(i["start"] - origin, 6)) for i in placed]
        assert positions == [("hook", 1.0), ("hook", pytest.approx(2.0 + 0.8 + 11.0)), ("clip", pytest.approx(3.3))]
        assert 60.0 - origin == pytest.approx(2.0 + 0.8 + 20.0)

    def test_no_plan_without_a_usable_hook(self):
        spec = resolve_transition(None, ClipContext("c"))
        assert BridgePlan.make(spec, None, MEDIA) is None
        assert BridgePlan.make(spec, 0.1, MEDIA) is None
        assert BridgePlan.make(None, 2.0, MEDIA) is None
        assert BridgePlan.make(spec, 7.5, MEDIA) is None

    def test_graph_concats_three_segments(self):
        spec = resolve_transition({"mode": "preset", "preset_id": "viral_rewind"}, ClipContext("c"))
        chains, video, audio, inputs = timeline_graph(BridgePlan.make(spec, 2.0, MEDIA), "ass=bridge.ass")[:4]
        graph = ";".join(chains)
        assert (video, audio, inputs) == ("vcat", "acat", 2)
        assert "concat=n=3:v=1:a=1[vjoin][acat]" in graph and "[vjoin]fps=30[vcat]" in graph
        assert "tpad" not in graph
        assert "ass=bridge.ass[gv]" in graph
        assert "areverse" in graph  # hook_rewind sound

    @pytest.mark.parametrize("source", ["sneak_peek", "flash_forward", "rewind", "freeze_frame"])
    def test_bridge_reads_its_own_input(self, source):
        """Regression: a bridge fed from a split of input 0 made FFmpeg queue
        every body frame until concat reached the body (gigabytes at 1080p)."""
        spec = resolve_transition({"mode": "custom", "source": source}, ClipContext("c"))
        timeline = timeline_graph(BridgePlan.make(spec, 2.0, MEDIA))
        graph = ";".join(timeline.chains)
        assert timeline.inputs == 2
        assert "[0:v]setpts=PTS-STARTPTS,split=2[vt][vb]" in graph and "[1:v]" in graph

    def test_generated_bridge_reads_once(self):
        spec = resolve_transition({"mode": "custom", "source": "black_card", "graphic": "none"}, ClipContext("c"))
        timeline = timeline_graph(BridgePlan.make(spec, 2.0, MEDIA))
        assert timeline.inputs == 1 and "[1:v]" not in ";".join(timeline.chains)
        assert timeline.extra_inputs == ()

    def test_silent_clip_gets_generated_audio(self):
        silent = MediaInfo(540, 960, 25.0, 8.0, has_audio=False)
        spec = resolve_transition({"mode": "custom", "source": "rewind", "sound": "hook_rewind"}, ClipContext("c"))
        graph = ";".join(timeline_graph(BridgePlan.make(spec, 2.0, silent))[0])
        assert "[0:a]" not in graph and "anullsrc" in graph


class TestBridgeText:
    @pytest.mark.parametrize("style", sorted(TEXT_STYLE_DEFS))
    def test_style_renders_one_centred_line(self, style):
        doc = bridge_ass("Wait {for} it", style, 1080, 1920, 1.2)
        events = [line for line in doc.splitlines() if line.startswith("Dialogue:")]
        assert len(events) == 1
        assert "0:00:01.20" in events[0] and "\\pos(540,960)" in events[0]
        assert "{for}" not in events[0]

    def test_uppercase_styles(self):
        assert "WAIT FOR IT" in bridge_ass("Wait for it", "impact_caps", 1080, 1920, 1.0)


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")
class TestRender:
    def test_preset_renders_at_the_planned_length(self, tmp_path):
        src = tmp_path / "cut.mp4"
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc2=size=320x568:rate=30:duration=5",
             "-f", "lavfi", "-i", "sine=frequency=330:duration=5", "-c:v", "libx264", "-pix_fmt", "yuv420p",
             "-c:a", "aac", "-shortest", str(src)],
            check=True,
        )
        media = MediaInfo(320, 568, 30.0, 5.0, True)
        spec = resolve_transition(
            {"mode": "custom", "source": "flash_forward", "effects": ["crash_zoom", "glitch"], "sound": "riser",
             "impact": "punch_zoom", "impact_sound": "boom", "text_id": "none", "duration": 1.0},
            ClipContext("c"),
        )
        timeline = timeline_graph(BridgePlan.make(spec, 1.5, media))
        chains, video, audio, inputs = timeline[:4]
        out = tmp_path / "out.mp4"
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", *["-i", str(src)] * inputs,
             *[a for extra in timeline.extra_inputs for a in ("-i", extra)], "-filter_complex", ";".join(chains),
             "-map", f"[{video}]", "-map", f"[{audio}]", "-c:v", "libx264", "-preset", "ultrafast", str(out)],
            check=True,
        )
        # Count video frames, not container duration: the audio alone filled
        # the duration while tpad left freeze bridges with no frames at all.
        frames = subprocess.check_output(
            ["ffprobe", "-v", "error", "-select_streams", "v", "-count_frames",
             "-show_entries", "stream=nb_read_frames", "-of", "csv=p=0", str(out)],
        )
        assert int(frames) == pytest.approx(6.0 * 30, abs=2)

    def test_freeze_bridge_has_every_frame(self, tmp_path):
        src = tmp_path / "cut.mp4"
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc2=size=320x568:rate=30:duration=5",
             "-f", "lavfi", "-i", "sine=frequency=330:duration=5", "-c:v", "libx264", "-pix_fmt", "yuv420p",
             "-c:a", "aac", "-shortest", str(src)],
            check=True,
        )
        spec = resolve_transition({"mode": "custom", "source": "blur_card", "sound": "whoosh", "text_id": "none",
                                   "duration": 1.0}, ClipContext("c"))
        timeline = timeline_graph(BridgePlan.make(spec, 1.5, MediaInfo(320, 568, 30.0, 5.0, True)))
        chains, video, audio, inputs = timeline[:4]
        out = tmp_path / "out.mp4"
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", *["-i", str(src)] * inputs,
             *[a for extra in timeline.extra_inputs for a in ("-i", extra)], "-filter_complex", ";".join(chains),
             "-map", f"[{video}]", "-map", f"[{audio}]", "-c:v", "libx264", "-preset", "ultrafast", str(out)],
            check=True,
        )
        frames = subprocess.check_output(
            ["ffprobe", "-v", "error", "-select_streams", "v", "-count_frames",
             "-show_entries", "stream=nb_read_frames", "-of", "csv=p=0", str(out)],
        )
        assert int(frames) == pytest.approx(6.0 * 30, abs=2)



class TestBridgeGraphics:
    """Motion graphics from static/hook_graphics laid over the bridge, each with its sound."""

    def test_library_has_every_rendered_graphic_with_its_sound(self):
        from hook_transitions.graphics import library

        graphics = library()
        assert len(graphics) >= 10
        for graphic in graphics.values():
            assert graphic.video.exists() and graphic.sfx is not None and graphic.sfx.exists()

    def test_auto_picks_a_graphic_and_varies_it_across_clips(self):
        picks = {resolve_transition(None, ClipContext(f"clip-{i}", "podcast_interview", "Why?")).graphic for i in range(40)}
        assert None not in picks
        assert len(picks) >= 6

    def test_a_clip_keeps_its_graphic_on_re_export(self):
        first = resolve_transition(None, ClipContext("same", "comedy", "lol"))
        assert resolve_transition(None, ClipContext("same", "comedy", "lol")).graphic == first.graphic

    def test_graphic_can_be_chosen_or_turned_off(self):
        assert resolve_transition({"mode": "auto", "graphic": "lightning"}, ClipContext("c")).graphic == "lightning"
        assert resolve_transition({"mode": "auto", "graphic": "none"}, ClipContext("c")).graphic is None
        with pytest.raises(ValueError):
            resolve_transition({"mode": "auto", "graphic": "not_a_graphic"}, ClipContext("c"))

    def test_graph_overlays_the_graphic_under_the_bridge_text_and_mixes_its_sound(self):
        spec = resolve_transition({"mode": "auto", "graphic": "shockwave"}, ClipContext("c"))
        timeline = timeline_graph(BridgePlan.make(spec, 2.0, MEDIA), "ass=bridge.ass")
        graph = ";".join(timeline.chains)
        assert timeline.extra_inputs[0].endswith("shockwave.mp4") and timeline.extra_inputs[1].endswith(".wav")
        assert "alphamerge" in graph and "[gv1]ass=bridge.ass[gv]" in graph
        assert "[ga1][gsfx]amix" in graph

    @pytest.mark.parametrize("ratio", [(320, 568), (568, 320)])
    def test_bridge_with_a_graphic_renders_at_the_planned_length(self, tmp_path, ratio):
        width, height = ratio
        src = tmp_path / "cut.mp4"
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"testsrc2=size={width}x{height}:rate=30:duration=5",
             "-f", "lavfi", "-i", "sine=frequency=330:duration=5", "-c:v", "libx264", "-pix_fmt", "yuv420p",
             "-c:a", "aac", "-shortest", str(src)],
            check=True,
        )
        spec = resolve_transition({"mode": "custom", "source": "freeze_frame", "graphic": "particle_burst",
                                   "text_id": "none", "duration": 0.8}, ClipContext("c"))
        timeline = timeline_graph(BridgePlan.make(spec, 1.5, MediaInfo(width, height, 30.0, 5.0, True)))
        out = tmp_path / "out.mp4"
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", *["-i", str(src)] * timeline.inputs,
             *[a for extra in timeline.extra_inputs for a in ("-i", extra)],
             "-filter_complex", ";".join(timeline.chains), "-map", f"[{timeline.video}]", "-map", f"[{timeline.audio}]",
             "-c:v", "libx264", "-preset", "ultrafast", str(out)],
            check=True,
        )
        frames = subprocess.check_output(
            ["ffprobe", "-v", "error", "-select_streams", "v", "-count_frames",
             "-show_entries", "stream=nb_read_frames", "-of", "csv=p=0", str(out)],
        )
        assert int(frames) == pytest.approx(5.8 * 30, abs=2)
