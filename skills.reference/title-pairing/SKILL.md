---
name: title-pairing
description: >-
  Lint a clip's text surfaces together (burned-in title, teaser hook, caption first line, YouTube
  title and thumbnail text) for length, repetition, vagueness and shouting. Use when writing or
  reviewing titles, when CTR is low, or before publishing to YouTube.
---

# title-pairing

Inspired by `yt-package` + `title.py`.

## The idea

The title and the thumbnail are one unit. When they repeat each other, half of the space that
earns the click says the same thing twice. The fix is a linter that looks at them **as a pair**.

Rules, with the reason for each:

- **Length cut-offs** – YouTube search cuts near 60 characters on desktop and near 40 in the mobile
  feed. Report both: one loses the end, the other can lose the subject.
- **No shared content words** between the two surfaces. Same promise, different words.
- **Thumbnail text ≤ 3 words** – a fourth word is unreadable at feed size.
- **Concrete beats adjective** – a number, a name or a date wins over "insane/ultimate/crazy".
- **At most two ALL-CAPS words** before it reads as spam.
- **Subject in the first three words** – not "This is how the…".

## Clipnera's surfaces

| Surface | Written in | Limit today |
| --- | --- | --- |
| Burned-in title | `metadata_gen.py`, director `title` | 60 chars, about the payoff |
| Teaser hook (spoken) | director `hook` id | 5–15 words |
| Instagram first line | `social_copy.py` | ~125 chars before "more", must not repeat burned title |
| YouTube title / thumbnail | `social/providers/youtube.py` publish path | — |

`social_copy.py` already tells the model not to repeat the burned title; nothing *checks* it.

## Build plan

1. `backend/content_intelligence/packaging_lint.py` – pure function
   `lint(primary: str, secondary: str | None, limits: Limits) -> LintResult` with issues + score.
   One shared stop-word set; extend vague-word list with common Hinglish/Tenglish hype words.
2. Call it in three places: metadata title vs hook line, Instagram first line vs burned title,
   YouTube title vs thumbnail text. On a duplicate, regenerate once; otherwise keep and log.
3. Expose issues to the editor only after owner confirmation (UI rule). Start with logs/admin.
4. Tests in `backend/tests/test_packaging_lint.py` covering each rule and Telugu/Hindi romanised input.

## Guardrails

- The linter never rewrites text; the generator does.
- No invented numbers to satisfy "concrete": if the transcript has none, accept the warning.
