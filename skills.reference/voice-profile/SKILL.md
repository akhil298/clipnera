---
name: voice-profile
description: >-
  Keep one per-creator voice profile (audience, how they talk, banned words, own phrases, claims
  they won't make, format) and make every text generator read it. Use when writing any copy in a
  creator's name or when setting up a new creator.
---

# voice-profile

Inspired by the pack's `templates/voice.md`, which every skill there reads first.

## The idea

Copy in the wrong voice is worse than none, because the creator has to stand behind it. One short
profile fixes that for every generator at once:

- **Who they talk to** – one specific person, not "creators".
- **How they actually talk** – taken from their real transcripts, not how they wish they sounded.
- **Words they never use** and **words that are theirs**.
- **Claims they won't make** – numbers, results or tools they can't back up. Generators refuse
  these automatically.
- **Format** – language mix, swearing, emoji use, on camera or not.

If no profile exists, build a draft from three of the creator's own videos and let them edit it.

## Fit for Clipnera

Brand Kit (`backend/brand_kit/`) already stores per-creator look; voice is its missing half.
Readers: `metadata_gen.py` (titles), `social_copy.py` (captions), `creator_intro/copy.py`,
`publish-seo`, and the director's title field.

## Build plan

1. Add voice fields to the Brand Kit model + Alembic migration; Pydantic schema in
   `brand_kit/schema.py`, matching TS type in `frontend/lib/types.ts`.
2. Auto-draft: after a creator's first three processed videos, summarise transcripts into a draft
   profile (cheap model), marked "draft" until they confirm.
3. One helper `voice_block(brand_kit) -> str` appended to every copy prompt (DRY).
4. Banned words and "won't claim" become a post-generation check; a hit triggers one regeneration.
5. Brand Kit UI section – owner confirmation required before UI work.

## Guardrails

- Profile text is the creator's data; never share across workspaces.
- Language rule from `director.LANGUAGE_RULE` still wins over profile phrasing.
