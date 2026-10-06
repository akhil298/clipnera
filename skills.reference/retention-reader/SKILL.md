---
name: retention-reader
description: >-
  Read a published video's audience-retention curve, find where viewers left and what was said
  there, and name the single biggest fix. Use for "why do people stop watching", a retention CSV,
  or when feeding real performance back into clip selection.
---

# retention-reader

Inspired by `yt-retention` + `retention.py`.

## The idea

The retention curve is the most honest feedback a platform gives. Read it as three separate
problems, because each has a different fix:

- **Opening leak** – share of viewers lost at the start (first 30 s long-form; first ~3 s for a
  Short). Fix the opening line, never the edit.
- **Cliffs** – single steep drops at a moment. Line them up with the transcript to see *what was
  being said* when people left; that's what makes the report usable.
- **Slide** – steady loss through the middle. That's pacing; the fix is cutting, not rewriting.

Hand back **one** fix. If the opening is healthy and the slide is flat, the clip is fine and the
problem is packaging → send to `title-pairing`.

## Fit for Clipnera

This closes the loop: we publish clips (YouTube + Instagram connections exist in `social/`), so we
could learn which hook formulas and clip shapes hold viewers *for this creator*.

## Build plan (later)

1. Decide on scope: YouTube Analytics API needs the `yt-analytics.readonly` OAuth scope added to
   the YouTube connection (owner decision; re-consent required). Instagram Insights gives far less.
2. `backend/analytics/retention.py` – pure analysis on `(position, pct_watching)` points:
   opening leak, top cliffs, slide rate. Align cliffs to the clip's output-timeline captions
   (`hook.on_output_timeline`).
3. Store per published clip; aggregate by `hook_formula` (from `hook-formulas`) and clip format.
4. Feed aggregates into the director as a per-creator prior, only after enough data (e.g. ≥20 clips).

## Guardrails

- Never fetch analytics without the scope the user granted.
- Never show a cause as fact: "people left while you said X" is an observation, not a diagnosis.
