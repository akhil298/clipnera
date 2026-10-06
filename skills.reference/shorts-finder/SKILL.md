---
name: shorts-finder
description: >-
  Pick the moments in a long video that survive as standalone Shorts, and prepare each one with a
  new opening line, on-screen text and a loop point. Use when tuning clip selection, reviewing why
  a clip needs outside context, or adding per-clip packaging.
---

# shorts-finder

Inspired by `yt-shorts`. This is Clipnera's core job, so this plan is about gaps, not a rebuild.

## The idea

The best moment of a video is not automatically a good Short. A good Short is a moment that still
makes sense **with the rest of the video removed**. Three tests, all required:

1. **Starts clean** – the first sentence doesn't lean on anything said before it.
2. **Has a turn** – a claim followed by something that complicates or proves it.
3. **Ends on a line** – a finished sentence that lands, not a trail-off.

Then each Short gets its own packaging, because the long video's wording assumes context:

- a **rewritten first line** (text overlay or teaser) aimed at a stranger,
- **on-screen text for the first two seconds** that says something different from the spoken words,
- a **loop point**: the last line sets up the first, so a replay feels intentional,
- a **framing note**: what a 9:16 crop loses from the 16:9 source and whether it matters.

## What Clipnera already does

- `director.py` `MAP_SYSTEM` and `DIRECTOR_SYSTEM` already demand complete thoughts, setup + payoff
  inside the clip, and ending after the payoff. That covers tests 1–3.
- `edit_plan.py` `_thought_start` / `_ends_mid_thought` / `_thought_end` enforce clean edges.
- `clip_generation/hook.py` plays a teaser line first.
- Layout and framing are chosen per clip (formats/, video_processor/).

## Gaps worth closing

| Gap | Today | Plan |
| --- | --- | --- |
| Ranking shown to the user | clips listed by score | Show top candidates with first line + timecode so a reject takes one glance |
| Opening overlay ≠ spoken words | burned title may echo the hook | Run `title-pairing` overlap check between title and hook text |
| Loop point | not considered | Add `loop` (0–10) to the director's `RUBRIC`; prompt: "does the ending set up the opening?" |
| Framing loss | layout picked, loss not reported | When the speaker or screen content falls outside the crop, flag for a split/screen layout |

## Build plan

1. Add `loop` to `RUBRIC` in `director.py` and to `_rubric` in `edit_plan.py`; weight it low at first.
2. After metadata generation, call the title-pairing overlap check (see `title-pairing/`) for
   title vs. hook line; if they share content words, regenerate the title once.
3. Score each clip's hook with `hook-formulas` and store it with the clip plan.
4. Frontend: no change until scores are calibrated; then a small "why this clip" line in the clip
   card (needs owner confirmation per UI rules).

## Guardrails

- Clip length rules stay where they are (`edit_plan._fit_length`).
- Never stitch a "turn" from another part of the video into a single-moment clip; that is what
  story clips are for.
