"""A compiled timeline, rendered on CPU with FFmpeg.

1. Every picture item becomes a segment in one shared format (cropped to the
   reel's shape, exposure-corrected, graded with the look), so the segments
   join by stream copy.
2. The audio is mixed in one filter graph: the voice pieces (with 15 ms fades
   so cuts never click) through a cleanup chain, the music ducked under the
   voice, the sound effects placed so their peak lands on the cut, and the
   lot mastered to -14 LUFS, Instagram's loudness.
3. Captions, the hook, pop-ups and script lines are burned in one last pass;
   on Free the Clipnera intro, watermark and end card are added on top.

Every function takes local paths; nothing here touches the database or S3.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from branding.service import added_seconds
from broll.renditions import run
from core.logging_config import get_logger
from edit_engine.looks import exposure_filter, look_filter
from edit_engine.perception import probe_media
from hook_transitions.graph import SAMPLE_RATE, SOUND_BUILDERS
from reels import render as reel_render
from subtitle_styling.ass_generator import AssGenerator, ass_time, escape_ass, script_font
from subtitle_styling.emoji_art import colourize
from subtitle_styling.templates import DEFAULT_STYLE

log = get_logger(__name__)

PARALLEL_SEGMENTS = 2
ENCODE = [
    "-c:v", "libx264", "-preset", "ultrafast", "-crf", "17", "-pix_fmt", "yuv420p", "-r", "30",
    "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv", "-an",
]
CARD_STYLE = reel_render.style_for("bold")
FADE = 0.015
# name -> (builder in hook_transitions.graph, seconds, where its peak is)
SFX: dict[str, tuple[str, float, float]] = {
    "hit": ("impact_hit", 0.8, 0.0),
    "pop": ("pop", 0.3, 0.02),
    "whoosh": ("whoosh", 0.5, 0.25),
    "ding": ("ding", 1.0, 0.0),
}
SFX_GAIN_DB = -12.0
# Instagram plays reels at about -14 LUFS; mastering there keeps ours from sounding quiet.
LOUDNESS_TARGET = "I=-14:TP=-1:LRA=11"
VOICE_CHAIN = "highpass=f=80,afftdn=nf=-25,acompressor=threshold=-18dB:ratio=3:attack=5:release=80"
STEREO = f"aresample={SAMPLE_RATE},aformat=sample_fmts=fltp:channel_layouts=stereo"


def crop_filter(zoom: float, crop_x: float | None) -> str:
    """Cut the reel's 9:16 frame out of any source shape, centred on the face (or the middle)."""
    centre = 0.5 if crop_x is None else min(1.0, max(0.0, crop_x))
    w = f"min(iw\\,ih*9/16)/{zoom:.3f}"
    h = f"min(ih\\,iw*16/9)/{zoom:.3f}"
    return f"crop=w='{w}':h='{h}':x='max(0\\,min(iw-ow\\,{centre:.3f}*iw-ow/2))':y='(ih-oh)*0.45'"


def video_segment_cmd(src: Path, item: dict[str, Any], look: str, size: tuple[int, int], out: Path) -> list[str]:
    filters = [crop_filter(item.get("zoom") or 1.0, item.get("crop_x")), f"scale={size[0]}:{size[1]}", "setsar=1"]
    exposure = exposure_filter(item.get("brightness"))
    filters += [f for f in (exposure, look_filter(look)) if f]
    filters += ["fps=30", "scale=out_range=tv:out_color_matrix=bt709", "format=yuv420p"]
    return [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
        "-ss", f"{item['in']:.3f}", "-t", f"{item['out'] - item['in']:.3f}", "-i", str(src),
        "-vf", ",".join(filters), *ENCODE, str(out),
    ]


async def render_segments(timeline: dict[str, Any], sources: dict[int, Path], work: Path) -> list[Path]:
    size = (timeline["width"], timeline["height"])
    slots = asyncio.Semaphore(PARALLEL_SEGMENTS)

    async def segment(index: int, item: dict[str, Any]) -> Path:
        out = work / f"seg{index:04d}.mp4"
        async with slots:
            if item["kind"] == "video":
                await run(video_segment_cmd(sources[item["src"]], item, timeline["look"], size, out))
            elif item["kind"] == "image":
                await run(reel_render.still_cmd(sources[item["src"]], item["dur"], out, blur_fill=True, size=size))
            else:
                card = reel_render.text_card(item.get("text") or " ", CARD_STYLE, work / f"card{index}.png", size=size)
                await run(reel_render.still_cmd(card, item["dur"], out, blur_fill=False, size=size))
        return out

    return list(await asyncio.gather(*(segment(i, item) for i, item in enumerate(timeline["picture"]))))


def _voice_graph(pieces: list[dict[str, Any]], inputs: dict[int, int], duration: float) -> tuple[list[str], str]:
    """Voice pieces laid end to end, with silence where the picture has a card."""
    parts, chains, cursor = [], [], 0.0
    for n, piece in enumerate(sorted(pieces, key=lambda p: p["at"])):
        gap = piece["at"] - cursor
        if gap > 0.005:
            chains.append(f"anullsrc=r={SAMPLE_RATE}:cl=stereo,atrim=duration={gap:.3f}[gap{n}]")
            parts.append(f"[gap{n}]")
        length = piece["out"] - piece["in"]
        chains.append(
            f"[{inputs[piece['src']]}:a]atrim=start={piece['in']:.3f}:end={piece['out']:.3f},asetpts=PTS-STARTPTS,{STEREO},"
            f"afade=t=in:d={FADE},afade=t=out:st={max(0.0, length - FADE):.3f}:d={FADE}[vp{n}]"
        )
        parts.append(f"[vp{n}]")
        cursor = piece["at"] + length
    chains.append(f"{''.join(parts)}concat=n={len(parts)}:v=0:a=1,{VOICE_CHAIN},apad=whole_dur={duration:.3f},"
                  f"atrim=duration={duration:.3f}[voice]")
    return chains, "[voice]"


def _sfx_chain(cue: dict[str, Any], n: int) -> str:
    builder, seconds, peak = SFX[cue["sound"]]
    delay = max(0, round((cue["at"] - peak) * 1000))
    return (f"{SOUND_BUILDERS[builder](None, seconds, None)},{STEREO},volume={SFX_GAIN_DB}dB,"
            f"adelay={delay}|{delay}[sfx{n}]")


def audio_mix_cmd(timeline: dict[str, Any], sources: dict[int, Path], music: Path | None, out: Path) -> list[str] | None:
    """One FFmpeg command mixing voice, music and SFX into ``out``; None when the reel is silent."""
    duration = timeline["duration"]
    args: list[str] = []
    inputs: dict[int, int] = {}

    def add_input(path: Path) -> int:
        args.extend(["-i", str(path)])
        return len(args) // 2 - 1

    chains: list[str] = []
    stems: list[str] = []
    voice_label = None
    if timeline.get("voiceover"):
        index = add_input(sources[timeline["voiceover"]["src"]])
        chains.append(f"[{index}:a]{STEREO},{VOICE_CHAIN},apad=whole_dur={duration:.3f},atrim=duration={duration:.3f}[voice]")
        voice_label = "[voice]"
    elif timeline["voice"]:
        for src in sorted({p["src"] for p in timeline["voice"]}):
            inputs[src] = add_input(sources[src])
        voice_chains, voice_label = _voice_graph(timeline["voice"], inputs, duration)
        chains += voice_chains

    spec = timeline.get("music")
    if music is not None and spec:
        index = add_input(music)
        fade_at = max(0.0, duration - 1.2)
        chains.append(
            f"[{index}:a]atrim=start={spec['offset']:.3f},asetpts=PTS-STARTPTS,{STEREO},volume={spec['gain_db']}dB,"
            f"apad=whole_dur={duration:.3f},atrim=duration={duration:.3f},afade=t=out:st={fade_at:.3f}:d=1.2[music]"
        )
        if voice_label and spec.get("duck"):
            chains.append(f"{voice_label}asplit=2[voicemix][voicekey]")
            chains.append("[music][voicekey]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=300[ducked]")
            stems += ["[voicemix]", "[ducked]"]
        else:
            stems += ([voice_label] if voice_label else []) + ["[music]"]
    elif voice_label:
        stems.append(voice_label)

    for n, cue in enumerate(c for c in timeline.get("sfx") or [] if c["sound"] in SFX):
        chains.append(_sfx_chain(cue, n))
        stems.append(f"[sfx{n}]")
    if not stems:
        return None
    # amix scales every input by 1/n; all stems run the whole reel, so volume=n undoes it exactly.
    chains.append(f"{''.join(stems)}amix=inputs={len(stems)}:duration=longest:dropout_transition=0,volume={len(stems)},"
                  f"atrim=duration={duration:.3f},{STEREO}[out]")
    return ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y", *args,
            "-filter_complex", ";".join(chains), "-map", "[out]", "-ar", str(SAMPLE_RATE), str(out)]


TEXT_STYLES = {
    # name: (font size as a share of width, vertical position as a share of height, colour, on a plate)
    "hook": (0.11, 0.22, "&H0000D7FF", True),
    "pop": (0.13, 0.40, "&H00FFFFFF", False),
    "line": (0.06, 0.70, "&H00FFFFFF", True),
}
POP_IN = "{\\fad(80,120)\\t(0,120,\\fscx118\\fscy118)\\t(120,220,\\fscx100\\fscy100)}"


def texts_ass(texts: list[dict[str, Any]], width: int, height: int, base: str | None) -> str:
    """The hook, pop-ups and script lines as ASS events, added to the caption file ``base`` if there is one."""
    family = "Anton"
    styles, events = [], []
    for name, (share, y, colour, plate) in TEXT_STYLES.items():
        size = round(width * share)
        margin_v = round(height * (1 - y) - size / 2)
        # BorderStyle 3 draws the outline as an opaque box behind the text.
        border, outline, shadow = (3, max(6, size // 6), 0) if plate else (1, max(3, size // 14), max(2, size // 24))
        outline_colour = "&H40000000" if plate else "&H00000000"
        styles.append(f"Style: Clip{name.title()},{family},{size},{colour},&H000000FF,{outline_colour},&H64000000,"
                      f"-1,0,0,0,100,100,0,0,{border},{outline},{shadow},2,{round(width * 0.08)},"
                      f"{round(width * 0.12)},{margin_v},1")
    for text in texts:
        value = text["text"].upper() if text["kind"] != "line" and (script_font(text["text"]) is None) else text["text"]
        font = script_font(value)
        override = f"{{\\fn{font[0]}}}" if font else ""
        effect = POP_IN if text["kind"] in ("pop", "hook") else "{\\fad(150,150)}"
        events.append(f"Dialogue: 2,{ass_time(text['at'])},{ass_time(text['at'] + text['dur'])},Clip{text['kind'].title()},"
                      f",0,0,0,,{effect}{override}{escape_ass(value)}")
    if base is None:
        base = "\n".join([
            "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {width}", f"PlayResY: {height}", "WrapStyle: 0",
            "ScaledBorderAndShadow: yes", "", "[V4+ Styles]",
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, "
            "Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, "
            "MarginL, MarginR, MarginV, Encoding", "", "[Events]",
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text", "",
        ])
    head, _, tail = base.partition("\n[Events]")
    return colourize(f"{head.rstrip()}\n" + "\n".join(styles) + "\n\n[Events]" + tail.rstrip("\n") + "\n" + "\n".join(events) + "\n")


def captions_ass(timeline: dict[str, Any]) -> str | None:
    width, height, duration = timeline["width"], timeline["height"], timeline["duration"]
    base = None
    if timeline["words"]:
        words = [{"text": w["word"], "start": w["start"], "end": w["end"]} for w in timeline["words"]]
        # No caption line may run across a text card, or it would show words the card interrupts.
        breaks = sorted({t for item in timeline["picture"] if item["kind"] == "card" for t in (item["at"], item["at"] + item["dur"])})
        base = AssGenerator().build_ass(words, 0.0, duration, style_id=timeline.get("caption_style") or DEFAULT_STYLE,
                                        width=width, height=height, segment_breaks=breaks)
    if not timeline["texts"]:
        return base
    return texts_ass(timeline["texts"], width, height, base)


async def render(timeline: dict[str, Any], sources: dict[int, Path], music: Path | None, watermark: bool,
                 work: Path) -> Path:
    """The finished reel at ``work/reel.mp4``."""
    if not timeline["picture"] or timeline["duration"] <= 0:
        raise ValueError("The timeline is empty")
    parts = await render_segments(timeline, sources, work)
    raw_mix, mix = work / "mix_raw.wav", work / "mix.wav"
    command = audio_mix_cmd(timeline, sources, music, raw_mix)
    if command:
        await run(command)
        await master(raw_mix, mix)
    joined = work / "joined.mp4"
    await reel_render.join(parts, mix if command else None, joined)
    ass_text = captions_ass(timeline)
    ass_file = None
    if ass_text:
        ass_file = work / "captions.ass"
        ass_file.write_text(ass_text, encoding="utf-8")
    final = await reel_render.finish(joined, ass_file, watermark, work / "reel.mp4", preset="veryfast")
    await check(final, timeline["duration"] + (added_seconds() if watermark else 0.0))
    return final


async def master(src: Path, out: Path) -> None:
    """Two-pass loudness normalisation: measure, then correct linearly so dynamics are kept."""
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-hide_banner", "-nostdin", "-i", str(src), "-af", f"loudnorm={LOUDNESS_TARGET}:print_format=json",
        "-f", "null", "-", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    text = stderr.decode("utf-8", "ignore")
    measured = json.loads(text[text.rfind("{"):text.rfind("}") + 1]) if "input_i" in text else {}
    second = ""
    if measured and measured.get("input_i") not in ("-inf", None):
        second = (f":measured_I={measured['input_i']}:measured_TP={measured['input_tp']}:measured_LRA={measured['input_lra']}"
                  f":measured_thresh={measured['input_thresh']}:offset={measured['target_offset']}:linear=true")
    await run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y", "-i", str(src),
               "-af", f"loudnorm={LOUDNESS_TARGET}{second},{STEREO}", "-ar", str(SAMPLE_RATE), str(out)])


async def check(path: Path, duration: float) -> None:
    """The QA gate: the file plays for the planned length and has picture and sound."""
    info = await probe_media(str(path))
    if not (info.has_video and info.has_audio) or abs(info.duration - duration) > 0.75:
        raise RuntimeError(f"The render came out wrong ({info.duration:.1f}s for a {duration:.1f}s timeline)")
