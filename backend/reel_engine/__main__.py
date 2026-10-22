"""Run the reel engine on local files.

    cd backend && venv/bin/python -m reel_engine clip1.mp4 [clip2.mp4 ...] --out out/reel.mp4 [--brief "..."] [--target 45]

The Edit Plan is written next to the reel as ``<name>.plan.json``; made assets go to a local registry
(``--store``, default ``~/.clipnera/reel_assets``) that later runs search before making anything again.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from reel_engine.assets import LocalAssetStore
from reel_engine.pipeline import run


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--brief", default="")
    parser.add_argument("--target", type=float, default=0.0)
    parser.add_argument("--passes", type=int, default=2)
    parser.add_argument("--work", type=Path)
    parser.add_argument("--store", type=Path, default=Path.home() / ".clipnera" / "reel_assets")
    args = parser.parse_args()
    out = args.out.resolve()
    work = (args.work or out.parent / f"{out.stem}_work").resolve()

    async def report(plan) -> None:
        last = plan.progress[-1]
        print(f"[{last.at:6.1f}s] {last.stage:9} {last.note}", flush=True)

    plan = asyncio.run(run([p.resolve() for p in args.inputs], work, out, LocalAssetStore(args.store), owner="local",
                           brief=args.brief, target_seconds=args.target, passes=args.passes, on_progress=report))
    out.with_suffix(".plan.json").write_text(json.dumps(plan.model_dump(), indent=1, ensure_ascii=False))
    print(f"\nReel: {out} ({plan.duration:.1f} s)")
    print(f"Path {plan.brief.path} · recipe {plan.brief.recipe} · audio {plan.audio.kind} · model calls {plan.ai_calls}")
    print("Review:", ", ".join(f"{s.layer} {s.score}" for s in plan.review.scores), f"→ {plan.review.overall}/10")
    for fix in plan.review.fixes:
        print("  fix:", fix)
    if plan.assets_made:
        print("Made and stored:", ", ".join(f"{a.kind}:{a.id[:8]}" for a in plan.assets_made))


if __name__ == "__main__":
    main()
