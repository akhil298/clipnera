---
name: upload-plan
description: >-
  Spread one long video's outputs across a realistic posting week: one anchor, one cheap follow-up,
  and Shorts cut from the anchor. Use for "plan my week", "when should I post these", or scheduling
  a batch of clips.
---

# upload-plan

Inspired by `yt-plan`.

## The idea

A plan that doesn't fit the creator's week is just a list of regrets. Ask first: how many hours do
they really have, and what's already half-made. Then shape the week:

- **One anchor** – the piece the week is about, posted on the day *their own analytics* say is
  best (ask; never assume).
- **One cheap piece** – built from what exists: a clip, a reaction, an answer to last week's top
  comment.
- **Shorts from the anchor** – cut from it, not written separately.

About three uploads a week, not seven. Empty days keep the plan survivable. End with the honest
cost in hours and what to drop first if the week goes wrong.

## Fit for Clipnera

Clipnera already makes "Shorts from the anchor" automatically, and `social/` can schedule posts.
What's missing is spacing a batch sensibly instead of posting all clips at once.

## Build plan (product decision first)

1. Owner decides: auto-spread clips, or suggest a schedule the user approves.
2. `backend/social/schedule_plan.py` – given N ready clips and best days (from analytics when
   available), return dated slots, highest-scored clip first, at most one per day per platform.
3. UI only after confirmation.

## Guardrails

- Never auto-publish without the user's approval of the schedule.
