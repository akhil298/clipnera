"""The on-screen bridge line, written as a one-event ASS file.

Rendered with libass over the bridge segment only, using the display faces
bundled in ``static/fonts`` so it looks the same on every host.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

BRIDGE_ASS_NAME = "bridge.ass"


@dataclass(frozen=True)
class _TextStyle:
    font: str
    size: int  # on the 1080-wide scale captions use
    primary: str  # ASS &HAABBGGRR
    outline: str
    back: str
    border_style: int  # 1 outline + shadow, 3 opaque box
    outline_width: int
    shadow: int
    uppercase: bool = False
    # Override tags applied to the line; "{pop}" expands to the entry animation.
    tags: str = "{pop}"


_POP = r"\fscx55\fscy55\t(0,160,\fscx110\fscy110)\t(160,260,\fscx100\fscy100)"

TEXT_STYLE_DEFS: dict[str, _TextStyle] = {
    "bold_white": _TextStyle("Archivo Black", 76, "&H00FFFFFF", "&H00000000", "&H80000000", 1, 6, 3),
    "yellow_box": _TextStyle("Archivo Black", 70, "&H00000000", "&H0000E0FF", "&H0000E0FF", 3, 18, 0),
    "red_banner": _TextStyle("Anton", 84, "&H00FFFFFF", "&H002D2DE1", "&H002D2DE1", 3, 20, 0, uppercase=True),
    "neon": _TextStyle("Bebas Neue", 120, "&H00FFFF7A", "&H00FF40C0", "&H00000000", 1, 4, 0, tags=r"{pop}\blur6"),
    "impact_caps": _TextStyle("Anton", 124, "&H00FFFFFF", "&H00000000", "&H90000000", 1, 6, 4, uppercase=True),
    "marker": _TextStyle("Permanent Marker", 92, "&H0000E0FF", "&H00000000", "&H80000000", 1, 5, 3, tags=r"{pop}\frz-3"),
    "comic": _TextStyle("Bangers", 116, "&H00FFFFFF", "&H00000000", "&H00000000", 1, 7, 5, tags=r"{pop}\frz-4"),
    "cinematic": _TextStyle("DM Serif Display", 86, "&H00FFFFFF", "&H00000000", "&H60000000", 1, 0, 2, tags=r"\fad(250,200)"),
}


def _ass_time(seconds: float) -> str:
    centis = max(0, round(seconds * 100))
    hours, rest = divmod(centis, 360000)
    minutes, rest = divmod(rest, 6000)
    secs, cs = divmod(rest, 100)
    return f"{hours}:{minutes:02d}:{secs:02d}.{cs:02d}"


def _escape(text: str) -> str:
    return " ".join(text.replace("\\", "").replace("{", "").replace("}", "").split())


def bridge_ass(text: str, style_id: str, width: int, height: int, duration: float) -> str:
    """ASS document showing ``text`` centred for ``duration`` seconds."""
    style = TEXT_STYLE_DEFS.get(style_id, TEXT_STYLE_DEFS["bold_white"])
    scale = width / 1080.0
    size = max(12, round(style.size * scale))
    margin = round(width * 0.08)
    line = _escape(text.upper() if style.uppercase else text)
    tags = style.tags.replace("{pop}", _POP)
    return "\n".join([
        "[Script Info]",
        "ScriptType: v4.00+",
        f"PlayResX: {width}",
        f"PlayResY: {height}",
        "WrapStyle: 0",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
        "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: Bridge,{style.font},{size},{style.primary},{style.primary},{style.outline},{style.back},"
        f"0,0,0,0,100,100,0,0,{style.border_style},{round(style.outline_width * scale)},"
        f"{round(style.shadow * scale)},5,{margin},{margin},0,1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
        f"Dialogue: 0,{_ass_time(0)},{_ass_time(duration)},Bridge,,0,0,0,,"
        f"{{\\an5\\pos({width // 2},{round(height * 0.5)}){tags}}}{line}",
        "",
    ])


def write_bridge_ass(text: str, style_id: str, width: int, height: int, duration: float, work_dir: str) -> str:
    """Write the bridge line into ``work_dir`` and return its bare filename."""
    with open(os.path.join(work_dir, BRIDGE_ASS_NAME), "w", encoding="utf-8") as handle:
        handle.write(bridge_ass(text, style_id, width, height, duration))
    return BRIDGE_ASS_NAME
