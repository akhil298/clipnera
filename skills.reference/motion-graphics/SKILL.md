---
name: motion-graphics
description: >-
  Add template-based motion graphics (counters, lower thirds, keyword slams, callouts, progress
  bars) to an edit: the director picks a template and fills its fields, Chrome renders it as a
  transparent clip, FFmpeg lays it over the footage. Use when planning or building motion layers,
  adding a template, or tuning where graphics appear.
---

# motion-graphics

> **Superseded (2026-10-06).** The owner chose one engine and one look for motion graphics:
> `backend/motion/` (ASS, burned in the caption pass), with white cards, amber accents,
> Montserrat ExtraBold / Anton, Pro-only. The shared contract is `backend/motion/plan.py`
> (`Cue` / `MotionPlan`); placement and face avoidance live in `backend/motion/graphics.py`.
> The Chrome spike below (dark panel, Syne) is not to be grown as a second look. Any new
> template matches the chosen look and consumes `Cue`. Kept for its render timings and lessons.

Clipnera's own plan. It is not taken from the YouTube pack. The model **chooses** graphics; it
never draws them.

## The idea

```
director (LLM) ──► motions: [{template, at, dur, slot, fields}]       ~3k tokens in, ~3k out
                       │
                 validator (code) ── numbers exist in transcript? face clear? density OK?
                       │
                 render.mjs motion  ── template(t, fields, brand) → transparent .mov per graphic
                       │                (cached by hash; only the graphic's own seconds)
                 render.py ── picture → motions overlay → captions/texts on top → master
```

- **A template** is a pure function of time: given `t`, its fields and the brand colours, it draws
  one frame. That is how `branding/motion/source/kit.js` already works. Because of this, any frame
  can be rendered on its own, frames can be rendered in parallel, and the same input always gives
  the same output.
- **Only the graphic's own seconds are rendered**, not the whole video. Five 2.5 s graphics at 30
  fps make about 375 frames, not the 1,200 frames of a full 40 s video.
- **Cache key** = hash(template id, fields, size, brand). Re-renders after chat edits that don't
  touch a graphic reuse its clip.

## What exists today

| Piece | Where | State |
|---|---|---|
| Time-driven canvas kit | `branding/motion/source/kit.js` | Brand pieces only (intros, watermarks, end cards) |
| Chrome → video renderer | `branding/motion/source/render.mjs` | Alpha output only for `.mov`; driven by its own `catalog.json` |
| Text layers | `edit_engine/schema.py` `EditText` (`hook`, `pop`, `line`) | Burned as ASS in `render.py` `texts_ass` |
| Text cards | `EditPicture(kind="card")` | Full-frame still card replacing footage |
| Overlays / transitions / emoji | `motion_assets/` + `catalog.json` | `motion_graphic` kind has count 0 |
| `backend/motion_library/` | — | Only stale `__pycache__`, no tracked source. Nothing in `backend/` reads `motion_assets/catalog.json` |
| Face boxes per shot | `edit_engine/perception.py` | Available for keep-clear zones |

## Template catalogue (v1: 16 templates)

Every template has: id, family, when to use, typed fields, default duration, allowed slots, and
a max-characters limit for each text field.

| Family | Template | Use when the speaker… | Fields |
|---|---|---|---|
| Numbers | `count-up` | says a number that matters | `value`, `prefix`, `suffix`, `label` |
| Numbers | `stat-bar` | compares a share or percentage | `percent`, `label` |
| Numbers | `versus-bars` | compares two named things | `a_label`, `a_value`, `b_label`, `b_value` |
| Numbers | `money-tick` | mentions a price or amount | `amount`, `currency` |
| Text | `keyword-slam` | lands the single key word of a line | `word` |
| Text | `lower-third` | introduces a person, brand or tool | `name`, `role` |
| Text | `quote-card` | delivers the punchline line | `quote` (≤ 90 chars) |
| Text | `list-step` | goes through a counted list | `index`, `total`, `label` |
| Pointers | `callout-arrow` | refers to something on screen | `label`, `target` (x, y) |
| Pointers | `circle-mark` | "look at this" on a screen recording | `target`, `radius` |
| Pointers | `spotlight` | narrows to one area of a screen | `target`, `radius` |
| Structure | `progress-bar` | runs a multi-step tutorial | `steps`, `current` |
| Structure | `chapter-tag` | starts a new section in a story clip | `label` |
| Structure | `split-label` | uses before/after or split layout | `left`, `right` |
| Accent | `swipe-underline` | stresses a phrase in the caption | (follows caption word) |
| Accent | `burst` | hits a reveal or punchline | `color` (brand default) |

Not motion graphics, keep as they are: zoom punches and crops (FFmpeg, `EditPicture.zoom`),
flash transitions and light overlays (`motion_assets/`), emoji (ASS vector layers).

**Slots** are fixed safe areas, not free x/y: `top`, `center`, `lower-third`, `beside-face`,
`screen-target`. The validator turns a slot into pixels using the face boxes, so a graphic never
covers the speaker's face or the caption band.

## Timeline contract

New Pydantic model in `edit_engine/schema.py`, with the matching TypeScript type in
`frontend/lib/types.ts` in the same change (API contract rule):

```python
class EditMotion(BaseModel):
    template: str            # id from the motion catalogue
    at: float                # seconds on the output timeline
    dur: float
    slot: Literal["top", "center", "lower-third", "beside-face", "screen-target"]
    fields: dict[str, str | float]
```

`EditTimelineResponse` gains `motions: list[EditMotion] = []`. Older timelines without the field
still load. Check how the timeline is stored before deciding on a migration: a JSON column needs
none, typed columns need an Alembic revision.

Each template's fields are validated by its own small Pydantic model in a registry, so the director
cannot send a field the template doesn't have.

## Director rules (prompt section)

- Use a graphic only to **show what the words already say**: a spoken number → `count-up`; a list →
  `list-step`; a person named → `lower-third`. If no line calls for one, use none.
- **Never invent a value.** Every number or name in `fields` must appear in the transcript words
  inside `[at - 2 s, at + dur]`. The validator enforces this.
- Start on the word that says it (word timings), hold 1.5–3 s.
- At most one graphic on screen at a time; at most one every ~6 s; none in the first 1.5 s (the hook
  owns it) and none over a text card.
- Pick from the catalogue by id only; unknown ids are dropped, never guessed.

The catalogue goes into the prompt in a short form (id, use-when, fields): about 1–1.5k tokens.

## Validator (code, after the plan)

`edit_engine/motion.py`:

1. Drop unknown templates; validate fields against the registry.
2. Number and name check against the transcript window; drop on a miss and log it.
3. Resolve slots to pixels using `perception` face boxes and the caption band; move to another
   allowed slot or drop.
4. Enforce density and overlap rules; keep the higher-scoring graphic.
5. Clamp to the timeline and to the clip's cuts (a graphic never spans a jump cut by default).

## Rendering

1. **Templates** live in `branding/motion/source/templates/<id>.js`, written in the same style as
   `kit.js` (`draw(ctx, t, fields, brand, W, H)`), reusing its easing and drawing helpers.
2. **`render.mjs motion --spec specs.json --out dir/`** – a new mode: one Chrome session, every
   graphic in the spec, each to a transparent `.mov` sized to its slot box (not full frame), so files
   stay small.
3. **`render.py`** – after the picture segments and before `texts_ass`, add one `overlay` filter per
   graphic with `enable='between(t,at,at+dur)'` and the slot's x/y. Captions and texts stay the top
   layer.
4. **Brand** – colours and fonts come from Brand Kit; with no kit, use the locked amber/neutral
   palette.
5. **Cache** in the work dir keyed by the spec hash; the edit job copies hits instead of rendering
   them again.

## Cost

- **Model:** about +3k input and +3k output tokens per edit. With the current Sonnet director this
  is about +$0.05; with Gemini 3.8 Flash about +$0.015. The credit price in
  `edit_engine/pricing.py` probably holds, but that is the owner's call.
- **Compute:** about 375 frames of Chrome rendering for five graphics, plus one more FFmpeg overlay
  pass. Measure this on the EC2 box during Phase 1 before turning it on for Free.

## Build phases

1. **Spike, no wiring.** Four templates (`count-up`, `lower-third`, `keyword-slam`,
   `callout-arrow`), the `render.mjs motion` mode, and a script that overlays them on a
   `Validations/` clip. Measure render seconds per graphic.
2. **Contract + compiler.** `EditMotion`, TS type, registry, validator, `render.py` overlay pass,
   tests (`backend/tests/test_edit_motion.py`) for validation rules and filter strings.
3. **Director.** Prompt section and fields in the plan schema; behind a feature flag
   (`feature_flags/`), admin-only first.
4. **Editor UI.** A motion track in the timeline; select, move, retime, edit text, delete. Copilot
   chat ops (`add_motion`, `remove_motion`) through StudioDoc `commit()`. **Needs owner
   confirmation before any UI change.**
5. **Fill the catalogue** to 16, add `motion_graphic` entries to `motion_assets/catalog.json`, and
   compare against the OpusClip benchmark renders.

## Phase 1 results (2026-10-05)

Built: `branding/motion/source/templates.js` (4 templates), `motion.html` (harness),
`render.mjs motion --spec --out` (one PNG-in-MOV per spec + `manifest.json`).

Tested on `Validations/Think for Yourself…` (47 s, 1080×1920, 25 fps), with each graphic placed on
a line actually spoken (transcribed with faster-whisper `small`):

| Graphic | Spoken line | Box | Frames | Render |
|---|---|---|---|---|
| count-up "10 MIN" | "for 10 minutes" @ 7.44 s | 900×420 | 84 | 0.39 s |
| lower-third "Gratitude vs. Instagram" | "versus I use my Instagram" @ 11.56 s | 1000×260 | 90 | 0.53 s |
| callout-arrow "Exposing the brain" | "expose their brain" @ 23.72 s | 1080×1100 | 84 | 0.75 s |
| keyword-slam "YOURSELF" | "think for yourself" @ 36.68 s | 1000×400 | 57 | 0.44 s |

- **Chrome render:** ~2.1 s for all 315 frames, ~3.1 s including Chrome start, on the M-series dev
  Mac. Measure again on EC2.
- **FFmpeg composite** of 4 overlays + x264 re-encode of the 47 s clip: ~4.7 s wall.
- **PNG-in-MOV files** are 2–5 MB each: fine as job temp files, not for storage.
- **Lessons:**
  - Size text for the largest scale an animation reaches, not the resting one.
  - Nothing may draw past its box; the edge clips it into stray shapes.
  - Text over a wiping slab needs a clip, not a colour switch.
  - `catalog.fps` (30) is used even for 25 fps sources. FFmpeg resamples by timestamp, so this
    works; Phase 2 should pass the source fps in the spec.
- **Slots used** (until the validator computes them from face boxes): face in the top half,
  captions at ~80% height, so graphics go in the chest band y ≈ 1020–1450.

## Open decisions for the owner

1. Plans: motion graphics on all plans, or Pro only?
2. Credits: same price, or +N credits when graphics are used?
3. Auto by default, or a toggle per edit?
4. Brand Kit: allow per-creator template colours or fonts in v1, or the palette only?
5. Delete the stale `backend/motion_library/__pycache__`, or restore that module from history?

## Guardrails

- The model picks and fills; code validates; the renderer draws. No model-written animation code.
- No graphic may show a number, name or claim that isn't spoken in the clip.
- Never cover the face or the captions; captions always render last.
- Templates use only fonts and assets whose licence allows commercial use (same rule as
  `catalog.json`).
