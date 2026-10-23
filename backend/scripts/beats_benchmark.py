"""Benchmark the graphic beats against the human Before/After edits in before_after_reels/.

Six raw clips were each edited by several editors (before_after_reels/ANALYSIS.md §5). For each:

    plan    plan beats from the clip's words (measure/measurements.json) -> bench/<id>.plan.json
    render  finish a raw video with a plan (--video raw.mp4) and stack it beside the human edit -> bench/<id>.side.mp4
    judge   the beat planner's model compares our plan with the human edits' frames and scores it -> bench/<id>.judge.json

    cd backend && venv/bin/python scripts/beats_benchmark.py plan
    venv/bin/python scripts/beats_benchmark.py render --id DRZkc5yjQ9v --video ~/raw/rupee_clip.mp4
    venv/bin/python scripts/beats_benchmark.py judge
    venv/bin/python scripts/beats_benchmark.py report

``plan`` and ``judge`` call the model (Pro routing, step beat_planning): they cost money.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from beats.plan import dump_plan, load_plan  # noqa: E402
from beats.planner import plan_beats  # noqa: E402
from broll.planner import ClipWords  # noqa: E402
from clients.ai import get_text_client  # noqa: E402

REELS = Path(__file__).resolve().parents[2] / "before_after_reels"
BENCH = REELS / "bench"
# Raw clip -> the human edits of it (first id's words are planned from).
SHARED: dict[str, list[str]] = {
    "rupee_27000": ["DRZkc5yjQ9v", "DXV50FxAPKh"],
    "youtube_titles": ["DaSrSnMKstL", "Db8QKJ_SJVD"],
    "iman_gadzhi_style": ["DbBnxQ_Rrt1", "Dbf3GijNRV5", "DeEdW5wPt6t"],
    "manoj_mistakes": ["DbYJygqB2F6", "DcS1V8LM1sx"],
    "intelligent_apparel": ["DZgzUHxSLBG", "DdUFMn_NPWG"],
    "agency_hiring_test": ["Dcs-5D_SVqB"],
}
CATEGORIES = {"manoj_mistakes": "podcast_interview", "iman_gadzhi_style": "educational"}
FRAMES_PER_REEL = 12

JUDGE = """You compare an AI editor's planned graphic beats with how human editors cut the same clip.

You see frames (one per second) of each human edit, then the AI's beats as JSON (kind, words shown, start-end seconds).
The human edits show the raw speaker small and their edit large; judge only the edit. Score 0-10:
- coverage: of the moments the humans put a graphic on, how many the AI also covers with a fitting graphic;
- fit: whether each AI beat shows the right kind of thing for its words (number, list, logo, object, image...);
- pacing: graphics about every 2-3 seconds, none crowded, none missing on long stretches;
- variety: a good mix of kinds, not keyword after keyword;
- taste: would a premium editor make these choices.
List up to 5 human beats the AI missed and up to 3 AI beats a premium editor would cut. Return JSON only."""


class _Score(BaseModel):
    model_config = ConfigDict(extra="forbid")

    coverage: int
    fit: int
    pacing: int
    variety: int
    taste: int
    missed: list[str]
    cut: list[str]


@dataclass
class BenchClip:
    """The bare clip fields the finish pass reads, for a raw file outside the database."""

    id: str
    start_time: float
    end_time: float
    transcript: str
    analysis_json: str
    edit_spans: str | None = None
    output_formats: str = "{}"
    hook_start: float | None = None
    hook_end: float | None = None


def words_of(reel: str) -> list[dict[str, Any]]:
    path = REELS / reel / "measure" / "measurements.json"
    if not path.is_file():
        return []
    speech = json.loads(path.read_text(encoding="utf-8")).get("speech") or {}
    return [{"word": w["word"], "start": float(w["start_s"]), "end": float(w["end_s"])} for w in speech.get("words") or []]


async def cmd_plan(_: argparse.Namespace) -> None:
    BENCH.mkdir(parents=True, exist_ok=True)
    client = get_text_client(is_pro=True, step="beat_planning")
    for name, reels in SHARED.items():
        words = words_of(reels[0])
        if not words:
            print(f"{name}: no words for {reels[0]} (no measurements); skipped")
            continue
        clip = ClipWords(words=words, spans=[(words[0]["start"], words[-1]["end"] + 0.5)])
        [plan] = await plan_beats([clip], client, [CATEGORIES.get(name, "educational")])
        (BENCH / f"{name}.plan.json").write_text(json.dumps(dump_plan(plan), ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"{name}: {len(plan.beats)} beats, theme {plan.theme}: " + ", ".join(f"{b.kind}@{b.start:.1f}" for b in plan.beats))


async def cmd_render(args: argparse.Namespace) -> None:
    from beats.compose import finish

    name = next((n for n, reels in SHARED.items() if args.id in reels or args.id == n), None)
    if name is None:
        sys.exit(f"{args.id} is not a benchmark clip")
    plan = load_plan((BENCH / f"{name}.plan.json").read_text(encoding="utf-8"))
    if plan is None:
        sys.exit("Run `plan` first.")
    words = words_of(SHARED[name][0])
    clip = BenchClip(id=name, start_time=0.0, end_time=words[-1]["end"] + 0.5,
                     transcript=json.dumps([{"words": words}]), analysis_json=json.dumps({"beats": dump_plan(plan)}))
    with tempfile.TemporaryDirectory() as tmp:
        ours = await finish(str(Path(args.video).expanduser()), clip, None, plan, "9:16", Path(tmp))
        human = REELS / SHARED[name][0] / "reel.mp4"
        out = BENCH / f"{name}.side.mp4"
        subprocess.run([
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", ours, "-i", str(human),
            "-filter_complex", "[0:v]scale=-2:1280[a];[1:v]scale=-2:1280[b];[a][b]hstack=inputs=2[v]",
            "-map", "[v]", "-map", "0:a?", "-c:v", "libx264", "-crf", "20", "-shortest", str(out),
        ], check=True)
    print(f"side by side: {out}")


def frames(reel: str) -> list[bytes]:
    video = REELS / reel / "reel.mp4"
    duration = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(video)],
                                    capture_output=True, text=True).stdout.strip() or 10)
    shots = []
    for k in range(FRAMES_PER_REEL):
        t = duration * (k + 0.5) / FRAMES_PER_REEL
        shots.append(subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.2f}", "-i", str(video), "-frames:v", "1",
                                     "-vf", "scale=360:-2", "-f", "image2pipe", "-vcodec", "mjpeg", "-"], capture_output=True).stdout)
    return [shot for shot in shots if shot]


async def cmd_judge(_: argparse.Namespace) -> None:
    client = get_text_client(is_pro=True, step="beat_planning")
    for name, reels in SHARED.items():
        path = BENCH / f"{name}.plan.json"
        plan = load_plan(path.read_text(encoding="utf-8")) if path.is_file() else None
        if plan is None:
            continue
        beats = [{"kind": b.kind, "shows": b.data, "start": b.start, "end": b.end} for b in plan.beats]
        jpegs = [shot for reel in reels for shot in frames(reel)]
        message = client.image_message(f"Human edits: {len(reels)} ({FRAMES_PER_REEL} frames each).\n\nAI beats:\n"
                                       f"{json.dumps(beats, ensure_ascii=False)}\n\nScore it. JSON only.", jpegs)
        score = await client.chat_json([{"role": "system", "content": JUDGE}, message], _Score, max_tokens=1500)
        (BENCH / f"{name}.judge.json").write_text(score.model_dump_json(indent=1), encoding="utf-8")
        print(f"{name}: {score.model_dump(exclude={'missed', 'cut'})}")


async def cmd_report(_: argparse.Namespace) -> None:
    rows = []
    for name in SHARED:
        path = BENCH / f"{name}.judge.json"
        if path.is_file():
            score = json.loads(path.read_text(encoding="utf-8"))
            rows.append((name, *(score[k] for k in ("coverage", "fit", "pacing", "variety", "taste"))))
    print(f"{'clip':<22} cov fit pace var taste")
    for row in rows:
        print(f"{row[0]:<22} {row[1]:>3} {row[2]:>3} {row[3]:>4} {row[4]:>3} {row[5]:>5}")
    if rows:
        print(f"{'mean':<22} " + " ".join(f"{sum(r[i] for r in rows) / len(rows):>4.1f}" for i in range(1, 6)))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("plan")
    render = sub.add_parser("render")
    render.add_argument("--id", required=True)
    render.add_argument("--video", required=True)
    sub.add_parser("judge")
    sub.add_parser("report")
    args = parser.parse_args()
    asyncio.run({"plan": cmd_plan, "render": cmd_render, "judge": cmd_judge, "report": cmd_report}[args.cmd](args))


if __name__ == "__main__":
    main()
