"""Render every catalog effect on a few seconds of real footage, to see each look before it reaches a reel.

    cd backend && venv/bin/python scripts/effects_gallery.py talking_head.mp4 out_dir [--at 60] [--only orbit,doodle]

The footage is framed 9:16 around its centre; each effect runs through the same steps a reel uses (faces, picture
effects, the speaker's matte, the renderer, compose). Writes out_dir/<effect>.mp4 and out_dir/gallery.jpg (one frame
of each, mid-effect). No model calls.
"""

from __future__ import annotations

import argparse
import asyncio
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from reel_engine import effects  # noqa: E402
from reel_engine.media import FPS, H, W, run  # noqa: E402
from reel_engine.plan import EditPlan  # noqa: E402
from reel_engine.render import compose, render_graphics, resolve_behind  # noqa: E402

SECONDS = 6.0
START, END = 1.0, 4.4
SAMPLES = {
    "doodle": dict(choice="crown", target="face_top"),
    "headline_wall": dict(texts=["Everyone is talking about this", "The internet can't stop", "It went viral overnight", "Experts are stunned"]),
    "orbit": dict(texts=["Design", "Code", "Marketing", "Sales", "Hiring"]),
    "glass_type": dict(texts=["Values never change"]),
    "paper_cut": dict(texts=["Step one:", "write it down"]),
    "phone_mockup": dict(choice="chat", texts=["Are you coming tonight?"]),
    "cover_story": dict(texts=["MINDSET", "From zero to CEO", "The habit that changed everything", "Inside his routine"]),
    "ui_world": dict(texts=["New follower: @priya", "You earned ₹12,400", "3 new messages", "Your post hit 1M views"]),
    "framebreak": dict(texts=["I quit"]),
    "pullback": dict(target="face"),
    "zoom_through": dict(),
    "vertigo": dict(),
    "green_screen": dict(choice="space"),
    "couch_wall": dict(texts=["No excuses"]),
}


def frame_picture(src: Path, at: float, out: Path) -> None:
    run(["ffmpeg", "-v", "error", "-y", "-ss", f"{at:.2f}", "-t", f"{SECONDS:.2f}", "-i", str(src), "-an",
         "-vf", f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS}",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "17", "-pix_fmt", "yuv420p", str(out)])


async def one(name: str, base: Path, out_dir: Path, silence: Path) -> Path | None:
    work = out_dir / f"work_{name}"
    work.mkdir(parents=True, exist_ok=True)
    plan = EditPlan(duration=SECONDS)
    start, end = (2.7, 3.3) if name == "zoom_through" else (START, END)
    plan.graphics = effects.make_items("g", name, start, end, **{"texts": [], **SAMPLES[name]})
    effects.place_on_faces(plan, base)
    picture = await effects.apply_picture(plan, base, work)
    await resolve_behind(plan, picture, work)
    if not plan.graphics:
        print(f"{name}: dropped (no face or no matte)")
        return None
    placed = await render_graphics(plan, work)
    out = out_dir / f"{name}.mp4"
    await compose(plan, picture, placed, silence, work, out)
    print(f"{name}: {out}")
    return out


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("footage", type=Path)
    parser.add_argument("out", type=Path)
    parser.add_argument("--at", type=float, default=60.0)
    parser.add_argument("--only", default="")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    base, silence = args.out / "base.mp4", args.out / "silence.wav"
    frame_picture(args.footage, args.at, base)
    run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"anullsrc=r=48000:cl=stereo", "-t", f"{SECONDS}", str(silence)])
    names = [n for n in SAMPLES if not args.only or n in args.only.split(",")]
    made = []
    for name in names:
        try:
            made.append((name, await one(name, base, args.out, silence)))
        except Exception as exc:
            print(f"{name}: FAILED {type(exc).__name__}: {exc}"[:400])
    frames = []
    for name, path in made:
        if path:
            shot = args.out / f"{name}.jpg"
            mid = 3.0 if name == "zoom_through" else 2.6
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{mid}", "-i", str(path), "-frames:v", "1", "-vf",
                            f"scale=270:480,drawtext=fontfile=/System/Library/Fonts/Helvetica.ttc:text={name}:fontsize=20:"
                            "fontcolor=white:box=1:boxcolor=black@0.6:x=8:y=8", str(shot)])
            frames.append(shot)
    if frames:
        cols = min(5, len(frames))
        inputs = sum((["-i", str(f)] for f in frames), [])
        pad = (cols - len(frames) % cols) % cols
        layout = "|".join(f"{(k % cols) * 270}_{(k // cols) * 480}" for k in range(len(frames)))
        subprocess.run(["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex",
                        f"xstack=inputs={len(frames)}:layout={layout}:fill=black" if len(frames) > 1 else "null",
                        str(args.out / "gallery.jpg")])
        print(f"gallery: {args.out / 'gallery.jpg'} ({len(frames)} effects{', ' + str(pad) + ' empty' if pad else ''})")


if __name__ == "__main__":
    asyncio.run(main())
