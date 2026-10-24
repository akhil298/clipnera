"""Render one explainer scene of every shot and world, to see each before it reaches a reel.

    cd backend && venv/bin/python scripts/scenes_gallery.py out_dir [--only inside,flow]

Each sample goes through the reel's own steps (actors matched to built forms or kit objects without a model call,
the renderer, the cutaway encode). Writes out_dir/<shot>_<world>.mp4 and out_dir/gallery.jpg (four frames of
each). No model calls.
"""

from __future__ import annotations

import argparse
import asyncio
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from reel_engine import icons  # noqa: E402
from reel_engine.render import _draw  # noqa: E402
from reel_engine.scenes import SCENE_FRAME_SECONDS, DActor, DScene, form_of, spec  # noqa: E402

SAMPLES = [
    ("inside", "sky", [("cloud", "5 lakh kg")], {}),
    ("wrong", "sky", [("water", "One big blob"), ("droplets", "Tiny droplets")], {}),
    ("many", "macro", [("water droplets", "Water droplets")], {"number": "Billions"}),
    ("compare", "sky", [("raindrop", "Raindrop"), ("droplet", "Droplet")], {"ratio": 0.25}),
    ("force", "sky", [("droplets", "Droplets"), ("warm air", "Heat")], {"direction": "up"}),
    ("transform", "macro", [("droplet", ""), ("raindrop", "Raindrop")], {}),
    ("flow", "studio", [("money", "Salary"), ("bank", "Savings"), ("chart increasing", "Investing")], {}),
    ("cycle", "sky", [("sun", "Heat"), ("cloud", "Clouds"), ("raindrop", "Rain"), ("water", "Sea")], {}),
    ("scale", "studio", [("coins", "")], {"number": "₹5,00,000"}),
    ("inside", "body", [("lungs", "Lungs"), ("blood cell", "Oxygen")], {}),
    ("reveal", "space", [("atom", "Atom")], {}),
    ("reveal", "room", [("light bulb", "Dust particles")], {}),
    ("reveal", "ocean", [("fish", "Fish")], {}),
    ("reveal", "city", [("house", "Rent"), ("money with wings", "Salary")], {}),
    ("location", "space", [], {"place": "Mumbai", "lat": 19.07, "lon": 72.88}),
]


def kit_picture(show: str) -> str | None:
    """The best word match among the kit's 3D objects (the reel asks a model to confirm it; the gallery does not)."""
    from beats import kit

    found = icons.candidates(show, 1, kinds=("object3d",))
    return str(kit.path_of(found[0])) if found else None


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("out", type=Path)
    parser.add_argument("--only", default="")
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    only = {s for s in args.only.split(",") if s}
    specs = []
    for shot, world, actors, extra in SAMPLES:
        if only and shot not in only:
            continue
        scene = DScene(shot=shot, world=world, w0=0, w1=0, actors=[DActor(show=s, label=label) for s, label in actors],
                       number=extra.get("number", ""), ratio=extra.get("ratio", 0.0), direction=extra.get("direction", "none"),
                       place=extra.get("place", ""), lat=extra.get("lat", 0.0), lon=extra.get("lon", 0.0), why="")
        drawn = []
        for a in scene.actors:
            form = form_of(a.show)
            entry = None if form else kit_picture(a.show)
            if form or entry:
                drawn.append({**({"form": form} if form else {"img": Path(entry).resolve().as_uri()}), "label": a.label})
        specs.append(spec(f"{shot}_{world}", 3.6 if shot in ("flow", "cycle") else 3.0, scene, drawn, "#ffb020"))
    rendered = await _draw(specs, out, SCENE_FRAME_SECONDS)
    sheets = []
    for s in specs:
        movie = (rendered.get(s["id"]) or {}).get("file")
        if not movie:
            print(f"{s['id']}: failed {(rendered.get(s['id']) or {}).get('error')}")
            continue
        mp4 = out / f"{s['id']}.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", movie, "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", str(mp4)], check=True)
        sheet = out / f"{s['id']}.jpg"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(mp4), "-vf", f"fps={4 / s['dur']:.3f},scale=216:384,tile=4x1",
                        "-frames:v", "1", str(sheet)], check=True)
        sheets.append(sheet)
        print(f"{s['id']}: {mp4}")
    if sheets:
        inputs = [a for p in sheets for a in ("-i", str(p))]
        subprocess.run(["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", f"vstack={len(sheets)}" if len(sheets) > 1 else "null",
                        str(out / "gallery.jpg")], check=True)
        print(f"Gallery: {out / 'gallery.jpg'}")


if __name__ == "__main__":
    asyncio.run(main())
