"""Every effect the editor can apply, in one list the AI searches before it edits.

Each entry says what it is for and how it goes on the Timeline (the operation to send), and
everything here is drawn by the export (edit_engine). Ids come from the shelves themselves:
sounds and graphics (brain.library), looks (edit_engine.looks), caption styles (the template
catalogue), so the AI never has to guess a name.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from functools import lru_cache
from typing import Literal

from brain import library
from brain.preview import caption_styles
from edit_engine.looks import LOOK_LABELS, LOOKS

EffectKind = Literal["motion", "speed", "transition", "sound", "graphic", "music", "look", "caption_style", "title", "broll"]
KINDS: tuple[EffectKind, ...] = ("motion", "speed", "transition", "sound", "graphic", "music", "look", "caption_style", "title", "broll")


def _add(track: str, item: str) -> str:
    return f"add_item {{track: <id of {"an" if track[0] in "aeiou" else "a"} {track} track; add_track {{kind: \"{track}\"}} first if there is none>, item: {item}}}"


@dataclass(frozen=True)
class Effect:
    kind: EffectKind
    id: str
    name: str
    # What it is for, in an editor's words, and tags to search by.
    use: str
    # How it goes on the Timeline: the operation to send, with the parts to fill in <like this>.
    apply: str


_MOTION = [
    Effect("motion", "punch_in", "Punch-in", "A held closer shot on a key line; alternate with wider shots so cuts read as angle changes. punch zoom close",
           'update_item {item: <clip>, patch: {transform: {scale: 1.15}}} (1.1–1.3)'),
    Effect("motion", "push_in", "Slow push-in", "The camera creeps closer through a moment: emotion, tension, a reveal. zoom keyframes",
           'update_item {item: <clip>, patch: {keyframes: {scale: [{f: 0, v: 1}, {f: <clip frames>, v: 1.2, ease: "in_out"}]}}}'),
    Effect("motion", "snap_zoom", "Snap zoom", "A fast zoom onto a punchline or a reaction. zoom keyframes fast hype",
           'update_item {item: <clip>, patch: {keyframes: {scale: [{f: 0, v: 1}, {f: 6, v: 1.35, ease: "out"}]}}}'),
    Effect("motion", "pan", "Pan", "Move across the frame to follow someone or show a second person. keyframes x",
           'update_item {item: <clip>, patch: {keyframes: {x: [{f: 0, v: 0.35}, {f: <clip frames>, v: 0.65, ease: "in_out"}]}}}'),
    Effect("motion", "reframe", "Reframe", "Keep a face centred in a narrower frame. crop x",
           'update_item {item: <clip>, patch: {transform: {x: <0–1, where the face is across the source>}}}'),
]
_SPEED = [
    Effect("speed", "slow_motion", "Slow motion", "Stretch a moment: an action, a reaction, an emotional beat. The voice slows too, so use it where nobody talks. slowmo",
           'update_item {item: <clip>, patch: {speed: 0.5}} (0.25–0.9)'),
    Effect("speed", "speed_up", "Speed up", "Hurry through a process or a walk; a timelapse feel. fast forward",
           'update_item {item: <clip>, patch: {speed: 2}} (1.25–4)'),
    Effect("speed", "speed_ramp", "Speed ramp", "Normal, then slow on the moment: split the clip at the moment and slow the second piece.",
           'split_item {item: <clip>, at: <frame>, new_id: <id>}, then update_item {item: <id>, patch: {speed: 0.5}}'),
]
_TRANSITIONS = [
    Effect("transition", "flash", "Flash", "A white flash on a cut or a beat drop: energy, a jump in time. flash cut",
           _add("graphic", '{type: "graphic", id: <id>, at: <cut frame>, dur: 2, extra: {solid: "#FFFFFF"}}')),
    Effect("transition", "whoosh_cut", "Whoosh cut", "A cut that moves the story on, sold with a whoosh. Pick the sound with kind=sound query=whoosh.",
           _add("audio", '{type: "sfx", id: <id>, at: <cut frame - 8>, name: <sound id>, dur: <frames>}')),
    Effect("transition", "fade_in", "Fade in (layers)", "Bring B-roll or a picture-in-picture in softly.",
           'update_item {item: <overlay clip>, patch: {transition_in: {type: "fade", frames: 8}}}'),
]
_TITLES = [
    Effect("title", "hook", "Hook title", "Big words at the very start that make people stay. Top of the frame.",
           _add("text", '{type: "text", id: <id>, at: 0, dur: 60, text: <2–6 words>, style: "title", transform: {y: 0.3}}')),
    Effect("title", "pop", "Pop-up words", "A word or number that pops in the middle of the frame as it is said.",
           _add("text", '{type: "text", id: <id>, at: <frame>, dur: 30, text: <1–3 words>, style: "pop", transform: {y: 0.5}}')),
    Effect("title", "lower_third", "Lower line", "A name, a place or a point, in the lower part of the frame.",
           _add("text", '{type: "text", id: <id>, at: <frame>, dur: 90, text: <words>, style: "studio", transform: {y: 0.72}}')),
]
_BROLL = [
    Effect("broll", "cutaway", "Cutaway (B-roll)", "Footage over the talk to show what is being said; the voice carries on underneath. "
           "For the public-domain shelf, use find_broll and place_broll instead of this operation.",
           _add("overlay", '{type: "clip", id: <id>, at: <frame>, asset: <video or image asset>, src_in: <frame>, src_out: <frame>}')),
    Effect("broll", "picture_in_picture", "Picture-in-picture", "A small window over the main shot: a screen, a photo, a reaction.",
           'as a cutaway, plus transform: {scale: 0.35, x: 0.78, y: 0.25} (x/y: where its centre sits in the frame)'),
]


@lru_cache(maxsize=1)
def catalogue() -> tuple[Effect, ...]:
    sounds = [Effect("sound", s.id, s.name, f"{s.category} sound, {s.seconds:.1f} s. {' '.join(s.tags)}",
                     _add("audio", f'{{type: "sfx", id: <id>, at: <frame>, name: "{s.id}", dur: {max(1, round(s.seconds * 30))}, gain_db: 0}}'))
              for s in library.sounds().values()]
    graphics = [Effect("graphic", g.id, g.name, f"Animated overlay, {g.duration:.1f} s, for {', '.join(g.moods) or 'any'} moments"
                       + (f"; its own sound: {g.sfx.stem}" if g.sfx else "") + ".",
                       _add("graphic", f'{{type: "graphic", id: <id>, at: <frame>, dur: {round(g.duration * 30)}, extra: {{graphic: "{g.id}"}}}}'))
                for g in library.graphics().values()]
    tracks = [Effect("music", t.id, t.name, f"{t.mood} music bed, {t.bpm:.0f} bpm, {t.seconds:.0f} s, loops to the end. {' '.join(t.tags)}",
                     f'set_music {{track: "{t.id}"}}') for t in library.music().values()]
    looks = [Effect("look", look, LOOK_LABELS.get(look, look), f"Colour for the whole edit: {LOOK_LABELS.get(look, look).lower()}.",
                    f'set_project {{look: "{look}"}}') for look in LOOKS]
    styles = [Effect("caption_style", s.id, s.name, s.description, f'set_captions {{enabled: true, style: "{s.id}"}}')
              for s in caption_styles()]
    return (*_MOTION, *_SPEED, *_TRANSITIONS, *_TITLES, *_BROLL, *sounds, *graphics, *tracks, *looks, *styles)


def find(kind: EffectKind | None = None, query: str = "", limit: int = 25) -> list[dict[str, str]]:
    """Effects of ``kind`` whose name, id or use holds every word of ``query``."""
    words = query.lower().replace("_", " ").split()
    found = [e for e in catalogue() if (kind is None or e.kind == kind)
             and all(w in f"{e.id.replace('_', ' ')} {e.name} {e.use}".lower() for w in words)]
    return [asdict(e) for e in found[:limit]]


def counts() -> dict[str, int]:
    every = catalogue()
    return {kind: sum(1 for e in every if e.kind == kind) for kind in KINDS}
