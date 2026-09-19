# Advanced Layouts — Implementation Plan

Two new output formats for the clipping pipeline:

- **Feature A — Split-Screen Gaming Layout:** stacked gameplay-over-facecam for
  9:16 gaming clips.
- **Feature B — Countdown Compilation:** several highlights concatenated into
  one ranked "Top N" clip with a persistent header and numbered list.

**Status:** proposed, not started
**Prerequisite:** render-performance fixes should land first (see *Sequencing*)

---

# Feature A — Split-Screen Gaming Layout

---

## A1. What we are building

For gaming content where a streamer's webcam is composited into the corner of a
gameplay recording, produce a vertical clip that stacks two independently
cropped regions:

```
┌─────────────────┐
│                 │
│    GAMEPLAY     │  top ~60%   — cropped from the gameplay region
│                 │
├─────────────────┤
│                 │
│    FACECAM      │  bottom ~40% — cropped from the webcam inset
│                 │
└─────────────────┘
```

Both regions come from the *same* source frame, cropped separately and stacked.
This is the dominant format for gaming shorts and is what our current renderer
cannot express.

## A2. Why the current pipeline cannot do this

The classifier already recognises the case. `ClipCutter._classify_layout`
(`backend/video_processor/clip_cutter.py:297`) returns `gaming_with_facecam`
when the content category is `gaming` and at least one face track exists.

The renderer, however, is single-region by construction:

- `_build_tracking` (`clip_cutter.py:326`) returns **one** crop rectangle per
  timestamp.
- `_render` (`clip_cutter.py:406`) passes that single rectangle to
  `FFmpegService.crop_with_tracking`.
- `crop_with_tracking` (`ffmpeg_service.py:189`) emits exactly one filter chain:
  `crop=W:H:x:y,scale=tw:th:flags=lanczos`.

So `gaming_with_facecam` currently resolves to the `cover_subjects` strategy,
which computes the smallest single rectangle enclosing every subject. On a
gameplay frame with a corner webcam that rectangle is close to the full frame,
which then gets squeezed into 9:16 — a small, wide strip. The layout is
detected and then effectively discarded.

## A3. Design

### 3.1 Facecam detection

New module: `backend/video_processor/facecam.py`.

A face track is treated as a facecam when **all** hold:

| Signal | Threshold | Rationale |
|---|---|---|
| Face centre lies in a frame corner | within 35% of a corner on both axes | webcams are cornered, not centred |
| Face area | < 12% of frame area | a facecam face is small relative to frame |
| Positional stability | centre drifts < 5% of frame width across the clip | insets are pinned; a talking head moves |
| Source aspect | landscape (ratio > 1.2) | portrait sources are not gameplay captures |

Detection runs on the frames `_sample_frames` already decodes, so it adds no
new FFmpeg pass.

```python
@dataclass(frozen=True)
class FacecamRegion:
    box: Box                 # normalised, padded webcam bounds
    corner: str              # "tl" | "tr" | "bl" | "br"
    confidence: float        # 0..1
```

`detect_facecam(tracks, frames, source_width, source_height) -> FacecamRegion | None`

Confidence blends the four signals. Below `FACECAM_MIN_CONFIDENCE = 0.6` we
return `None` and the clip falls through to today's behaviour. **Failing closed
is deliberate** — a false positive stacks an ordinary talking-head clip and
looks broken, which is far worse than not applying the layout.

The returned box is padded ~8% beyond the detected face so the crop contains the
whole webcam inset (shoulders, border) rather than just the face.

### 3.2 Gameplay region

The gameplay crop is the frame with the facecam corner excluded: take the
largest 16:9-ish window that avoids `FacecamRegion.box`, then centre-crop it to
the top panel's target ratio. When exclusion is not possible without losing more
than ~25% of the frame, use a plain centre crop — the webcam overlapping a
corner of the gameplay panel is acceptable and normal for the format.

### 3.3 Multi-region render

`CutRequest` / `CutResult` (`clip_cutter.py:80-115`) keep their existing
single-crop fields; we add an optional composite plan so nothing downstream
breaks:

```python
@dataclass
class CompositeRegion:
    source_box: Box                       # what to crop from the source
    tracking: list[dict[str, Any]]        # per-frame boxes, same shape as today
    target_height_fraction: float         # 0.6 for gameplay, 0.4 for facecam

@dataclass
class CompositePlan:
    regions: list[CompositeRegion]        # top to bottom
    layout: str                           # "gaming_split"
```

New `FFmpegService.render_composite()` builds a `vstack`:

```
[0:v]crop=<gameplay>,scale=1080:1152:flags=lanczos[top];
[0:v]crop=<facecam>,scale=1080:768:flags=lanczos[bottom];
[top][bottom]vstack=inputs=2[v]
```

Panel heights must be even and sum exactly to the target height (1080×1920 →
1152 + 768). Rounding each independently can produce a 1918px output, so the
second panel is computed as `target_height - first_panel_height`.

Existing single-crop rendering is untouched; `render_composite` is a sibling of
`crop_with_tracking`, selected by `_render` when a `CompositePlan` is present.

### 3.4 Gating

The split layout applies only when **all** hold:

- `content_category == "gaming"`
- `detect_facecam` returns a region above the confidence floor
- target aspect ratio is `9:16` (the stack is meaningless for 16:9 or 1:1)

Any failure falls back to the current `cover_subjects` path.

## A4. Files touched

| File | Change |
|---|---|
| `video_processor/facecam.py` | **new** — detection + region geometry |
| `video_processor/clip_cutter.py` | build `CompositePlan` for `gaming_with_facecam`; pass to `_render` |
| `video_processor/ffmpeg_service.py` | **new** `render_composite()` — vstack graph |
| `video_processor/geometry.py` | helper: largest box excluding a region |
| `tests/test_facecam_detection.py` | **new** — detection thresholds, corners, negatives |
| `tests/test_composite_render.py` | **new** — filter-graph construction, panel arithmetic |

No API, schema, or database change. No frontend change: the clip is still one
mp4 per aspect ratio, so `mapBackendClip` and the editor are unaffected.

## A5. Testing

**Unit.** Facecam detection against synthesised track fixtures: each of the four
corners; a centred talking head (must return `None`); a face too large (must
return `None`); a drifting face (must return `None`); an empty track list.

**Filter graph.** Assert the composite string is well-formed and that panel
heights sum exactly to the target, across 1080×1920, 1080×1350 and odd source
dimensions.

**Integration.** One real gaming clip with a corner webcam end-to-end, asserting
output dimensions and that both panels contain non-uniform pixel content (a
black panel means a crop landed off-frame).

**Regression.** A non-gaming clip must produce a byte-identical filter graph to
today's, proving the single-crop path is untouched.

## A6. Risks

| Risk | Mitigation |
|---|---|
| False positives stacking normal clips | High confidence floor; fail closed to current behaviour |
| Facecam moves or disappears mid-clip | Require stability across sampled frames; skip layout if it drifts |
| Circular / borderless webcams | v1 treats them as rectangular; acceptable — crop is padded |
| Render cost rises | Two crops in one graph ≈ 1.3× a single crop, not 2× — one decode pass |
| Haar backend misses profile faces | Pre-existing; unchanged by this work |

## A7. Sequencing

See **Combined Sequencing** at the end of this document.

## A8. Estimate

| Task | Effort |
|---|---|
| Facecam detection + tests | ~1 day |
| Composite render + tests | ~1 day |
| Integration, tuning on real clips | ~1 day |
| **Total** | **~3 days** |

Most of the risk is in detection tuning, not rendering — thresholds in §3.1 are
starting points and will need calibration against real gaming footage.

## A9. Open questions

1. **Panel split ratio** — 60/40 is the common convention. Fixed, or derived
   from the facecam's own aspect?
2. **Non-gaming categories** — `speaker_plus_screen` (tutorial/tech) has the
   same shape: screen share on top, presenter below. Extend after gaming proves
   out?
3. **Manual override** — should the editor let a user force or disable the split
   when detection gets it wrong? Needs a UI surface that does not exist yet.

---

# Feature B — Countdown Compilation

---

## B1. What we are building

One clip that concatenates the best N highlights from a video into a ranked
countdown, with a persistent title header and a numbered list overlay:

```
┌─────────────────────┐
│ Ranking Best Reels  │  ← persistent header band (title, all segments)
├─────────────────────┤
│  1.                 │  ← list rail; the current rank is highlighted
│  2.                 │
│  3.   [ VIDEO ]     │  ← the segment playing right now
│  4.                 │
│  5.                 │
└─────────────────────┘
```

This is a **new output artifact**, not a new framing of an existing clip: it is
produced *after* individual clips are cut, by stitching several of them
together. The existing per-clip outputs are unaffected and still produced.

## B2. What already exists

More of this is in place than for Feature A:

| Piece | Status | Location |
|---|---|---|
| Ranked highlights with scores | **exists** | `highlighter.py` — `_select_spread`, `score` per candidate |
| Per-clip rendered mp4s | **exists** | `ClipCutter` output, one per ratio |
| Concatenation | **exists** | `FFmpegService.concat_segments` (`ffmpeg_service.py:310`) |
| ASS subtitle/graphics burn | **exists** | `subtitle_styling/ass_generator.py` |
| Per-clip titles from an LLM | **exists** | `metadata_gen.py` — `generate_batch` |
| Compilation-level title | missing | needs one LLM call over the chosen clips |
| Header band + list rail overlay | missing | new ASS construction |
| Ordering / ranking policy | missing | ascending vs descending countdown |

So Feature B is mostly **composition of existing parts**, where Feature A needs
a genuinely new detection capability. That makes it the lower-risk of the two.

## B3. Design

### B3.1 Selecting and ordering segments

Take the top N clips by `score` (default `N = 5`). Two orderings, both common:

- **Countdown** (`5 → 1`): builds to the best moment, better retention.
- **Ranked** (`1 → 5`): leads with the strongest hook.

Default to **countdown** — saving the best moment for last is what the format is
for.

Each segment is capped (default 6s) so the compilation lands near 30–40s total.
The cap trims around the clip's highest-scoring window rather than simply taking
its first seconds.

### B3.2 Compilation title

One LLM call over the N chosen clips' titles and transcript excerpts, reusing
the existing text-client plumbing:

```
"Top 5 <topic> Moments"   /   "Ranking Best Reels Of <channel>"
```

Falls back to `f"Top {n} Moments"` when the call fails — the same fallback
discipline `metadata_gen.py` already uses.

### B3.3 Overlay construction

Two bands composited over the concatenated video:

**Header band.** Fixed height (~12% of frame), opaque background, compilation
title centred, present for the whole duration.

**List rail.** Left-aligned numbers `1.` to `N.` spread vertically. The entry
matching the currently playing segment is drawn in the highlight colour; the
rest are dimmed. Because segment boundaries are known timestamps, this is a
static ASS file with per-entry timing — no per-frame work.

Generated as a single ASS file and burned in one pass, reusing
`ass_generator.build_ass_file` and the existing burn path, so the compilation's
styling stays consistent with normal clips.

### B3.4 Pipeline placement

A new optional step after `clip_generation`:

```
clip_generation → [compilation] → done
```

Gated on: at least `MIN_COMPILATION_CLIPS` (3) clips rendered successfully, and
the feature enabled for the request. Runs on the `9:16` renders only.

A failure here must **not** fail the run — the individual clips are the primary
product. Log and continue, exactly as `prepare_clip_outputs` does for a single
failed ratio.

### B3.5 Storage

The compilation is a `GeneratedClip` row with a marker so the UI can tell it
apart:

- `is_compilation: bool` (new column), or
- reuse `analysis_json` with a `{"kind": "compilation"}` key — no migration.

Prefer the explicit column: queryable and self-describing. One Alembic
migration, defaulting to `false`.

## B4. Files touched

| File | Change |
|---|---|
| `video_processor/compilation.py` | **new** — segment selection, trimming, orchestration |
| `video_processor/ffmpeg_service.py` | concat hardening (see B6); no new render method needed |
| `subtitle_styling/compilation_overlay.py` | **new** — header band + list rail ASS |
| `content_intelligence/metadata_gen.py` | add `generate_compilation_title()` |
| `clip_generation/service.py` | invoke compilation after clips are rendered |
| `clip_generation/model.py` | `is_compilation` column |
| `alembic/versions/<new>.py` | **new** migration |
| `pipeline/model.py` | new `COMPILATION` step type (enum + migration) |
| `tests/test_compilation.py` | **new** |

Frontend: the compilation appears as another clip in the existing list. A badge
distinguishing it is desirable but not required for v1.

## B5. Testing

**Unit.** Segment selection (ordering, N cap, duration cap, fewer than N
available); title fallback on LLM failure; ASS timing — each list entry
highlights over exactly its segment's span.

**Integration.** Three or more real clips end-to-end: assert output duration
equals the sum of trimmed segments within tolerance, and that the file plays.

**Failure.** Compilation failure must leave individual clips intact and the
pipeline `completed`, not `error`.

## B6. Risks

| Risk | Mitigation |
|---|---|
| `concat` demuxer requires identical codec / resolution / timebase | All inputs come from our own renderer at one ratio, so they already match. Add an explicit guard rejecting mismatched inputs with a clear error rather than producing a corrupt file. |
| Audio discontinuity at joins | Short crossfade, or accept hard cuts (the format tolerates them) |
| Extra render pass raises cost | One concat plus one burn over ~35s of video; small next to per-clip cutting |
| A weak 5th clip drags quality down | Enforce a minimum score floor; emit fewer than N rather than pad |

The concat guard matters: `concat_segments` currently writes the list file and
runs with no validation that inputs share parameters. That is safe today because
callers pass same-ratio renders, but the compilation path makes it easier to get
wrong.

## B7. Estimate

| Task | Effort |
|---|---|
| Selection, trimming, concat orchestration | ~1 day |
| Header + list-rail overlay | ~1 day |
| Title generation, persistence, migration | ~0.5 day |
| Tests and tuning | ~0.5 day |
| **Total** | **~3 days** |

## B8. Open questions

1. **Who triggers it?** Automatic for every video, or opt-in per request?
   Automatic costs an extra render on every run; opt-in needs a UI control that
   does not exist yet.
2. **N** — fixed at 5, or scaled by video length?
3. **Does it consume credits?** It is an additional output; the current credit
   model charges by source duration, so it is free as things stand.
4. **Header styling** — follow the user's brand kit (`brand_kit/`), or a fixed
   compilation style?

---

# Combined Sequencing

Neither feature should be built before the render-performance work. A recent run
showed `[CUT DONE] clip=highlight_7 rendered=4/4 elapsed=394.0s` — a single 39s
clip taking 6.5 minutes across four aspect ratios. Both features add render cost
on top of that.

Recommended order:

1. **Stream-copy no-op crops.** When the crop equals the full source frame
   (observed: `crop=1920x1080 tracking_points=1` costing a 114s re-encode), use
   `-c copy`. Roughly 114s saved per clip for about a one-line change.
2. **Content-based aspect-ratio defaults.** Stop rendering all four ratios for
   every clip. Gaming maps to `9:16` only — which also gives Feature A a single
   target ratio and Feature B a single source ratio.
3. **Feature B — Countdown Compilation.** Mostly composition of existing parts
   (concat, ASS burn and ranked highlights all exist), so lower risk.
4. **Feature A — Split-Screen Gaming.** Needs new facecam detection, the hardest
   and least certain piece in either feature.

Steps 1 and 2 remove roughly 65–75% of render time, which buys the headroom both
features consume. B before A because B reuses what exists, while A introduces
new computer-vision behaviour that will need calibration against real footage.
