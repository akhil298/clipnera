"""Layers drawn over the joined picture, before captions: B-roll, images, flashes and graphics.

A layer is one of:
- ``video``: footage (``src``, ``in``, ``speed``, framing as on the main track), graded with the look;
- ``image``: a still (``src``) filling the frame, graded with the look;
- ``solid``: a flat ``colour``, such as a flash;
- ``graphic``: a packed-alpha animation from the shelf (``path``: colour left, matte right).

Every layer has ``at`` and ``dur`` (seconds), ``opacity`` and ``fade_in``/``fade_out`` (seconds).
A ``scale`` under 1 makes it picture-in-picture, centred at ``x``/``y`` (shares of the frame);
otherwise it fills the frame. Later layers draw over earlier ones.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from edit_engine.framing import framing_filters, timing_filters
from edit_engine.looks import look_filter


def _even(value: float) -> int:
    return max(2, round(value / 2) * 2)


def _input(layer: dict[str, Any], sources: dict[int, Path], size: tuple[int, int]) -> list[str]:
    kind, dur = layer["kind"], f"{layer['dur']:.3f}"
    if kind == "video":
        return ["-ss", f"{layer.get('in', 0.0):.3f}", "-t", f"{layer['dur'] * (layer.get('speed') or 1.0):.3f}",
                "-i", str(sources[layer["src"]])]
    if kind == "image":
        return ["-loop", "1", "-framerate", "30", "-t", dur, "-i", str(sources[layer["src"]])]
    if kind == "solid":
        return ["-f", "lavfi", "-t", dur, "-i", f"color=c={layer['colour']}:s={size[0]}x{size[1]}:r=30"]
    return ["-i", str(layer["path"])]


def _picture(layer: dict[str, Any], index: int, look: str, size: tuple[int, int], label: str) -> list[str]:
    """Chains turning input ``index`` into the layer, with alpha, placed in time, as ``label``."""
    width, height = size
    cover = f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height}"
    kind = layer["kind"]
    chains: list[str] = []
    if kind == "graphic":
        chains.append(f"[{index}:v]split[c{index}][m{index}]")
        chains.append(f"[m{index}]crop=iw/2:ih:iw/2:0,format=gray[a{index}]")
        chains.append(f"[c{index}]crop=iw/2:ih:0:0[k{index}]")
        source, steps = f"[k{index}][a{index}]alphamerge,", ["fps=30", cover]
    elif kind == "video":
        source, steps = f"[{index}:v]", [*timing_filters(layer.get("speed") or 1.0), *framing_filters(layer, size)]
    elif kind == "image":
        source, steps = f"[{index}:v]", [cover]
    else:
        source, steps = f"[{index}:v]", []
    if kind in ("video", "image") and look_filter(look):
        steps.append(look_filter(look))
    steps += ["setsar=1", "format=yuva420p"]
    scale = layer.get("scale") or 1.0
    if scale < 1:
        steps.append(f"scale={_even(width * scale)}:{_even(height * scale)}")
    if (opacity := layer.get("opacity", 1.0)) < 1:
        steps.append(f"colorchannelmixer=aa={opacity:.3f}")
    if fade := layer.get("fade_in"):
        steps.append(f"fade=t=in:st=0:d={fade:.3f}:alpha=1")
    if fade := layer.get("fade_out"):
        steps.append(f"fade=t=out:st={max(0.0, layer['dur'] - fade):.3f}:d={fade:.3f}:alpha=1")
    steps.append(f"setpts=PTS-STARTPTS+{layer['at']:.3f}/TB")
    chains.append(f"{source}{','.join(steps)}{label}")
    return chains


def compose_cmd(video: Path, layers: list[dict[str, Any]], sources: dict[int, Path], look: str,
                size: tuple[int, int], encode: list[str], out: Path) -> list[str]:
    """One FFmpeg command drawing ``layers`` over ``video`` (its sound copied) into ``out``."""
    args, chains, base = ["-i", str(video)], [], "[0:v]"
    for n, layer in enumerate(layers, start=1):
        args += _input(layer, sources, size)
        chains += _picture(layer, n, look, size, f"[l{n}]")
        small = (layer.get("scale") or 1.0) < 1
        x = f"{size[0] * layer.get('x', 0.5):.1f}-w/2" if small else "0"
        y = f"{size[1] * layer.get('y', 0.5):.1f}-h/2" if small else "0"
        end = layer["at"] + layer["dur"]
        chains.append(f"{base}[l{n}]overlay=x={x}:y={y}:eof_action=pass:enable='between(t,{layer['at']:.3f},{end:.3f})'[b{n}]")
        base = f"[b{n}]"
    chains.append(f"{base}format=yuv420p[v]")
    return ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y", *args,
            "-filter_complex", ";".join(chains), "-map", "[v]", "-map", "0:a?", *encode, "-c:a", "copy", str(out)]
