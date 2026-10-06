---
name: outlier-research
description: >-
  Rank videos by how far each beat its own channel's median views, then name the title formula
  each used. Use for "what's working", a creator's own top performers, or format research.
---

# outlier-research

Inspired by `yt-viral` + `swipe.py`.

## The idea

Raw view counts measure channel size, not ideas. Rank by **views ÷ that channel's median views**
instead. A 400k video on a channel that normally gets 30k is worth studying; the same number on a
huge channel is an ordinary day. A median from fewer than four videos is noise, so skip those
channels and say so. Label each outlier with the hook formula its *title* matches – a statement
about the words, not a claim about why it worked.

Read public listings only. Never log in as the user or use their credentials for research.

## Fit for Clipnera

- **Good fit:** the creator's *own* published clips. Once `retention-reader` stores stats, "your
  clips that beat your median, and the formula they share" is a strong, honest insight.
- **Weak fit for now:** researching other channels. It adds scraping risk and the product has no
  place for it yet.

## Build plan (only after retention-reader)

1. `backend/analytics/outliers.py` – `rank(videos) -> list[Outlier]` with the ≥4-videos rule.
2. Classify titles with the `hook-formulas` catalogue.
3. Surface in Analytics as one sentence + top 3, after owner confirms the UI.

## Guardrails

- No scraping of logged-in pages; no use of `youtube_cookies.txt` for research.
- Present formula labels as labels, never as causes.
