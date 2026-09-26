# OpusClip-Quality Enhancement Plan

## Research Summary

### Recordly (AGPL-3.0, Electron desktop recorder+editor)
- **Phrase-aware segmentation**: Splits transcripts on sentence boundaries + silence detection
  - Min clip cap: 500ms, phrase gap: 1500ms, pad: 80ms
- **Whisper+parser pipeline**: Transcription → parsing → silence analysis → segment generation

### Flick (MIT, Creatorberry)
- **Scene planning**: transcript → scene-plan → scene-spec.json → Remotion components
- **Sound effects**: Bundled SFX per scene category, NO background music
- **Reframing**: Face-tracked auto-crop

### OpenShorts (MIT, OpenShot-style)
- **Window building**: Scoring windows aligned to Whisper segments (window ~90s, overlap ~30s)
- **Word-snapping**: Snap clip boundaries to word timestamps + lead/trail silence (max_lead 0.35s, max_tail 0.45s)
- **Clip count targeting**: Floor grows with material (3 windows → 3, 10+ → 6), ceiling up to 12
- **Score-based trimming**: Rank by predicted_score, keep earliest in ties

### SupoClip (AGPL-3.0, OpusClip clone)
- **Virality scoring**: hook_score, engagement_score, value_score, shareability_score (0-25 each, summed → 0-100)
- **Caption templates**: karaoke animation styles (default, hormozi, mrbeast, minimal, tiktok, neon, podcast)
  - Fields: word_pop, emoji, emphasis_color, word_box, glow, max_words_per_line, uppercase, position_y
- **Emoji annotations**: Curated keyword→emoji map + POWER_WORDS set, rate-limited (max 8/clip, min 3-word gap, 8-word repeat gap)
- **Hook titles**: AI-written 3-9 word titles burned into top safe area (~4s, translucent pill box)
- **SSE progress + email notifications**
- **Credit billing**: credit_minutes per plan, CREDIT_COST_PER_2_MINUTES=4

### ClipForge (Qt+Remotion desktop)
- **ASS karaoke captions**: Word-by-word highlighting via ASS Dialogue events
- **Font scaling**: em-size → ASS Fontsize via winSpan/unitsPerEm ratio (~1.75)
- **Caption layout**: Word grouping by display width, line breaking, safe-area margins

## Clipnera Current State

| Feature | Status | Gap |
|---------|--------|-----|
| Credit billing | Present in subscription/service.py, integrated in pipeline/route.py | None — credit deduction + refund on failure already working |
| Transcription resume | Present (chunk-level CheckpointManager) | None |
| Pipeline progress (SSE) | Present (pipeline/route.py SSE stream) | Needs email/SMS completion notification |
| Pipeline resume from failure | Route has /resume endpoint but re-runs whole pipeline | Need skip-completed-steps + checkpoint artifacts |
| Subtitle styling | SRT+force_style via FFmpeg SUBTITLES filter | No ASS karaoke, no word-level highlighting, no templates |
| Virality scoring | Basic (scorer.py: engagement_factor, signals, reasons) | No multi-dimensional (hook/engagement/value/shareability), no word-snapping |
| Emoji captions | suggested_emoji in metadata_gen | No contextual emoji injection into captions |
| Hook titles | Basic drawtext overlay | No translucent pill background, no proper top safe-area styling |
| Sound effects | None | No SFX injection |

## Implementation Priority

### P1 — Output Quality (do first)
1. **ASS karaoke caption generation** — `subtitle_styling/ass_generator.py`
   - Word-level karaoke highlight via ASS Dialogue events
   - Font scaling: em → ASS Fontsize (winSpan/unitsPerEm ratio)
   - Caption layout: word grouping, line breaking, safe-area margins
   - Hook title pill (translucent box at top)

2. **Phrase-aware caption segmentation** — `subtitle_styling/phrase_segmenter.py`
   - Split on sentence boundaries + silence detection
   - Configurable min duration, max gap, padding

3. **Caption templates** — `subtitle_styling/templates.py`
   - default, hormozi, mrbeast, minimal, tiktok, neon, podcast
   - Animation types: karaoke, pop, fade, bounce

4. **Word-snapping for clip boundaries** — `content_intelligence/word_snapper.py`
   - Snap start/end to nearest word timestamp + lead/trail silence

### P2 — Scoring & Embellishments
5. **Advanced virality scoring** — extend `content_intelligence/scorer.py`
   - hook_score, engagement_score, value_score, shareability_score

6. **Emoji annotation** — `subtitle_styling/emoji_annotator.py`
   - Keyword→emoji map, POWER_WORDS, rate-limited placement

### P3 — Pipeline Reliability
7. **Resume-from-failure** — extend `pipeline/service.py`
   - Skip completed steps, restore artifacts from checkpoint
   - Use existing step_artifacts field in PipelineState

8. **Completion notifications** — extend `notifications/service.py`
   - Email on pipeline complete/fail
   - Integrate with pipeline route

### P4 — Polish
9. **Sound effects injection** — `clip_generation/sfx.py`
   - SFX library, contextual matching, inject during FFmpeg render
10. **Hook title enhancement** — integrate into ASS generator

## File Changes Summary

New files:
- `backend/subtitle_styling/ass_generator.py` — ASS caption generation with karaoke
- `backend/subtitle_styling/phrase_segmenter.py` — Phrase-aware segmentation
- `backend/subtitle_styling/templates.py` — Caption templates (ported from supoclip)
- `backend/subtitle_styling/emoji_annotator.py` — Emoji keyword annotation
- `backend/content_intelligence/word_snapper.py` — Word-boundary snapping for clips

Modified files:
- `backend/subtitle_styling/service.py` — Add ASS generation, integrate templates
- `backend/subtitle_styling/model.py` — Extend SubtitleStyleType enum
- `backend/content_intelligence/scorer.py` — Add multi-dimensional virality scoring
- `backend/content_intelligence/highlighter.py` — Add word-snapping
- `backend/pipeline/service.py` — Add resume-from-failure capability
- `backend/pipeline/route.py` — Wire resume to skip completed steps
- `backend/clip_generation/service.py` — Integrate SFX, hook titles into burn-in
- `backend/notifications/service.py` — Add pipeline completion notification
- `backend/core/config.py` — Add new config settings

Tests:
- `backend/tests/test_ass_generator.py`
- `backend/tests/test_phrase_segmenter.py`
- `backend/tests/test_caption_templates.py`
- `backend/tests/test_emoji_annotator.py`
- `backend/tests/test_word_snapper.py`
- `backend/tests/test_virality_scoring.py`
- `backend/tests/test_pipeline_resume.py`
