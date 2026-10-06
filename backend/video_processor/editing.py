"""Editorial decisions on top of face tracking: layout, shot cuts and beats.

The cutter frames whoever is talking; this module decides how the frame is
built, the way a human editor would. One person on screen is the default and
the camera cuts to whoever talks. The frame is decided shot by shot, from the
people actually in each shot: for vertical output it can stack two regions
(facecam over gameplay, a screen over its presenter, and two people through a
two-shot of them or while they trade quick replies), a shot with nobody in it is shown
whole, and within a followed shot it sets the rhythm: a fresh framing at each
new sentence, a punch-in zoom where a point lands, a cut to the listener's face
for a reaction. Everything here is geometry and timing; FFmpeg work stays in
:mod:`video_processor.ffmpeg_service`.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field, replace
from typing import Any

import cv2
import numpy as np

from video_processor.focus import Focus
from video_processor.geometry import Box
from video_processor.speaker_tracking import SpeakerTrack

# Composite layouts are built for this shape only; other shapes follow a speaker.
VERTICAL = "9:16"
# Correlation between consecutive sampled frames' colour histograms below which
# the picture is treated as a new shot.
SHOT_CUT_CORRELATION = 0.55
# Two cameras on one set share their colours, so histograms miss the cut
# between them; the picture itself still changes completely. Mean absolute
# difference of small greyscale thumbnails (0-255) at or above this, and this
# many times the typical difference nearby, is a cut. Within a podcast shot the
# difference stays under ~13 while angle changes score 30+.
SHOT_CUT_DIFFERENCE = 20.0
SHOT_CUT_DIFFERENCE_RATIO = 4.0
SHOT_CUT_CONTEXT_SAMPLES = 12
THUMBNAIL_SIZE = (64, 36)
PUNCH_IN_ZOOM = 1.2
PUNCH_IN_SECONDS = 2.0
REACT_SECONDS = 1.2
MIN_BEAT_GAP_SECONDS = 3.0
MIN_PART_SECONDS = 0.4
# A facecam is a small face that stays put.
FACECAM_MAX_AREA = 0.06
FACECAM_MAX_DRIFT = 0.05
# A shot shorter than this joins its neighbour; re-laying the frame for a flash
# of footage reads as a glitch.
MIN_SHOT_SECONDS = 1.0
# Face samples either side of a faceless run compared with it, so a dissolve
# that shows the face before its picture settles still counts as a change.
PRESENCE_SETTLE_SAMPLES = 4
# A person is in a shot when seen in at least this share of its sampled frames.
MIN_SHOT_PRESENCE = 0.4
# A stacked speaker's cell is centred this many face heights below the face, so
# the face sits in the upper part of the cell with room for the shoulders.
SPEAKER_HEADROOM = 0.5
# A stacked speaker's cell spans this many face sizes: a head-and-shoulders
# framing where the face reads at phone size, not a wide shot cut in half.
STACK_FACE_SPAN = 2.3
# A stacked cell must actually show its person: a face cut by the edge of the
# picture, or one the crop cannot centre (it is pinned against that edge), puts
# a sliver of shoulder beside an empty set in the cell. Then the speaker is
# followed instead.
FRAME_EDGE_MARGIN = 0.01
STACK_MAX_FACE_OFFSET = 0.25
# A faceless shot is shown whole only when cropping would lose this much more
# width than the output shape keeps; a near match is simply cropped.
FIT_MIN_ASPECT_GAP = 1.15
# Two people are shown at once only while they trade replies: turns no longer
# than this, going back and forth at least EXCHANGE_MIN_TURNS times. Anything
# longer is someone making a point, and the frame belongs to them.
EXCHANGE_MAX_TURN_SECONDS = 4.0
EXCHANGE_MIN_TURNS = 3
# A split shorter than this flashes by; the exchange is cut between faces instead.
MIN_SPLIT_SECONDS = 3.0
# The pair must be in the same picture for this share of the exchange...
PAIR_MIN_TOGETHER = 0.6
# ...and this many face widths apart, or it is one person tracked twice.
PAIR_MIN_SEPARATION = 1.5
# Two people sharing a shot sit about as far from the camera, so their faces are
# of a size; a much smaller face is a photo, poster or screen behind a solo speaker.
PAIR_MIN_SIZE_RATIO = 0.6
# A talking head gets a fresh framing, alternately wide and this much tighter,
# at a new sentence at most this often: the jump-cut zoom editors use so a long
# answer never sits in one static shot.
RHYTHM_ZOOM = 1.12
RHYTHM_MIN_SECONDS = 3.0
# Content shown above its audience takes between these shares of the frame's
# height, as close as it can to its own shape so it fills the width.
CONTENT_MIN_SHARE = 0.32
CONTENT_MAX_SHARE = 0.62
# The audience under shown content: one person framed head and shoulders, a
# group framed from the span of their faces.
AUDIENCE_GROUP_SPAN = 1.4
# A lone face that would need enlarging more than this to fill the audience
# cell is a small webcam: it goes in a round bubble over the content instead.
MAX_AUDIENCE_UPSCALE = 3.0
# The bubble's window on the face, in face sizes.
BUBBLE_FACE_SPAN = 1.9


@dataclass(frozen=True)
class Cell:
    """One stacked region: a source box shown at ``height`` pixels of the output."""

    box: Box
    height: int
    # Show the whole box inside the cell over a blurred copy of itself, rather
    # than cropping it to fill: shown content is never cut, nor padded with
    # whatever happened to surround it on screen.
    fit: bool = False


@dataclass
class Layout:
    kind: str  # follow | fit | content | split_gameplay | two_speaker_stack | screen_with_speaker
    cells: list[Cell] = field(default_factory=list)
    # The region a ``content`` layout fits whole into the frame.
    content: Box | None = None
    # A square window on a small webcam face, shown as a round bubble over ``content``.
    bubble: Box | None = None

    @property
    def composite(self) -> bool:
        return bool(self.cells)


@dataclass(frozen=True)
class Part:
    """A stretch of source to render with one framing treatment."""

    start: float
    end: float
    zoom: float = 1.0
    # Normalised centre to hold the crop on (a reaction shot); None follows the tracking.
    hold: tuple[float, float] | None = None
    # A zoom eases in (a punch-in) or starts at full size (a rhythm cut).
    ease: bool = True


@dataclass(frozen=True)
class Turn:
    """A stretch where one person holds the frame; ``track`` is None when nobody does."""

    start: float
    end: float
    track: SpeakerTrack | None


def thumbnail(frame: np.ndarray) -> np.ndarray:
    """A small greyscale copy for comparing whole pictures."""
    grey = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if frame.ndim == 3 else frame
    return cv2.resize(grey, THUMBNAIL_SIZE, interpolation=cv2.INTER_AREA).astype(np.float32)


def picture_difference(a: np.ndarray, b: np.ndarray) -> float:
    """Mean absolute difference of two thumbnails, 0-255."""
    return float(np.abs(a - b).mean())


def shot_cuts(frames: Iterable[tuple[float, np.ndarray]]) -> list[float]:
    """Timestamps where the picture changes shot, from sampled frames.

    Each cut is stamped at the first sample of the new shot.
    """
    stamps: list[float] = []
    differences: list[float] = []
    colour_cuts: set[float] = set()
    previous_hist = previous_thumb = None
    for timestamp, frame in frames:
        if frame is None or frame.size < 3:
            continue
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        hist = cv2.calcHist([hsv], [0, 1], None, [16, 16], [0, 180, 0, 256])
        cv2.normalize(hist, hist)
        thumb = thumbnail(frame)
        if previous_hist is not None:
            stamp = round(timestamp, 3)
            stamps.append(stamp)
            differences.append(picture_difference(previous_thumb, thumb))
            if cv2.compareHist(previous_hist, hist, cv2.HISTCMP_CORREL) < SHOT_CUT_CORRELATION:
                colour_cuts.add(stamp)
        previous_hist, previous_thumb = hist, thumb

    cuts = set(colour_cuts)
    for index, difference in enumerate(differences):
        nearby = differences[max(0, index - SHOT_CUT_CONTEXT_SAMPLES):index + SHOT_CUT_CONTEXT_SAMPLES + 1]
        typical = float(np.median(nearby))
        if difference >= SHOT_CUT_DIFFERENCE and difference >= typical * SHOT_CUT_DIFFERENCE_RATIO:
            cuts.add(stamps[index])
    return sorted(cuts)


def presence_cuts(frames: Iterable[tuple[float, np.ndarray]], faces_per_frame: Iterable[list[Any]]) -> list[float]:
    """Where the picture turns into, or out of, a stretch with nobody in it.

    A title card or disclaimer that fades into the speaker never jumps from
    one sample to the next, so :func:`shot_cuts` misses it and the card is
    cropped like the speaker's shot. A faceless run lasting ``MIN_SHOT_SECONDS``
    whose picture differs from the face beside it by ``SHOT_CUT_DIFFERENCE`` is
    its own shot. A speaker who only looks away keeps the same picture, so it
    never qualifies. Each cut is stamped at the first sample of the new shot.
    """
    samples = [
        (timestamp, thumbnail(frame), bool(faces))
        for (timestamp, frame), faces in zip(frames, faces_per_frame)
        if frame is not None and frame.size >= 3
    ]
    cuts: list[float] = []
    index = 0
    while index < len(samples):
        if samples[index][2]:
            index += 1
            continue
        after = index
        while after < len(samples) and not samples[after][2]:
            after += 1
        last = samples[after - 1][0] + (samples[after - 1][0] - samples[after - 2][0] if after - index > 1 else 0.0)
        if (samples[after][0] if after < len(samples) else last) - samples[index][0] >= MIN_SHOT_SECONDS:
            middle = samples[(index + after - 1) // 2][1]

            def differs(beside: list[tuple[float, np.ndarray, bool]]) -> bool:
                # A dissolve shows the face before the picture settles, so the
                # settled frames a little further in are compared too.
                return any(picture_difference(thumb, middle) >= SHOT_CUT_DIFFERENCE for _, thumb, _ in beside)

            if index > 0 and differs(samples[max(0, index - PRESENCE_SETTLE_SAMPLES):index]):
                cuts.append(round(samples[index][0], 3))
            if after < len(samples) and differs(samples[after:after + PRESENCE_SETTLE_SAMPLES]):
                cuts.append(round(samples[after][0], 3))
        index = after
    return cuts


def shot_windows(start: float, end: float, cuts: list[float]) -> list[tuple[float, float]]:
    """``start``..``end`` divided at the camera cuts inside it.

    A sliver shorter than ``MIN_SHOT_SECONDS`` joins the shot before it, or
    the one after when it opens the span.
    """
    bounds = [start, *(c for c in sorted(cuts) if start < c < end), end]
    windows: list[list[float]] = []
    for low, high in zip(bounds, bounds[1:]):
        if windows and (high - low < MIN_SHOT_SECONDS or windows[-1][1] - windows[-1][0] < MIN_SHOT_SECONDS):
            windows[-1][1] = high
        else:
            windows.append([low, high])
    return [(low, high) for low, high in windows]


def tracks_in_shot(
    tracks: list[SpeakerTrack], start: float, end: float, sample_interval: float
) -> list[SpeakerTrack]:
    """The people in ``start``..``end``, each cut down to their samples there.

    A track can span camera angles, and a close-up and a wide shot put the same
    person in different places; averaged over both, the box frames neither.
    """
    expected = _expected_samples(start, end, sample_interval)
    windowed = (_within(track, start, end) for track in tracks)
    return [track for track in windowed if len(track.samples) >= expected * MIN_SHOT_PRESENCE]


def speaker_turns(timestamps: list[float], speakers: list[SpeakerTrack | None]) -> list[Turn]:
    """The speaker timeline as runs of one person; each run ends where the next begins."""
    turns: list[Turn] = []
    for timestamp, speaker in zip(timestamps, speakers):
        if turns and turns[-1].track is speaker:
            continue
        if turns:
            turns[-1] = replace(turns[-1], end=timestamp)
        turns.append(Turn(timestamp, timestamp, speaker))
    if turns and timestamps:
        turns[-1] = replace(turns[-1], end=timestamps[-1])
    return turns


def framing_stretches(
    start: float,
    end: float,
    turns: list[Turn],
    sample_interval: float,
    transcript_segments: list[dict[str, Any]],
    present: list[SpeakerTrack] | None = None,
) -> list[tuple[float, float, list[SpeakerTrack]]]:
    """The shot ``start``..``end`` tiled into stretches, each with the pair to show together.

    A two-shot, exactly two people side by side in the picture (``present``),
    is split for its whole length with whoever talks more on top: cropping to
    one of them would throw away the other's reactions, which the wide shot is
    there to show. In any other shot the pair is empty except during a live
    exchange: two people seen side by side, trading quick replies, and, when
    the transcript is diarized, two voices actually heard. A close-up, B-roll
    or a second detection of the same face never splits the screen.
    """
    two_shot = _two_shot(present or [], turns, start, end, sample_interval)
    if two_shot:
        return [(start, end, two_shot)]
    stretches: list[tuple[float, float, list[SpeakerTrack]]] = []
    cursor = start
    for low, high, first, second in _exchanges(turns, start, end):
        pair = [_within(first, low, high), _within(second, low, high)]
        if not (_on_screen_together(pair, low, high, sample_interval)
                and _two_voices(transcript_segments, low, high)):
            continue
        if low - cursor >= MIN_SHOT_SECONDS:
            stretches.append((cursor, low, []))
        elif stretches and stretches[-1][2]:
            low = stretches[-1][1]
        else:
            low = cursor  # A sliver before the exchange joins it rather than flash one face.
        stretches.append((low, high, pair))
        cursor = high
    if end - cursor >= MIN_SHOT_SECONDS or not stretches:
        stretches.append((cursor, end, []))
    else:
        stretches[-1] = (stretches[-1][0], end, stretches[-1][2])
    return stretches


def _exchanges(
    turns: list[Turn], start: float, end: float
) -> list[tuple[float, float, SpeakerTrack, SpeakerTrack]]:
    """Runs of quick replies alternating between the same two people inside ``start``..``end``."""
    found: list[tuple[float, float, SpeakerTrack, SpeakerTrack]] = []
    run: list[Turn] = []

    def close() -> None:
        if len(run) >= EXCHANGE_MIN_TURNS and run[-1].end - run[0].start >= MIN_SPLIT_SECONDS:
            found.append((run[0].start, run[-1].end, run[0].track, run[1].track))

    for turn in turns:
        if turn.end <= start or turn.start >= end:
            continue
        turn = Turn(max(turn.start, start), min(turn.end, end), turn.track)
        quick = turn.track is not None and turn.end - turn.start <= EXCHANGE_MAX_TURN_SECONDS
        replies = bool(run) and turn.track is not run[-1].track and (len(run) < 2 or turn.track is run[-2].track)
        if quick and replies:
            run.append(turn)
            continue
        close()
        run = [turn] if quick else []
    close()
    return found


def _two_shot(
    present: list[SpeakerTrack], turns: list[Turn], start: float, end: float, sample_interval: float,
) -> list[SpeakerTrack]:
    """The two people of a two-shot, the more talkative first; empty for any other shot."""
    if len(present) != 2 or end - start < MIN_SPLIT_SECONDS:
        return []
    pair = [_within(track, start, end) for track in present]
    if not _on_screen_together(pair, start, end, sample_interval):
        return []
    small, large = sorted(typical_box(track).width for track in pair)
    if small < large * PAIR_MIN_SIZE_RATIO:
        return []
    return sorted(pair, key=lambda track: -_talk_time(track, turns, start, end))


def _talk_time(track: SpeakerTrack, turns: list[Turn], start: float, end: float) -> float:
    return sum(
        max(0.0, min(turn.end, end) - max(turn.start, start))
        for turn in turns if turn.track is not None and turn.track.track_id == track.track_id
    )


def _on_screen_together(pair: list[SpeakerTrack], start: float, end: float, sample_interval: float) -> bool:
    """Both people in the same frames, far enough apart to be two people."""
    first, second = pair
    seen = {round(s.timestamp, 3) for s in first.samples}
    together = sum(1 for s in second.samples if round(s.timestamp, 3) in seen)
    if together < _expected_samples(start, end, sample_interval) * PAIR_MIN_TOGETHER:
        return False
    a, b = typical_box(first), typical_box(second)
    return abs(a.center[0] - b.center[0]) >= PAIR_MIN_SEPARATION * max(a.width, b.width)


def _two_voices(transcript_segments: list[dict[str, Any]], start: float, end: float) -> bool:
    """Whether two diarized voices are heard in ``start``..``end``; True without diarization."""
    labels = {str(s["speaker"]) for s in transcript_segments if s.get("speaker")}
    if not labels:
        return True
    heard = {
        str(s["speaker"]) for s in transcript_segments
        if s.get("speaker") and float(s.get("end", 0.0)) > start and float(s.get("start", 0.0)) < end
    }
    return len(heard) >= 2


def _within(track: SpeakerTrack, start: float, end: float) -> SpeakerTrack:
    return SpeakerTrack(
        track_id=track.track_id, samples=[s for s in track.samples if start <= s.timestamp < end], cuts=track.cuts,
    )


def _expected_samples(start: float, end: float, sample_interval: float) -> float:
    return max(1.0, (end - start) / sample_interval)


def choose_layout(
    hint: str,
    detected: str,
    tracks: list[SpeakerTrack],
    aspect_ratio: str,
    source_width: int,
    source_height: int,
    output_width: int,
    output_height: int,
    pair: list[SpeakerTrack] | None = None,
    focus: Focus | None = None,
) -> Layout:
    """How to build the frame, from the director's hint and what was actually detected.

    ``tracks`` are the people in the stretch being framed (see
    :func:`tracks_in_shot`). With nobody there the whole picture is shown, since
    a crop would cut an arbitrary slice out of it. ``pair`` is set only during
    a two-shot or a live exchange (see :func:`framing_stretches`), in the order
    stacked top to bottom; two people are stacked then and never on the
    director's say-so alone, since the director reads the
    transcript and cannot see who is in the picture. A composite layout is used
    only when the faces it needs were found; any other doubt falls back to
    following the speaker, which is always safe.

    ``focus`` (see :mod:`video_processor.focus`) comes first: when the stretch
    is about something on screen, that thing is shown, with the people
    reacting to it below when there are any.
    """
    if focus is not None and focus.content is not None and aspect_ratio == VERTICAL:
        return _content_layout(focus, source_width, source_height, output_width, output_height)
    if not tracks and source_width / max(1, source_height) > output_width / output_height * FIT_MIN_ASPECT_GAP:
        return Layout("fit")
    if aspect_ratio != VERTICAL or source_width / max(1, source_height) < 1.2:
        return Layout("follow")
    wants_split = hint == "split_gameplay" or detected == "gaming_with_facecam"
    wants_screen = hint == "screen_with_speaker" or detected == "speaker_plus_screen"

    if wants_split:
        facecam = _facecam(tracks)
        if facecam is not None:
            top = round(output_height * 0.4) // 2 * 2
            return Layout("split_gameplay", [
                Cell(region_around(facecam, 2.6, output_width / top, source_width, source_height), top),
                Cell(_centre_region(output_width / (output_height - top), source_width, source_height), output_height - top),
            ])
    if pair and len(pair) == 2:
        half = output_height // 2 // 2 * 2
        heights = (half, output_height - half)
        faces = [typical_box(track) for track in pair]
        cells = [
            Cell(region_around(_with_headroom(face), STACK_FACE_SPAN, output_width / h, source_width, source_height), h)
            for face, h in zip(faces, heights)
        ]
        if all(_frames_face(cell.box, face) for cell, face in zip(cells, faces)):
            return Layout("two_speaker_stack", cells)
        return Layout("follow")
    if wants_screen:
        speaker = _most_present(tracks, 1)
        if speaker:
            top = round(output_width * source_height / source_width) // 2 * 2
            return Layout("screen_with_speaker", [
                Cell(Box(0.0, 0.0, 1.0, 1.0), top),
                Cell(region_around(_with_headroom(typical_box(speaker[0])), 3.5, output_width / (output_height - top),
                                   source_width, source_height), output_height - top),
            ])
    return Layout("follow")


def _content_layout(
    focus: Focus, source_width: int, source_height: int, output_width: int, output_height: int,
) -> Layout:
    """Shown content on top and its audience below, or the content alone, fitted whole."""
    content = focus.content.box
    if not focus.people:
        return Layout("content", content=content)
    shape = (content.width * source_width) / max(1.0, content.height * source_height)
    share = min(CONTENT_MAX_SHARE, max(CONTENT_MIN_SHARE, output_width / shape / output_height))
    top = round(output_height * share) // 2 * 2
    bottom = output_height - top
    audience = _audience(list(focus.people), output_width / bottom, source_width, source_height)
    if len(focus.people) == 1 and bottom / max(1.0, audience.height * source_height) > MAX_AUDIENCE_UPSCALE:
        face = typical_box(focus.people[0])
        return Layout("content", content=content,
                      bubble=region_around(face, BUBBLE_FACE_SPAN, 1.0, source_width, source_height))
    return Layout("screen_with_speaker", [Cell(content, top, fit=True), Cell(audience, bottom)])


def _audience(people: list[SpeakerTrack], cell_aspect: float, source_width: int, source_height: int) -> Box:
    """A window on the people watching: one face head and shoulders, a group by the span of their faces."""
    faces = [_with_headroom(typical_box(track)) for track in _most_present(people, 2)]
    if len(faces) == 1:
        return region_around(faces[0], STACK_FACE_SPAN, cell_aspect, source_width, source_height)
    left = min(f.x for f in faces)
    top = min(f.y for f in faces)
    right = max(f.x + f.width for f in faces)
    bottom = max(f.y + f.height for f in faces)
    group = Box(left, top, right - left, bottom - top)
    return region_around(group, AUDIENCE_GROUP_SPAN, cell_aspect, source_width, source_height)


def plan_parts(
    start: float,
    end: float,
    beats: list[dict[str, Any]],
    listener_at: Any,
    sentence_starts: list[float] | None = None,
) -> list[Part]:
    """Split one span of a followed shot into parts around its beats.

    ``listener_at(t)`` returns the normalised centre of someone other than the
    speaker at ``t``, or None; a reaction beat without a listener is skipped.
    Between beats the framing alternates wide and tight at ``sentence_starts``
    (see :func:`_rhythm`).
    """
    sentence_starts = sorted(sentence_starts or [])
    marks: list[Part] = []
    last = -1e9
    for beat in sorted(beats, key=lambda b: float(b.get("t", 0.0))):
        t = float(beat.get("t", 0.0))
        if not (start <= t < end) or t - last < MIN_BEAT_GAP_SECONDS:
            continue
        if beat.get("fx") == "punch_in":
            marks.append(Part(t, min(end, t + PUNCH_IN_SECONDS), zoom=PUNCH_IN_ZOOM))
        elif beat.get("fx") == "react_cut":
            centre = listener_at(t)
            if centre is None:
                continue
            marks.append(Part(t, min(end, t + REACT_SECONDS), hold=centre))
        else:
            continue
        last = t

    parts: list[Part] = []
    cursor = start
    for mark in marks:
        if mark.end - cursor < MIN_PART_SECONDS:
            continue
        mark_start = mark.start
        if mark_start - cursor >= MIN_PART_SECONDS:
            # Wide going into a beat, so a punch-in eases in from the plain frame.
            parts.extend(_rhythm(cursor, mark_start, sentence_starts, end_wide=True))
        elif parts:
            parts[-1] = replace(parts[-1], end=mark_start)
        else:
            # A sliver before the first beat joins the beat, so nothing is lost.
            mark_start = cursor
        parts.append(replace(mark, start=mark_start))
        cursor = mark.end
    if end - cursor >= MIN_PART_SECONDS or not parts:
        parts.extend(_rhythm(cursor, end, sentence_starts, end_wide=False))
    else:
        parts[-1] = replace(parts[-1], end=end)
    return parts


def _rhythm(start: float, end: float, sentence_starts: list[float], end_wide: bool) -> list[Part]:
    """``start``..``end`` cut at new sentences into parts alternating wide and tight.

    Cuts land only on a sentence start, never within ``RHYTHM_MIN_SECONDS`` of
    another cut or of either end, so every framing gets time to breathe.
    """
    bounds = [start]
    for t in sentence_starts:
        if t - bounds[-1] >= RHYTHM_MIN_SECONDS and end - t >= RHYTHM_MIN_SECONDS:
            bounds.append(t)
    bounds.append(end)
    pieces = list(zip(bounds, bounds[1:]))
    parts = []
    for index, (low, high) in enumerate(pieces):
        tight = (len(pieces) - 1 - index if end_wide else index) % 2 == 1
        parts.append(Part(low, high, zoom=RHYTHM_ZOOM, ease=False) if tight else Part(low, high))
    return parts


def region_around(box: Box, expand: float, cell_aspect: float, source_width: int, source_height: int) -> Box:
    """A window of ``cell_aspect`` (width / height) around ``box``, grown ``expand`` times, inside the frame."""
    cx, cy = box.center
    width_px = max(box.width * source_width * expand, box.height * source_height * expand * cell_aspect)
    height_px = width_px / cell_aspect
    scale = min(1.0, source_width / width_px, source_height / height_px)
    width_px, height_px = width_px * scale, height_px * scale
    left = min(max(0.0, cx * source_width - width_px / 2), source_width - width_px)
    top = min(max(0.0, cy * source_height - height_px / 2), source_height - height_px)
    return Box(left / source_width, top / source_height, width_px / source_width, height_px / source_height)


def _centre_region(cell_aspect: float, source_width: int, source_height: int) -> Box:
    return region_around(Box(0.5, 0.5, 0.0, 1.0), 1.0, cell_aspect, source_width, source_height)


def typical_box(track: SpeakerTrack) -> Box:
    """Per-coordinate median of the track's boxes; one stray detection cannot drag it."""
    boxes = [s.face.box for s in track.samples] or [Box()]
    return Box(*(float(np.median([getattr(b, key) for b in boxes])) for key in ("x", "y", "width", "height")))


def _frames_face(cell: Box, face: Box) -> bool:
    """Whether ``cell`` shows the whole of ``face`` near its middle."""
    if face.x < FRAME_EDGE_MARGIN or face.x + face.width > 1.0 - FRAME_EDGE_MARGIN:
        return False
    return abs(face.center[0] - cell.center[0]) <= STACK_MAX_FACE_OFFSET * cell.width


def _with_headroom(face: Box) -> Box:
    return Box(face.x, face.y + face.height * SPEAKER_HEADROOM, face.width, face.height)


def _most_present(tracks: list[SpeakerTrack], count: int) -> list[SpeakerTrack]:
    return sorted(tracks, key=lambda t: len(t.samples), reverse=True)[:count]


def _facecam(tracks: list[SpeakerTrack]) -> Box | None:
    """The mean box of a small, stationary face, or None."""
    for track in _most_present(tracks, 3):
        mean = typical_box(track)
        drift = max(
            (abs(s.face.box.center[0] - mean.center[0]) + abs(s.face.box.center[1] - mean.center[1]))
            for s in track.samples
        ) if track.samples else 1.0
        if mean.area <= FACECAM_MAX_AREA and drift <= FACECAM_MAX_DRIFT:
            return mean
    return None
