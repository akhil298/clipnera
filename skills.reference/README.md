# skills.reference

Skill plans for Clipnera, written after studying the open-source
[youtube-agent-skill](https://github.com/Jakeschincariol/youtube-agent-skill) pack (MIT, 11 skills
plus 6 small Python tools). Nothing here is copied. Each folder restates the *idea* behind one of
those skills, judges whether it fits Clipnera, and plans how we would build it on top of the modules
we already have.

## What the source pack is

It is built for a solo YouTuber working in a chat with Claude. Every skill writes text (a script, a
title, a cut list) and the creator applies it by hand. Three ideas run through all of it, and they
are the parts worth taking:

1. **Measure instead of eyeballing.** Hooks, titles, chapters and cut lists are checked by small
   deterministic scorers, not by asking the model "is this good?".
2. **One answer, not twenty.** Each skill ends on the single most important fix or the top few
   options with their scores.
3. **Never invent numbers.** If a figure isn't in the source, the line is written without it.

Clipnera is different in one important way: we *render and publish*. So the plans below turn chat
advice into checks inside the pipeline (director → edit plan → metadata → social publisher).

## Verdict per skill

| Plan folder | Source skill | Fit | Why |
| --- | --- | --- | --- |
| [hook-formulas/](hook-formulas/SKILL.md) | yt-script | **High** | Our teaser hook and burned-in title are picked by the model with no score. A formula catalogue and a hook scorer give them a measurable bar. |
| [shorts-finder/](shorts-finder/SKILL.md) | yt-shorts | **High** | This is Clipnera's core job. The director already does most of it; three gaps (rewritten first line, on-screen text, loop point) are worth closing. |
| [title-pairing/](title-pairing/SKILL.md) | yt-package | **High** | Burned-in title, caption first line and YouTube title should never repeat each other. A cheap linter catches it before render. |
| [retake-cutter/](retake-cutter/SKILL.md) | yt-edit | **High** | We already cut silence and filler. We do not detect restarted sentences (retakes), which is the main thing left in raw talking-head footage. |
| [publish-seo/](publish-seo/SKILL.md) | yt-seo | **Medium** | We write Instagram copy well; the YouTube publish path needs its own description/tags rules and a "query test". |
| [chapters/](chapters/SKILL.md) | yt-chapters | **Medium** | Useful for long-form exports and for the director's map pass (section boundaries). Not needed for Shorts themselves. |
| [retention-reader/](retention-reader/SKILL.md) | yt-retention | **Medium (later)** | Closing the loop from published clip → where viewers left → better future picks. Needs the YouTube Analytics scope. |
| [outlier-research/](outlier-research/SKILL.md) | yt-viral | **Low–Medium** | "Views ÷ the channel's own median" is a great ranking idea for the creator's *own* back catalogue. Researching other channels is out of scope for now. |
| [upload-plan/](upload-plan/SKILL.md) | yt-plan | **Low–Medium** | One long video → one anchor + N shorts spread over a week fits our scheduler, but it's a product feature, not an engine gap. |
| [voice-profile/](voice-profile/SKILL.md) | templates/voice.md | **Medium** | Every text generator should read one creator voice file. Brand Kit is the natural home. |
| [motion-graphics/](motion-graphics/SKILL.md) | — (Clipnera's own) | **Superseded** | Owner chose `backend/motion/` (ASS, white cards + amber, Montserrat/Anton, Pro-only). The Chrome spike is kept for reference only. |
| [comment-replies/](comment-replies/SKILL.md) | yt-comment | **Not now** | Outside Clipnera's product. Kept for reference. |
| [channel-audit/](channel-audit/SKILL.md) | yt-audit | **Not now** | A consulting feature. Kept for reference; its "ONE fix" rule is reused in retention-reader. |

## Suggested build order

```
 1. hook-formulas   ──►  2. title-pairing  ──►  3. shorts-finder gaps
        │                       │
        └── scorer reused by ───┘
 4. retake-cutter   (independent; edit_plan.py)
 5. voice-profile   (Brand Kit field, read by 1–3 and publish-seo)
 6. publish-seo     ──►  7. chapters (long-form only)
 8. retention-reader ──► feeds director scoring (needs OAuth scope)
 9. outlier-research / upload-plan   (product decisions first)
```

Steps 1–4 need no new API keys, no migrations and no UI changes; they tighten what already ships.

## How to use these files

Each `SKILL.md` has Claude-skill frontmatter so it can later be moved into `.claude/skills/` as-is,
but for now they are **plans**: what the skill does, how it works, where it plugs into the code,
what already exists, what to build, and the guardrails. Implementing one means following its
"Build plan" section and adding tests in `backend/tests/`.
