---
name: hook-formulas
description: >-
  Name and score the opening line of a clip (teaser hook, burned-in title, caption first line)
  against a catalogue of hook shapes before rendering. Use when choosing or rewriting a hook,
  when a clip's opening feels flat, or when tuning the director's hook pick.
---

# hook-formulas

Inspired by `yt-script` (21 hook formulas + `hookscore.py`). Rewritten for short clips.

## The idea

A hook is judged in the first one to three seconds on a Short. It has to do three things at once:
match what the viewer was promised (title or thumbnail), open a question they can't close yet, and
make it believable that the answer is coming. A line that only summarises the clip does the third
job and leaks.

Two tools make that measurable instead of a matter of taste:

1. **A catalogue of hook shapes**, each with how it works, a failure mode, and regex cues that
   recognise it in transcribed speech.
2. **A scorer** that rates a line on a few independent properties and reports the weakest one,
   because one dead property sinks a line that is otherwise strong.

## Our catalogue (own wording, grouped)

| Family | Shapes | What it needs to work |
| --- | --- | --- |
| Numbers | statistic, counted list, deadline/date | A real figure from the transcript, never made up |
| Proof | someone's result, receipt (show it first), before/after, I-tried-it | The result or artefact must appear on screen or in the clip |
| Tension | the mistake, the warning, contrarian flip, the impossible claim | The clip has to resolve it before it ends |
| Promise | the reveal, the clock, the superlative, the comparison | The payoff lands inside the clip, early |
| Address | direct question, naming the viewer, insider info, origin story | Has to be the viewer's question, not the speaker's |

For Indian-language clips the cues must also match Hinglish/Tenglish phrasing ("mistake chesthe",
"sabse bada", numbers spoken in words). Matching is on the romanised transcript.

## Our scorer (design)

Five properties, each 0–100, from the line's text alone:

- **Concrete** – numbers, names, dates up; hype adjectives and filler down.
- **Viewer** – "you/your" (and `meeru/aap/tum` equivalents), extra weight early in the line.
- **Stakes** – words about losing, cost, failing, stopping.
- **Open loop** – question words, "but/until/nobody"; penalised if the line answers itself ("because…").
- **Length** – a band that can be spoken in ~3 s for Shorts (roughly 5–15 words), not 9–24 as for long-form.

Verdict = mostly the mean, partly the minimum (weakest-link). Bands: strong / workable / weak.
It's a heuristic: a low score means look again, a high score is not a promise. Say so in the UI.

## Where it plugs in

- `backend/content_intelligence/director.py` – `CLIP_FIELD_RULES` asks for a hook id; the model's
  pick is unscored. Score the chosen hook sentence and its two nearest alternatives; keep the best.
- `backend/clip_generation/hook.py` – `locate_hook` timing logic stays as is; the scorer only
  chooses *which* line.
- `backend/content_intelligence/metadata_gen.py` – score generated titles the same way.
- `motion_assets/EDITING_REFERENCE.md` – link the catalogue so editing passes use the same names.

## Build plan

1. `backend/content_intelligence/hooks/catalogue.py` – the shapes as typed data (id, family,
   needs, cues per language). No JSON file: keep it in Python next to its user.
2. `backend/content_intelligence/hooks/score.py` – pure functions, no I/O, `score(text, lang) -> HookScore`.
3. In the director's plan step, re-rank hook candidates by score; store `hook_formula` and
   `hook_score` on the clip plan (debug/admin view only at first; no schema change to public API).
4. Tests: a fixture of real strong/weak hooks from `Validations/` transcripts; assert ordering, not
   exact numbers.

## Guardrails

- Never change the hook *timing* rules in `hook.py` (1.5–6 s, not the opening line).
- Never let the score fabricate: it ranks lines that exist, it does not write new ones.
- Calibrate on our own clips before showing scores to users.
