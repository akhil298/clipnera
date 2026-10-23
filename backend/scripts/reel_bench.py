"""Run the reel engine on a matrix of raw-footage cases and report how each scored.

    cd backend && venv/bin/python scripts/reel_bench.py cases.json out_dir [--parallel 2] [--only name,name]

``cases.json``: [{"name": "travel", "inputs": ["/path/a.mp4", ...], "brief": "...", "target": 30}, ...]
Each case writes ``out_dir/<name>/reel.mp4``, ``reel.plan.json`` and ``sheet.jpg``; ``out_dir/results.json``
and ``out_dir/results.md`` hold the table (review per layer, length, recipe, style, music, inserts, time).
Model calls cost money: every case is a full engine run.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from reel_engine.assets import LocalAssetStore  # noqa: E402
from reel_engine.pipeline import run  # noqa: E402
from reel_engine.plan import LAYERS  # noqa: E402


def sheet(video: Path, out: Path, frames: int = 14) -> None:
    seconds = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(video)],
                                   capture_output=True, text=True).stdout or 1)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(video), "-vf",
                    f"fps={frames / seconds:.4f},scale=200:-1,tile={(frames + 1) // 2}x2", "-frames:v", "1", str(out)], check=False)


async def one(case: dict, out: Path, store: LocalAssetStore) -> dict:
    folder = out / case["name"]
    folder.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    try:
        plan = await run([Path(p) for p in case["inputs"]], folder / "work", folder / "reel.mp4", store, owner="bench",
                         brief=case.get("brief", ""), target_seconds=float(case.get("target", 0)))
    except Exception as exc:
        return {"name": case["name"], "error": f"{type(exc).__name__}: {exc}"[:300], "seconds": round(time.monotonic() - started)}
    (folder / "reel.plan.json").write_text(json.dumps(plan.model_dump(), indent=1, ensure_ascii=False))
    sheet(folder / "reel.mp4", folder / "sheet.jpg")
    scores = {s.layer: s.score for s in plan.review.scores}
    return {"name": case["name"], "seconds": round(time.monotonic() - started), "length": round(plan.duration, 1),
            "path": plan.brief.path, "audio": plan.audio.kind, "recipe": plan.brief.recipe, "style": plan.brief.text_style,
            "music": plan.music.title if plan.music else plan.brief.music, "shots": len(plan.video), "graphics": len(plan.graphics),
            "captions": len(plan.captions), "inserts": len(plan.inserts) + sum(1 for g in plan.graphics if g.kind == "photocard"),
            "made": len(plan.assets_made), "ai_calls": plan.ai_calls, "overall": plan.review.overall, "scores": scores,
            "fixes": plan.review.fixes}


def table(results: list[dict]) -> str:
    head = "| case | overall | " + " | ".join(LAYERS) + " | length | recipe | style | music | inserts | time |"
    rows = [head, "|" + "---|" * (len(LAYERS) + 8)]
    for r in results:
        if "error" in r:
            rows.append(f"| {r['name']} | error | " + " | ".join("" for _ in LAYERS) + f" | | | | | | {r['seconds']}s |")
            continue
        rows.append(f"| {r['name']} | **{r['overall']}** | " + " | ".join(str(r["scores"].get(l, "")) for l in LAYERS)
                    + f" | {r['length']}s | {r['recipe']} | {r['style']} | {r['music']} | {r['inserts']} | {r['seconds']}s |")
    done = [r for r in results if "error" not in r]
    if done:
        rows.append(f"\nMean overall {sum(r['overall'] for r in done) / len(done):.1f} over {len(done)} case(s).")
    return "\n".join(rows)


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("cases", type=Path)
    parser.add_argument("out", type=Path)
    parser.add_argument("--parallel", type=int, default=2)
    parser.add_argument("--only", default="")
    args = parser.parse_args()
    cases = json.loads(args.cases.read_text())
    if args.only:
        wanted = set(args.only.split(","))
        cases = [c for c in cases if c["name"] in wanted]
    args.out.mkdir(parents=True, exist_ok=True)
    store = LocalAssetStore(args.out / "asset_store")
    slots = asyncio.Semaphore(max(1, args.parallel))
    results: list[dict] = []

    async def guarded(case: dict) -> None:
        async with slots:
            print(f"start {case['name']}", flush=True)
            result = await one(case, args.out, store)
            results.append(result)
            print(f"done  {case['name']}: {result.get('overall', result.get('error'))} in {result['seconds']}s", flush=True)
            (args.out / "results.json").write_text(json.dumps(results, indent=1, ensure_ascii=False))
            (args.out / "results.md").write_text(table(sorted(results, key=lambda r: r["name"])))

    await asyncio.gather(*(guarded(c) for c in cases))
    print(table(sorted(results, key=lambda r: r["name"])))


if __name__ == "__main__":
    asyncio.run(main())
