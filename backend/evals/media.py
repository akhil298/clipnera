"""Test media for the golden set: MUDs written by hand, so evals need no video files or analysis."""

from __future__ import annotations

from understanding.mud import MUD, Beat, Drop, Moment, Music, Scene, Shot, Silence, Utterance, Word

LINES = [
    (0.5, "Hi, I'm back with a quick update on the shop."),
    (5.0, "Um, so first, let's talk about pricing."),
    (9.0, "Our pricing starts at nine dollars a month, and that covers everything."),
    (15.0, "Uh, the second thing is shipping, which is now free over fifty dollars."),
    (20.0, "Now the money part: we saved forty percent by switching suppliers."),
    (26.5, "That saving goes straight back to you."),
    (31.0, "Third, we have a brand new colour, a deep forest green."),
    (37.0, "Why does it matter? Because you asked for it, a lot."),
    (43.0, "Um, we also fixed the zip that kept breaking."),
    (49.0, "So that's the update, thanks for watching, and follow for more."),
]
FILLERS = {"Um,": "um", "Uh,": "uh"}


def talking_head(asset_id: str = "a1", *, extra_line: str | None = None, caption_injection: str | None = None) -> MUD:
    """60 s of one person talking, ten lines, a filler or two, long pauses, a shot every 6 s."""
    lines = list(LINES)
    if extra_line:
        lines.insert(3, (13.0, extra_line))
    words, utterances, t_index = [], [], 0
    for n, (start, text) in enumerate(sorted(lines)):
        t = start
        first = t_index
        for token in text.split():
            words.append(Word(i=t_index, t0=round(t, 3), t1=round(t + 0.28, 3), text=token, conf=0.95,
                              filler=FILLERS.get(token)))
            t += 0.34
            t_index += 1
        utterances.append(Utterance(id=f"u{n:04d}", t0=start, t1=words[-1].t1, w0=first, w1=t_index - 1, text=text))
    silences = [Silence(t0=a.t1, t1=b.t0, kind="dead_air" if b.t0 - a.t1 >= 1 else "pause")
                for a, b in zip(utterances, utterances[1:]) if b.t0 - a.t1 >= 0.3]
    shots = [Shot(id=f"sh{n:04d}", t0=n * 6.0, t1=min(60.0, (n + 1) * 6.0), scene_id="", usable=True, blur=120,
                  brightness=110, motion=4 + n % 3, faces=1, face_x=0.5,
                  caption=caption_injection if caption_injection and n == 2 else f"person talking to camera, shot {n}")
             for n in range(10)]
    scenes = []
    for n in range(0, 10, 3):
        ids = [s.id for s in shots[n:n + 3]]
        for s in shots[n:n + 3]:
            s.scene_id = f"sc{n // 3:03d}"
        scenes.append(Scene(id=f"sc{n // 3:03d}", t0=shots[n].t0, t1=shots[min(9, n + 2)].t1, shot_ids=ids))
    moments = [Moment(id=f"m{n:03d}", t0=u.t0, t1=u.t1, score=round(0.9 - 0.06 * n, 2), kind="quote", why="spoken line",
                      shot_ids=[s.id for s in shots if s.t1 > u.t0 and s.t0 < u.t1])
               for n, u in enumerate(sorted(utterances, key=lambda u: ("pricing" not in u.text and "money" not in u.text, u.t0)))]
    return MUD(asset_id=asset_id, kind="video", duration=60.0, width=1080, height=1920, has_audio=True, language="en",
               analyzers={"probe": "ok"}, speech_ratio=0.6, words=words, utterances=utterances, silences=silences,
               shots=shots, scenes=scenes, moments=sorted(moments, key=lambda m: m.t0))


def song(asset_id: str = "m1") -> MUD:
    """60 s at 120 bpm: a beat every 0.5 s, a bar every 2 s, drops at 8, 16 and 24 s."""
    beats = [Beat(t=round(i * 0.5, 3), is_downbeat=i % 4 == 0, bar=i // 4 + 1, beat_in_bar=i % 4 + 1) for i in range(120)]
    return MUD(asset_id=asset_id, kind="audio", duration=60.0, has_audio=True, analyzers={"music": "ok"},
               speech_ratio=0.0, beats=beats,
               music=Music(tempo_bpm=120.0, drops=[Drop(t=8.0, strength=1.0), Drop(t=16.0, strength=0.8),
                                                    Drop(t=24.0, strength=0.9)]),
               scenes=[Scene(id="sc000", t0=0, t1=60)])
