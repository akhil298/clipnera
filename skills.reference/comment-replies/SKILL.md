---
name: comment-replies
description: >-
  Sort a comment section into questions, corrections, praise and bait, then draft short replies in
  the creator's voice and pick the one comment to pin. Reference only; not planned for Clipnera.
---

# comment-replies

Inspired by `yt-comment`. **Not planned** – Clipnera makes and publishes clips; it doesn't manage
communities. Kept so the idea isn't lost.

## The idea

- Sort first and report the counts: **questions** (answer; repeated ones are next video ideas),
  **corrections** (if right, say so plainly), **praise** (reply to a few with something specific),
  **bait** (don't reply, ever).
- Replies under ~30 words, answer in the first sentence, one real question back at most, no emoji
  unless the creator uses them, never promise a video they haven't agreed to.
- Pin the comment holding the question most people share, not the nicest one.

## If it ever gets built

The one piece that fits Clipnera is "repeated questions → clip ideas": map recurring questions to
moments in the creator's back catalogue that already answer them, and suggest those as clips.
That would read comments through the existing YouTube connection (needs `youtube.force-ssl` scope)
and reuse `voice-profile`. Never auto-post replies.
