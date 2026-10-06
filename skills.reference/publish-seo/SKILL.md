---
name: publish-seo
description: >-
  Write the YouTube description and tags for a published clip, aimed at the queries a real person
  types, and check the title carries those queries. Use when publishing to YouTube, when a video
  isn't being found in search, or when editing description/tag generation.
---

# publish-seo

Inspired by `yt-seo`.

## The idea

- **Only the first two lines of a description matter** – they show above "more" and are the search
  snippet. Say what the viewer gets, in the words they'd search.
- Links or resources next, so they stay above the fold. Then chapters (long-form only). Then detail.
- **Tags are a weak signal.** Use them for spellings, tool names and abbreviations people really
  type. About 15 at most. Stuffing unrelated tags breaks YouTube's rules.
- **The query test:** write the three searches this video should win, then check that the title and
  the first two description lines contain those words. If they don't, fix the title, not the
  description.
- Search matters for evergreen content. For feed-driven Shorts, effort belongs in packaging
  (`title-pairing`), and the skill should say so.

## Where it plugs in

- `backend/content_intelligence/social_copy.py` – Instagram playbook already follows the same
  spirit (searchable caption, ≤5 specific hashtags, no generic tags). Reuse its structure.
- `backend/social/providers/youtube.py` / `social/publisher.py` – the YouTube publish payload.

## Build plan

1. Add a `YOUTUBE_PLAYBOOK` beside the Instagram one in `social_copy.py`; produce
   `{youtube_title, description, tags, queries}` per clip in the same batched call.
2. Run the query test in code: every query's content words must appear in title + first 2 lines;
   on failure regenerate once.
3. Generic-tag blocklist shared with `GENERIC_TAGS`; cap tags at 15.
4. Schema: add the fields to `social/schema.py` and the matching TS type in `frontend/lib/types.ts`
   in the same change (API contract rule). Response stays `{data, message, error}`.

## Guardrails

- Same language rule as `director.LANGUAGE_RULE` (Tenglish for Telugu, never Telugu script).
- No claims, numbers or links that aren't in the clip or the creator's Brand Kit.
