# Hype edit engine — to-do

Working list for the focus-aware layout + motion graphics + SFX work.
`[x]` = built **and** verified (tests pass + rendered frames checked).

Test footage (local only, never shipped): `TRuX-Tn91uQ` (Speed + Jamal fan-art stream, 1080p60).

## A. Focus-aware layout (fixes the fan-art screenshots)
- [x] A1 Region map (`video_processor/regions.py`)
  - [x] A1.1 Candidate content rectangles per shot (straight-edge pairs + corners + colour steps; grain-robust)
  - [x] A1.2 Side panels (chat, member list) rejected by shape; overlays never chosen since content is cropped tight
  - [x] A1.3 Face roles: person cam vs depicted face; depicted faces dropped before speaker tracking
  - [x] A1.4 Unit tests (tests/test_focus_layout.py) + stream (6 moments) and podcast (6 moments, 0 false hits)
- [x] A2 Focus decision (`video_processor/focus.py`)
  - [x] A2.1 Rules: content / content_reaction / people, with evidence (hint, category, pointing words, pop-up)
  - [ ] A2.2 Vision tie-break — DEFERRED: rules gave 0 false hits on stream + podcast; a vision call can only choose among boxes CV already found, so it cannot fix the misses (faint pencil art)
  - [x] A2.3 Unit tests
- [x] A3 Layout from focus (`editing.choose_layout`)
  - [x] A3.1 Content focus checked first; a content shot is one stretch
  - [x] A3.2 Content cell = content box, fitted whole over its own blur; audience cell frames the group
  - [x] A3.3 Round webcam bubble when one face would need >3x upscale; content raised so the bubble sits under it (corner when it cannot)
  - [x] A3.4 DECIDED: kept. Without a detected picture, whole-screen-on-top is the clutter the owner rejected
  - [x] A3.5 Director prompt: screen_with_speaker covers reactions
  - [x] A3.6 Tests + rendered 2 fan-art clips (3:48, 22:20), frames checked

## B. Moments (`motion/moments.py`)
- [x] B1 Rule moments: loud reactions without speech (from source loudness)
- [x] B2 AI moments (lists, numbers, names, CTAs, mood) — one batched call, category + (LOUD) markers in the prompt
- [x] B3 Evidence: every shown word in its word range, digits exact (incl. "ten thousand" = 10,000), abbreviations (pcs, hrs)
- [x] B4 Tests (tests/test_motion.py) + real AI on 6 podcast windows: 2 figures found, both verified against the words

## C. Motion graphics (`motion/graphics.py`, ASS in the caption pass)
- [x] C1 One look (white cards, amber, Montserrat ExtraBold / Anton), slide-up entrance, fade exit
- [x] C2 Templates: list_card (ticks + typing + icons), big_number (count-up), entity_tag, cta_card (glow), reaction_sticker
- [x] C3 Gates: evidence, value, icon only from spoken words, tone (mood), place (clear of faces/content/title, else dropped or shrunk), time (reading time), budget (1 per 6 s, no overlaps)
- [x] C4 Tests + rendered review on stream (crowded: cards correctly dropped) and podcast (cards on chest, clear of face)

## D. Sound + library
- [x] D1 Curated SFX from library -> static/motion/sfx (10 sounds, manifest with peak times); game/meme rips excluded
- [x] D2 One sound per visual event, peak on frame (measured: clicks at 12.33/13.53/14.73 s exactly), under the voice (-16 dBFS peaks)
- [x] D3 DECIDED: library film burns / light leaks stay in the hook bridge only (existing). Dropping them on every cut is the "random graphics" the owner ruled out
- [x] D4 Tests

## E. Planner + pipeline wiring
- [x] E1 Planner (`motion/planner.py`): priority cta > list > number > name > reaction
- [x] E2 Plan stored on clip (`analysis_json.motion`), planned after clip generation for Pro (`pipeline/service.py`)
- [x] E3 Burned in the caption pass (all three paths: template captions, SRT, uncaptioned); captions step aside under cards; never fails an export
- [x] E4 Hook: existing teaser + bridge kept; title card now moves off shown content (unless the user set its position)
- [x] E5 End-to-end runs: podcast 0:10-0:40 (real AI -> 50% figure, count-up, cash sound) and fan-art 3:48 (content layout, title moved, no forced graphics)

## F. Verification
- [x] F1 Full suite: 1568 passed (1 known order-dependent flake, passes alone)
- [x] F2 Rendered clips reviewed frame by frame; sound timing measured
- [ ] F3 Owner review of the rendered samples

## Known limits
- Mood is judged from words + loud bursts. A constantly loud streamer has no bursts, so mock-anger reads as "serious" and gets no stickers (safe: nothing wrong is added).
- Faint drawings with no visible border (pencil on grey) are not detected as content; framing falls back to people.

## Notes
- Full suite: `test_plans::test_pro_user_passes_the_gate[hook-transitions resolve]` fails only in the full run (passes alone) — order-dependent, not from this work.
- Another session (clipnera-new-a9) is growing SFX under static/motion/sfx/synth and spiked Chrome templates; agreed `motion/plan.py` Cue is the shared contract. Owner decided 2026-10-06: white-card look (this engine) and Pro-only motion graphics.

## Later (not in this pass)
- Time effects (speed ramp, echo slow-mo) — change clip timing, need caption re-sync
- Editor UI to swap/remove graphics (needs frontend types)
