---
name: chapters
description: >-
  Build YouTube chapters from a transcript and validate them against YouTube's rendering rules.
  Use for long-form exports, "add timestamps", or when the director needs section boundaries.
---

# chapters

Inspired by `yt-chapters` + `chapters.py`.

## The idea

YouTube only turns a timestamp list into chapters if it follows three rules; otherwise the block
just sits in the description:

- first entry at **0:00**,
- **three or more** entries,
- each chapter **≥ 10 seconds**.

Finding boundaries: score every pause between segments by (a) how long the pause is and (b) how much
the vocabulary changes across it (compare content words in a window before vs. after). Take the
highest-scoring pauses that respect the 10 s spacing. The words found are a draft; every title is
then rewritten as a 3–5 word promise. If a section can't be named in five words, it's two
sections or it's filler – a useful editing signal on its own.

## Fit for Clipnera

- Shorts don't have chapters, so this is **only** for long-form outputs (story/recap exports,
  B-Roll Studio long videos) and for YouTube descriptions in `publish-seo`.
- The boundary scorer is also a cheap pre-pass for `director.py`'s map step on very long videos:
  section edges are natural places to split `_windows`.

## Build plan

1. `backend/content_intelligence/sections.py` – `find_sections(sentences, target) -> list[Section]`
   using the existing `Sentence` objects (timings already there; no SRT parsing needed).
2. `validate_chapters(sections) -> list[str]` returning rule violations.
3. Titles: one small LLM call to rename drafts in the speaker's language; validator runs after.
4. Wire into `publish-seo` only when the output is longer than 60 s.

## Guardrails

- Never paste an invalid list; return the violation instead.
