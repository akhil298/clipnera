---
name: retake-cutter
description: >-
  Find restarted sentences (retakes) in raw talking-head footage and cut the abandoned attempt,
  alongside the existing silence and filler cuts. Use when editing raw recordings, when a clip
  contains "so the — so the thing is", or when tightening edit_plan output.
---

# retake-cutter

Inspired by `yt-edit` + `deadair.py`.

## The idea

A transcript is enough to produce an edit list for raw speech. Three kinds of cut:

- **Dead air** – a pause longer than a floor. Cut the *middle* of it so each side keeps a short
  breath; cutting flush against words sounds breathless.
- **Filler** – segments that are only "um", "so yeah", "basically".
- **Retake** – the speaker starts a sentence, stops, and starts it again. Compare the new sentence
  with the last segment that was *real speech*, skipping fillers in between, because most retakes
  have an "um" between the two tries. Keep the second attempt.

## What Clipnera already does

`edit_plan._tighten` (word timings) already removes pauses over `JUMP_CUT_MIN_PAUSE`, keeps
`JUMP_CUT_KEEP` on each side, and drops hesitation words; `edit_engine/compiler.py` does the same
for the editor. **Dead air and filler are done.** Retakes are not.

## Build plan

1. In `edit_plan.py`, add `_retakes(words) -> list[(start, end)]`:
   - split into sentences/phrases on word timings,
   - normalise (lowercase, strip punctuation, romanise Telugu/Hindi via `transcription.language`),
   - if a phrase's first 3–5 tokens equal the next real phrase's first tokens, and the first phrase
     is shorter or unfinished, mark the first phrase for removal.
2. Feed those spans into the same cut list `_tighten` builds, so timing goes through one path and
   captions stay aligned (`hook.on_output_timeline`).
3. Same check in `edit_engine/compiler.py` so the editor shows the cut as a removable segment, not a
   hidden one.
4. Tests with synthetic word lists: plain retake, retake with filler between, false positive
   (deliberate repetition for emphasis: "never, never do this" – require ≥3 matching tokens).

## Guardrails

- Never cut deliberate repetition used for rhythm; require an unfinished first attempt.
- Report the cut as a share of *speech* time, not total time – screen demos have no words.
- Don't touch the hook teaser span.
