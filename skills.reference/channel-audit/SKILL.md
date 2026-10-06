---
name: channel-audit
description: >-
  Review a whole channel – titles as a set, thumbnails at feed size, the first seconds of recent
  uploads, posting consistency, retention – and end on ONE fix. Reference only; not planned.
---

# channel-audit

Inspired by `yt-audit`. **Not planned** as a feature; its method is reused elsewhere.

## The idea

An audit that lists twenty problems is a way to avoid the one that matters. Look in this order and
stop at the first serious problem:

1. Recent titles read **as a list** – all the same shape means a format problem, not a title one.
2. Thumbnails **shrunk to feed size** – if several are unreadable, that's the fix.
3. The **opening seconds** of recent uploads, scored (`hook-formulas`).
4. **Consistency**, not frequency – a burst then silence is worse than a steady slow pace.
5. **Retention shape**, if available (`retention-reader`).

Hand back: the one fix and what to do this week; three specific things already working (so they
aren't broken); what *not* to do yet. No empty praise.

## Reused in Clipnera

- "End on one fix" → `retention-reader` output rule.
- "Titles as a set" → a future check that a batch of clips from one video doesn't get six titles of
  the same shape (`title-pairing` batch mode).
