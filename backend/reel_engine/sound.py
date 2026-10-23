"""Sound: the voice, the music and every effect, mixed for phone speakers.

- Voice: the kept words, cut from the source with 10 ms fades at every join; separated from any music
  under it first (voice_song), then cleaned (rumble cut, noise reduced, levelled).
- Music: a bed from the library ducked under the voice, or a score composed to the cuts (picture reels).
- Effects: a sound on every graphic (pop, whoosh, ding, tick), whooshes on framing changes, the foley the
  director asked for (sizzle, chop, pour, sparkle), all through the asset loop so made sounds are kept.
- Mix: voice on top, music sidechained under it, effects on their frames, loudness -14 LUFS, peak -1 dB.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from core.logging_config import get_logger
from reel_engine.assets import Scout
from reel_engine.listen import SEPARATION_RATE, separate
from reel_engine.media import run
from reel_engine.music import Structure
from reel_engine.plan import AssetRef, AudioItem, EditPlan

log = get_logger(__name__)

# Only motivated accents: an entrance, a reveal, a count landing. Captions, small labels and framing stay quiet.
GRAPHIC_SOUNDS = {"photocard": ["whoosh_short"], "chapter": ["whoosh"], "two": [], "tag": ["pop"], "keyword": ["boom"],
                  "statement": ["whoosh"], "list": ["whoosh_short"], "flow": ["whoosh_short"], "count_up": ["ding"], "chart": ["riser"],
                  "name": [], "cta": ["pop"], "wash": [], "progress": [], "flicker": []}
MIN_SPACING = 2.5


def structure(plan: EditPlan) -> Structure:
    v = plan.video
    hook_end = max((i.out1 for i in v if i.role == "hook"), default=0.0)
    montage = [i for i in v if i.role == "montage"]
    sections = sorted({round(i.out0, 3) for i in v if i.section >= 0})
    payoff = next((i.out0 for i in v if i.role == "payoff"), None)
    cta = next((i.out0 for i in v if i.role == "cta"), None)
    return Structure(duration=plan.duration, hook_end=hook_end,
                     roll=(montage[0].out0, montage[-1].out1) if montage else None, sections=sections, payoff=payoff, cta=cta,
                     money=[(i.out0, i.out1) for i in v if i.money and i.speed < 1.0],
                     foley=[(i.out0, i.out1, i.sound) for i in v if i.sound in ("sizzle", "chop", "pour", "sparkle")],
                     mood=plan.brief.mood if plan.brief else "upbeat")


async def effects(plan: EditPlan, scout: Scout) -> list[tuple[float, AssetRef]]:
    """(output second, sound) for every graphic, caption payoff and framing change, spaced so none smear."""
    wanted: list[tuple[float, str]] = []
    for g in plan.graphics:
        for k, name in enumerate(GRAPHIC_SOUNDS.get(g.kind, ["pop"])):
            wanted.append((g.start + (0.3 * k if name != "ding" else 0.35), name))
    for c in plan.captions:
        if c.payoff:
            wanted.append((c.start + 0.3, "ding"))
    for item in plan.inserts:
        wanted.append((max(0.0, item.start - 0.06), "whoosh_short"))
    montage = [i for i in plan.video if i.role == "montage"]
    if montage:
        wanted.append((montage[0].out0, "riser"))
    if plan.brief and plan.brief.path == "voice":
        for item in plan.video:
            if item.sound in ("sizzle", "chop", "pour", "sparkle"):
                wanted.append((item.out0, item.sound))
    out, last = [], -1.0
    cache: dict[str, AssetRef | None] = {}
    for at, name in sorted(wanted):
        if at - last < MIN_SPACING or at >= plan.duration:
            continue
        if name not in cache:
            cache[name] = await scout.sound(name)
        if cache[name]:
            out.append((round(at, 3), cache[name]))
            last = at
    return out


async def voice_track(plan: EditPlan, work: Path) -> Path | None:
    """The kept speech, joined in output order, cleaned. None when nobody speaks in the reel."""
    talking = [i for i in plan.video if i.keeps_voice]
    if not talking:
        return None
    sources = {s.index: s for s in plan.sources}
    inputs: dict[int, Path] = {}
    for src in sorted({i.src for i in talking}):
        source = sources[src]
        mix = work / f"voice_src{src}.wav"
        run(["ffmpeg", "-v", "error", "-y", "-i", source.path, "-vn", "-ac", "2", "-ar", str(SEPARATION_RATE), str(mix)])
        if plan.audio.kind == "voice_song":
            # Separate only the stretch the reel uses: start to end of the kept items of this source.
            lo, hi = min(i.t0 for i in talking if i.src == src), max(i.t1 for i in talking if i.src == src)
            part = work / f"voice_src{src}_part.wav"
            run(["ffmpeg", "-v", "error", "-y", "-ss", f"{max(0.0, lo - 0.5):.3f}", "-t", f"{hi - lo + 1.0:.3f}", "-i", str(mix), str(part)])
            clean = work / f"voice_src{src}_vocals.wav"
            if await asyncio.to_thread(separate, part, clean):
                padded = work / f"voice_src{src}_sep.wav"
                run(["ffmpeg", "-v", "error", "-y", "-i", str(clean), "-af", f"adelay={round(max(0.0, lo - 0.5) * 1000)}:all=1",
                     str(padded)])
                mix = padded
        inputs[src] = mix
    order = sorted(inputs)
    chains, labels = [], []
    for n, item in enumerate(plan.video):
        length = item.out1 - item.out0
        if item.keeps_voice:
            k = order.index(item.src)
            chains.append(f"[{k}:a]atrim={item.t0:.3f}:{item.t1:.3f},asetpts=PTS-STARTPTS,"
                          f"apad=whole_dur={length:.3f},atrim=0:{length:.3f},afade=t=in:d=0.01,afade=t=out:st={max(0.0, length - 0.012):.3f}:d=0.012[a{n}]")
        else:
            chains.append(f"anullsrc=r={SEPARATION_RATE}:cl=stereo,atrim=0:{length:.3f}[a{n}]")
        labels.append(f"[a{n}]")
    chains.append("".join(labels) + f"concat=n={len(labels)}:v=0:a=1,highpass=f=80,afftdn=nf=-28,"
                  "acompressor=threshold=-20dB:ratio=3:attack=5:release=80,volume=1.5[v]")
    out = work / "voice.wav"
    run(["ffmpeg", "-v", "error", "-y", *[a for src in order for a in ("-i", str(inputs[src]))],
         "-filter_complex", ";".join(chains), "-map", "[v]", "-ar", "48000", str(out)])
    return out


async def mix(plan: EditPlan, scout: Scout, work: Path) -> Path:
    total = plan.duration
    voice = await voice_track(plan, work)
    music_ref: AssetRef | None = None
    music_start = 0.0
    if plan.music:
        music_ref = AssetRef(id=plan.music.key, kind="music", path=plan.music.path, licence=plan.music.licence, source=plan.music.source)
        music_start = plan.music.offset
    elif plan.brief and plan.brief.music == "score":
        music_ref = await scout.score(structure(plan), Path(plan.output or "reel").stem)
    elif plan.brief and plan.brief.music == "bed":
        music_ref = scout.bed(plan.brief.mood)
    sfx = await effects(plan, scout)
    inputs: list[str] = []
    chains: list[str] = []
    base = "base"
    chains.append(f"anullsrc=r=48000:cl=stereo,atrim=0:{total:.3f}[{base}]")
    layers = [f"[{base}]"]
    if music_ref:
        inputs += ["-i", music_ref.path]
        m = len(inputs) // 2 - 1
        music_gain = 0.3 if voice else 1.0
        chains.append(f"[{m}:a]aresample=48000,aformat=channel_layouts=stereo,atrim={music_start:.3f}:{music_start + total:.3f},"
                      f"asetpts=PTS-STARTPTS,volume={music_gain},"
                      f"afade=t=out:st={max(0.0, total - 1.2):.3f}:d=1.2[music]")
        plan.audio_items.append(AudioItem(id="m0", kind="music", start=0.0, end=total, asset=music_ref, gain=music_gain))
    if voice:
        inputs += ["-i", str(voice)]
        k = len(inputs) // 2 - 1
        chains.append(f"[{k}:a]aresample=48000,aformat=channel_layouts=stereo,asplit=2[voice][key]")
        if music_ref:
            chains.append("[music][key]sidechaincompress=threshold=0.03:ratio=8:attack=10:release=250[ducked]")
            layers.append("[ducked]")
        else:
            chains.append("[key]anullsink")
        layers.append("[voice]")
        plan.audio_items.append(AudioItem(id="v0", kind="voice", start=0.0, end=total,
                                          asset=AssetRef(id="voice", kind="voice", path=str(voice), licence="user footage", source="user")))
    elif music_ref:
        layers.append("[music]")
    for n, (at, ref) in enumerate(sfx):
        inputs += ["-i", ref.path]
        k = len(inputs) // 2 - 1
        chains.append(f"[{k}:a]aresample=48000,aformat=channel_layouts=stereo,volume=0.55,adelay={round(at * 1000)}:all=1[s{n}]")
        layers.append(f"[s{n}]")
        plan.audio_items.append(AudioItem(id=f"s{n}", kind="sfx", start=at, end=at + 0.5, asset=ref, gain=0.55))
    chains.append("".join(layers) + f"amix=inputs={len(layers)}:duration=first:normalize=0,"
                  f"loudnorm=I=-14:TP=-1:LRA=11,atrim=0:{total:.3f}[out]")
    out = work / "mix.wav"
    run(["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", ";".join(chains), "-map", "[out]", "-ar", "48000", str(out)])
    return out
