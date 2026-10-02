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

The clip's format (:mod:`formats.taxonomy`, chosen by AI from the content)
adds layouts of its own: a reacted-to video over its reactor, a screen share
zoomed on what is changing, a keyed green screen, voice-over footage followed
by what stands out in it. Each is built only when the picture in that shot
supports it; otherwise the shot falls through to the talking-head rules above,
which are always safe.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field, replace
from typing import Any

import cv2
import numpy as np

from formats.taxonomy import DEFAULT_FORMAT, VisualEvidence, recipe_for
from video_processor.geometry import Box, crop_around, normalize_box, target_crop_size
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
# A person is in a shot when seen in at least this share of its sampled frames.
MIN_SHOT_PRESENCE = 0.4
# A stacked speaker's cell is centred this many face heights below the face, so
# the face sits in the upper part of the cell with room for the shoulders.
SPEAKER_HEADROOM = 0.5
# A stacked speaker's cell spans this many face sizes: a head-and-shoulders
# framing where the face reads at phone size, not a wide shot cut in half.
STACK_FACE_SPAN = 2.3
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
# Formats paced harder than a talking head change framing more often. A format
# whose recipe turns the rhythm off gets none (see rhythm_seconds).
RHYTHM_SECONDS_BY_FORMAT: dict[str, float] = {"yap": 1.8}
# Formats built on two people, or one person playing two, sharing the picture:
# stacked whenever the pair is on screen together, not only while they trade
# quick replies, and without asking for two diarized voices, since a clone has
# one voice.
PAIR_FORMATS = frozenset({"split_screen", "clone"})
# A facecam over gameplay in a split-screen clip, when the probe saw one in at
# least this share of frames (the format's own evidence threshold).
SPLIT_FACECAM_MIN = 0.4
# A reacted-to video is fitted in a top cell of between these shares of the
# output height, the reactor's face filling the rest.
REACTION_CONTENT_SHARE = (0.35, 0.55)
# The reactor's cell spans this many face sizes, as the facecam cell of a split does.
REACTOR_FACE_SPAN = 2.6
# The region left once the reactor is masked must be this share of the frame
# to be the thing being reacted to.
MIN_CONTENT_SHARE = 0.2
# A screen share with a webcam gives the screen this share of the output height.
SCREEN_FOCUS_SHARE = 0.7
# The zoom window is this much larger than what changed, so the line being typed
# keeps its neighbours for context...
FOCUS_MARGIN = 1.4
# ...and never narrower than this share of the screen, so it never zooms past
# the point where an upscale turns text to mush.
FOCUS_MIN_WIDTH = 0.25
# The window is sized for this percentile of what changed through the shot, so
# one full-screen slide change does not widen a shot spent typing.
FOCUS_SPREAD_PERCENTILE = 80
# Green screens are keyed when the probe saw this much green, and a graphic
# behind the creator is used when it saw this much still backdrop (the
# format's own evidence thresholds).
GREEN_KEY_MIN = 0.25
GRAPHIC_BACKDROP_MIN = 0.35
# A keyed creator stands in the bottom share of the frame, framed this many
# face sizes wide: head, shoulders and the hands they talk with.
KEYED_PERSON_SHARE = 0.62
KEYED_PERSON_SPAN = 3.6
# FFmpeg's colour for a studio green screen.
DEFAULT_KEY_COLOUR = "0x00B140"


@dataclass(frozen=True)
class Cell:
    """One stacked region: a source box shown at ``height`` pixels of the output.

    ``fill`` is how the box meets its cell: "crop" scales it to cover the cell
    (the box already has the cell's shape), "fit" shows all of it over a
    blurred copy of itself, "blur" is a neutral backdrop made from it, and
    "key" chroma-keys it over the cell before it. A cell with ``roam`` is a
    window of ``box``'s size that moves inside ``roam`` with what the viewer
    should be looking at; ``path`` is its top-left over time, ``(source
    seconds, x, y)``, filled in by the cutter.
    """

    box: Box
    height: int
    fill: str = "crop"
    roam: Box | None = None
    path: tuple[tuple[float, float, float], ...] = ()


@dataclass
class Layout:
    # follow | fit | split_gameplay | two_speaker_stack | screen_with_speaker
    # | reaction_stack | screen_focus | green_screen | voice_over
    kind: str
    cells: list[Cell] = field(default_factory=list)
    # FFmpeg colour to key out of a "key" cell.
    key: str = ""

    @property
    def composite(self) -> bool:
        return bool(self.cells)

    @property
    def seam(self) -> float | None:
        """Where the top cell meets the next, as a share of the height, for a
        stack of regions; None for a single region or a keyed composite."""
        if len(self.cells) < 2 or any(cell.fill == "key" for cell in self.cells):
            return None
        return self.cells[0].height / sum(cell.height for cell in self.cells)


@dataclass(frozen=True)
class FormatContext:
    """What the cut knows about a clip's format, for the layouts built for it."""

    content_format: str = DEFAULT_FORMAT
    evidence: VisualEvidence | None = None
    # Per sampled frame of the stretch being framed, the region to look at
    # (what changed on a screen share, what stands out in voice-over footage),
    # or None where nothing did; see video_processor.focus.
    focus: tuple[tuple[float, Box | None], ...] = ()
    # The green screen's colour; empty when the clip's frames show none, and
    # then nothing is keyed whatever the probe reported.
    key_colour: str = DEFAULT_KEY_COLOUR


@dataclass(frozen=True)
class Canvas:
    source_width: int
    source_height: int
    output_width: int
    output_height: int


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
    any_pair: bool = False,
) -> list[tuple[float, float, list[SpeakerTrack]]]:
    """The shot ``start``..``end`` tiled into stretches, each with the pair to show together.

    A two-shot, exactly two people side by side in the picture (``present``),
    is split for its whole length with whoever talks more on top: cropping to
    one of them would throw away the other's reactions, which the wide shot is
    there to show. In any other shot the pair is empty except during a live
    exchange: two people seen side by side, trading quick replies, and, when
    the transcript is diarized, two voices actually heard. A close-up, B-roll
    or a second detection of the same face never splits the screen.

    ``any_pair`` is for formats built on a pair (:data:`PAIR_FORMATS`): the
    two people seen most are stacked even with a third face in the shot, and
    an exchange needs no second voice, since a clone talks to itself.
    """
    two_shot = _two_shot(present or [], turns, start, end, sample_interval, any_pair)
    if two_shot:
        return [(start, end, two_shot)]
    stretches: list[tuple[float, float, list[SpeakerTrack]]] = []
    cursor = start
    for low, high, first, second in _exchanges(turns, start, end):
        pair = [_within(first, low, high), _within(second, low, high)]
        if not (_on_screen_together(pair, low, high, sample_interval)
                and (any_pair or _two_voices(transcript_segments, low, high))):
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
    any_pair: bool = False,
) -> list[SpeakerTrack]:
    """The two people of a two-shot, the more talkative first; empty for any other shot.

    With ``any_pair`` the two people seen most make the pair however many are present.
    """
    if (len(present) < 2 if any_pair else len(present) != 2) or end - start < MIN_SPLIT_SECONDS:
        return []
    pair = [_within(track, start, end) for track in (_most_present(present, 2) if any_pair else present)]
    if not _on_screen_together(pair, start, end, sample_interval):
        return []
    small, large = sorted(_typical_box(track).width for track in pair)
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
    a, b = _typical_box(first), _typical_box(second)
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
    context: FormatContext | None = None,
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

    ``context`` carries the clip's format; a format with a layout of its own
    (see :data:`_FORMAT_LAYOUTS`) gets it when this stretch supports it, and
    otherwise the rules below apply as for any talking head.
    """
    canvas = Canvas(source_width, source_height, output_width, output_height)
    build = _FORMAT_LAYOUTS.get(recipe_for(context.content_format).layout) if context else None
    if build and aspect_ratio == VERTICAL and source_width / max(1, source_height) >= 1.2:
        frame = build(tracks, pair or [], context, canvas)
        if frame is not None:
            return frame
    if not tracks and source_width / max(1, source_height) > output_width / output_height * FIT_MIN_ASPECT_GAP:
        return Layout("fit")
    if aspect_ratio != VERTICAL or source_width / max(1, source_height) < 1.2:
        return Layout("follow")
    wants_split = hint == "split_gameplay" or detected == "gaming_with_facecam"
    wants_screen = hint == "screen_with_speaker" or detected == "speaker_plus_screen"

    if wants_split:
        facecam = _facecam(tracks)
        if facecam is not None:
            return _split_gameplay(facecam, canvas)
    if pair and len(pair) == 2:
        half = output_height // 2 // 2 * 2
        heights = (half, output_height - half)
        return Layout("two_speaker_stack", [
            Cell(region_around(_with_headroom(_typical_box(track)), STACK_FACE_SPAN, output_width / h,
                               source_width, source_height), h)
            for track, h in zip(pair, heights)
        ])
    if wants_screen:
        speaker = _most_present(tracks, 1)
        if speaker:
            top = round(output_width * source_height / source_width) // 2 * 2
            return Layout("screen_with_speaker", [
                Cell(Box(0.0, 0.0, 1.0, 1.0), top),
                Cell(region_around(_with_headroom(_typical_box(speaker[0])), 3.5, output_width / (output_height - top),
                                   source_width, source_height), output_height - top),
            ])
    return Layout("follow")


def _split_gameplay(facecam: Box, canvas: Canvas) -> Layout:
    """A facecam over the middle of the gameplay it sits on."""
    width, height = canvas.output_width, canvas.output_height
    top = _even(height * 0.4)
    return Layout("split_gameplay", [
        Cell(region_around(facecam, REACTOR_FACE_SPAN, width / top, canvas.source_width, canvas.source_height), top),
        Cell(_centre_region(width / (height - top), canvas.source_width, canvas.source_height), height - top),
    ])


def _over_face(kind: str, top: Cell, face: Box, canvas: Canvas) -> Layout:
    """``top`` over a cell framing ``face``, with headroom, in the rest of the height.

    The bottom-of-frame counterpart of :func:`_split_gameplay`: what the
    person is talking about or reacting to reads first, their face answers it.
    """
    height = canvas.output_height - top.height
    region = region_around(_with_headroom(face), REACTOR_FACE_SPAN, canvas.output_width / height,
                           canvas.source_width, canvas.source_height)
    return Layout(kind, [top, Cell(region, height)])


def _fitted_cell(content: Box, canvas: Canvas) -> Cell:
    """``content`` fitted to the output width in a top cell about its own height,
    kept within :data:`REACTION_CONTENT_SHARE` of the frame."""
    fitted = canvas.output_width * content.height * canvas.source_height / (content.width * canvas.source_width)
    low, high = REACTION_CONTENT_SHARE
    return Cell(content, _even(min(max(fitted, canvas.output_height * low), canvas.output_height * high)), fill="fit")


def _split_screen(
    tracks: list[SpeakerTrack], pair: list[SpeakerTrack], context: FormatContext, canvas: Canvas,
) -> Layout | None:
    """A split-screen clip without two people on screen together: a facecam over
    gameplay when the probe saw one. Two people are stacked by the usual pair
    rules, which :data:`PAIR_FORMATS` relaxes for this format."""
    if pair or context.evidence is None or context.evidence.facecam < SPLIT_FACECAM_MIN:
        return None
    facecam = _facecam(tracks)
    return _split_gameplay(facecam, canvas) if facecam is not None else None


def _reaction_stack(
    tracks: list[SpeakerTrack], pair: list[SpeakerTrack], context: FormatContext, canvas: Canvas,
) -> Layout | None:
    """What is being reacted to, fitted whole on top, over the reactor's face.

    The content is where the probe found it, or else the largest part of the
    frame clear of the reactor. Without a face in the shot there is nobody to
    show reacting, and the shot is framed as any other.
    """
    reactor = _most_present(tracks, 1)
    if not reactor:
        return None
    face = _typical_box(reactor[0])
    content = _evidence_box(context.evidence, "content_box") or _beside(face)
    if content is None or content.area < MIN_CONTENT_SHARE:
        return None
    return _over_face("reaction_stack", _fitted_cell(content, canvas), face, canvas)


def _screen_focus(
    tracks: list[SpeakerTrack], pair: list[SpeakerTrack], context: FormatContext, canvas: Canvas,
) -> Layout | None:
    """A screen share zoomed on what is changing, over the presenter's webcam if there is one.

    The zoom window is sized from the activity through the stretch (see
    :func:`_focus_window`) and moved with it by the cutter. When what changes
    is too wide to zoom on (a new slide, a full-page scroll) or nothing
    changes, the whole screen is fitted instead. A presenter filling the shot
    rather than sitting in a webcam corner is followed as a talking head.
    """
    face = _facecam(tracks)
    if tracks and face is None:
        return None
    screen = _evidence_box(context.evidence, "content_box") or Box()
    top = canvas.output_height if face is None else _even(canvas.output_height * SCREEN_FOCUS_SHARE)
    window = _focus_window(context.focus, screen, canvas.output_width / top, canvas)
    cell = Cell(window, top, roam=screen) if window else Cell(screen, top, fill="fit")
    return Layout("screen_focus", [cell]) if face is None else _over_face("screen_focus", cell, face, canvas)


def _green_screen(
    tracks: list[SpeakerTrack], pair: list[SpeakerTrack], context: FormatContext, canvas: Canvas,
) -> Layout | None:
    """A creator in front of what they talk about.

    A real green screen is keyed and the creator stands at the bottom of a
    full-height backdrop: the graphic behind them when the probe saw one, or
    else a neutral, darkened blur of the shot (the green itself turns grey).
    A screen already composited in the source is stacked instead: the graphic
    fitted on top, the creator below. Without evidence of either, or without
    the creator's face, the shot is framed as any other.
    """
    evidence = context.evidence
    person = _most_present(tracks, 1)
    if evidence is None or not person:
        return None
    face = _typical_box(person[0])
    has_graphic = evidence.graphic_backdrop >= GRAPHIC_BACKDROP_MIN
    graphic = _evidence_box(evidence, "content_box") if has_graphic else None
    width, height = canvas.output_width, canvas.output_height
    if evidence.green >= GREEN_KEY_MIN and context.key_colour:
        person_height = _even(height * KEYED_PERSON_SHARE)
        cutout = region_around(_with_headroom(face), KEYED_PERSON_SPAN, width / person_height,
                               canvas.source_width, canvas.source_height)
        backdrop = Cell(graphic, height, fill="fit") if graphic else Cell(Box(), height, fill="blur")
        return Layout("green_screen", [backdrop, Cell(cutout, person_height, fill="key")], key=context.key_colour)
    if has_graphic:
        graphic = graphic or _beside(face)
        if graphic is not None and graphic.area >= MIN_CONTENT_SHARE:
            return _over_face("green_screen", _fitted_cell(graphic, canvas), face, canvas)
    return None


def _voice_over(
    tracks: list[SpeakerTrack], pair: list[SpeakerTrack], context: FormatContext, canvas: Canvas,
) -> Layout | None:
    """Footage with nobody to follow, cropped on what stands out and moves in it.

    Shown whole when the salient part is wider than the crop, since cropping
    would cut it in half. A shot with someone in it is framed on them as usual.
    """
    boxes = [box for _, box in context.focus if box is not None]
    if tracks or not boxes:
        return None
    sw, sh = canvas.source_width, canvas.source_height
    shape = f"{canvas.output_width}:{canvas.output_height}"
    crop_width, _ = target_crop_size(sw, sh, shape)
    if float(np.percentile([box.width for box in boxes], FOCUS_SPREAD_PERCENTILE)) * sw > crop_width:
        return Layout("fit")
    window = crop_around(*_median_centre(boxes), sw, sh, shape)
    return Layout("voice_over", [Cell(window, canvas.output_height, roam=Box())])


def _focus_window(
    focus: tuple[tuple[float, Box | None], ...], screen: Box, cell_aspect: float, canvas: Canvas,
) -> Box | None:
    """A window of ``cell_aspect`` inside ``screen`` big enough for what changes
    through the stretch, centred on where it typically changes; None when
    nothing changed or what changed does not fit a window of that shape."""
    boxes = [box for _, box in focus if box is not None]
    if not boxes:
        return None
    sw, sh = canvas.source_width, canvas.source_height
    need_width = float(np.percentile([box.width for box in boxes], FOCUS_SPREAD_PERCENTILE)) * sw * FOCUS_MARGIN
    need_height = float(np.percentile([box.height for box in boxes], FOCUS_SPREAD_PERCENTILE)) * sh * FOCUS_MARGIN
    width_px = max(need_width, need_height * cell_aspect, FOCUS_MIN_WIDTH * screen.width * sw)
    height_px = width_px / cell_aspect
    if width_px > screen.width * sw or height_px > screen.height * sh:
        return None
    cx, cy = _median_centre(boxes)
    left = min(max(screen.x * sw, cx * sw - width_px / 2), (screen.x + screen.width) * sw - width_px)
    top = min(max(screen.y * sh, cy * sh - height_px / 2), (screen.y + screen.height) * sh - height_px)
    return Box(left / sw, top / sh, width_px / sw, height_px / sh)


def _median_centre(boxes: list[Box]) -> tuple[float, float]:
    return float(np.median([b.center[0] for b in boxes])), float(np.median([b.center[1] for b in boxes]))


def _evidence_box(evidence: VisualEvidence | None, name: str) -> Box | None:
    """A normalised ``(x, y, w, h)`` box from the probe's evidence, or None."""
    value = getattr(evidence, name, None) if evidence else None
    if not value or len(value) != 4:
        return None
    return normalize_box(Box(*(float(v) for v in value)))


def _beside(face: Box) -> Box | None:
    """The largest part of the frame clear of a person: left of them, right of
    them or above them, leaving a face width either side for their shoulders."""
    left = max(0.0, face.x - face.width)
    right = min(1.0, face.x + 2 * face.width)
    above = max(0.0, face.y - face.height / 2)
    regions = [Box(0.0, 0.0, left, 1.0), Box(right, 0.0, 1.0 - right, 1.0), Box(0.0, 0.0, 1.0, above)]
    regions = [box for box in regions if box.width > 0 and box.height > 0]
    return max(regions, key=lambda box: box.width * box.height, default=None)


def _even(value: float) -> int:
    return round(value) // 2 * 2


# Layouts a format asks for (Recipe.layout) and the builder that makes one from
# a stretch, or returns None when the stretch cannot support it. "follow" and
# "clone_stack" need none: a clone is stacked by the pair rules (PAIR_FORMATS).
_FORMAT_LAYOUTS = {
    "two_speaker_stack": _split_screen,
    "reaction_stack": _reaction_stack,
    "screen_focus": _screen_focus,
    "green_screen": _green_screen,
    "voice_over": _voice_over,
}


def rhythm_seconds(content_format: str | None) -> float | None:
    """Least time between wide/tight rhythm cuts for a format; None when it has no rhythm."""
    recipe = recipe_for(content_format)
    if not recipe.rhythm:
        return None
    return RHYTHM_SECONDS_BY_FORMAT.get(recipe.format, RHYTHM_MIN_SECONDS)


def plan_parts(
    start: float,
    end: float,
    beats: list[dict[str, Any]],
    listener_at: Any,
    sentence_starts: list[float] | None = None,
    rhythm_every: float | None = RHYTHM_MIN_SECONDS,
) -> list[Part]:
    """Split one span of a followed shot into parts around its beats.

    ``listener_at(t)`` returns the normalised centre of someone other than the
    speaker at ``t``, or None; a reaction beat without a listener is skipped.
    Between beats the framing alternates wide and tight at ``sentence_starts``
    no more often than every ``rhythm_every`` seconds (see :func:`_rhythm`),
    or holds when it is None (see :func:`rhythm_seconds`).
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
            parts.extend(_rhythm(cursor, mark_start, sentence_starts, rhythm_every, end_wide=True))
        elif parts:
            parts[-1] = replace(parts[-1], end=mark_start)
        else:
            # A sliver before the first beat joins the beat, so nothing is lost.
            mark_start = cursor
        parts.append(replace(mark, start=mark_start))
        cursor = mark.end
    if end - cursor >= MIN_PART_SECONDS or not parts:
        parts.extend(_rhythm(cursor, end, sentence_starts, rhythm_every, end_wide=False))
    else:
        parts[-1] = replace(parts[-1], end=end)
    return parts


def _rhythm(
    start: float, end: float, sentence_starts: list[float], every: float | None, end_wide: bool,
) -> list[Part]:
    """``start``..``end`` cut at new sentences into parts alternating wide and tight.

    Cuts land only on a sentence start, never within ``every`` seconds of
    another cut or of either end, so every framing gets time to breathe. With
    ``every`` None the span is one plain part.
    """
    if every is None:
        return [Part(start, end)]
    bounds = [start]
    for t in sentence_starts:
        if t - bounds[-1] >= every and end - t >= every:
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


def _typical_box(track: SpeakerTrack) -> Box:
    """Per-coordinate median of the track's boxes; one stray detection cannot drag it."""
    boxes = [s.face.box for s in track.samples] or [Box()]
    return Box(*(float(np.median([getattr(b, key) for b in boxes])) for key in ("x", "y", "width", "height")))


def _with_headroom(face: Box) -> Box:
    return Box(face.x, face.y + face.height * SPEAKER_HEADROOM, face.width, face.height)


def _most_present(tracks: list[SpeakerTrack], count: int) -> list[SpeakerTrack]:
    return sorted(tracks, key=lambda t: len(t.samples), reverse=True)[:count]


def _facecam(tracks: list[SpeakerTrack]) -> Box | None:
    """The mean box of a small, stationary face, or None."""
    for track in _most_present(tracks, 3):
        mean = _typical_box(track)
        drift = max(
            (abs(s.face.box.center[0] - mean.center[0]) + abs(s.face.box.center[1] - mean.center[1]))
            for s in track.samples
        ) if track.samples else 1.0
        if mean.area <= FACECAM_MAX_AREA and drift <= FACECAM_MAX_DRIFT:
            return mean
    return None
