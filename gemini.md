# Clipnera — AI B-Roll Reel Engine
## End-to-end architecture: raw motion-graphics library + user video → auto-generated, auto-edited short

**Status:** design spec, v1
**Owner:** Akhil
**Target:** a single pipeline run that takes (a) a user's long video and (b) a multi-GB unorganized motion-graphics library, and emits a finished 9:16 reel/short whose only job is to make the channel grow.

---

## 0. Assumptions and one hard constraint

| # | Assumption | Consequence |
|---|---|---|
| A1 | The motion-graphics library is **GBs of unstructured files** on disk/S3 (mp4, mov+alpha, webm, gif, AE renders, lottie/json). No reliable filenames, no tags. | We cannot search it at request time. It **must** be indexed offline into a searchable catalog before any reel job runs. This is Subsystem 1 and it is the single highest-leverage piece. |
| A2 | Google **Flow has no public API** — it is a consumer/pro UI product. | Video generation goes through **Veo 3.x on Vertex AI** (long-running operation, async) with **Gemini 2.5 Flash Image** for keyframe conditioning. Wrapped behind a `BrollProvider` interface so Flow/Runway/Kling can be swapped in later without touching anything else. |
| A3 | Veo clips are **4–8s**, have no native sync to our VO, and are weak at rendering legible text. | Scenes are planned at **6–10s**, and text is **never** asked of the generator — it is composited from our own motion-graphics library. |
| A4 | Cost per generated second dominates total cost. | Aggressive caching, a QA gate before spending on assembly, and "reuse a library asset instead of generating" as the default whenever retrieval confidence is high. |
| A5 | The existing pipeline (`backend/pipeline/service.py::PipelineOrchestrator`) already gives us download → audio → WhisperX transcript → analysis → clips. | We extend `PipelineStepType`; we do not fork the orchestrator. |

---

## 1. System at a glance

```
                      ┌──────────────────────────────────────────────────┐
  OFFLINE / CONTINUOUS│  SUBSYSTEM 1 — MOTION LIBRARY                    │
  (runs on its own    │  crawl → dedup → probe → proxy → auto-tag →      │
   schedule, never in │  embed → catalog (Postgres + pgvector)           │
   the request path)  └───────────────────────┬──────────────────────────┘
                                              │  queryable catalog
                                              ▼
  ┌────────────┐   ┌──────────────┐   ┌───────────────┐   ┌──────────────┐
  │ S2 INGEST  │──▶│ S3 NARRATIVE │──▶│ S4 SCENE PLAN │──▶│ S5 BINDING   │
  │ video →    │   │ transcript → │   │ Claude →      │   │ per scene:   │
  │ audio →    │   │ beats, hooks,│   │ 6–10s scenes  │   │ retrieve MG  │
  │ transcript │   │ claims, arcs │   │ + master      │   │ assets +     │
  │ (existing) │   │              │   │ prompts       │   │ generate-or- │
  │            │   │              │   │               │   │ reuse call   │
  └────────────┘   └──────────────┘   └───────────────┘   └──────┬───────┘
                                                                 │
                    ┌────────────────────────────────────────────┘
                    ▼
  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
  │ S6 GENERATE  │──▶│ S7 QA GATE   │──▶│ S8 ASSEMBLY  │──▶│ S9 RENDER    │
  │ Veo + Flash  │   │ score, reject│   │ EDL: rhythm, │   │ ffmpeg graph │
  │ fan-out,     │◀──│ regenerate   │   │ transitions, │   │ + captions   │
  │ queue, cache │   │ (bounded)    │   │ overlays,mix │   │ + aspects    │
  └──────────────┘   └──────────────┘   └──────────────┘   └──────┬───────┘
                                                                  │
                                              ┌───────────────────▼──────┐
                                              │ S10 GROWTH LAYER         │
                                              │ hook variants, titles,   │
                                              │ thumbnails, A/B,         │
                                              │ analytics → rerank weights│
                                              └──────────────────────────┘
```

**Four data planes:**

- **Asset plane** — the motion library catalog. Long-lived, shared across all users and jobs.
- **Content plane** — one user video: transcript, narrative map, scene plan. Per-project.
- **Generation plane** — Veo jobs and their outputs. Content-addressed, cacheable *across* projects.
- **Assembly plane** — the EDL and the render. Fully deterministic given the first three.

The separation matters: **the first three planes are all replayable.** If a render fails you re-render. If a scene fails QA you regenerate one scene, never the reel. Nothing ever forces you to pay for generation twice.

---

## 2. SUBSYSTEM 1 — Motion Library: turning GBs of raw files into a searchable catalog

This is where "we have GBs of raw data, pick the correct one" actually lives. It runs **offline, continuously, idempotently**. A reel job never touches raw files — only the catalog.

### 2.1 Pipeline

```
crawl → identity → probe → quality gate → proxy → analyze → tag → embed → publish
```

**Step 1 — Crawl.** Walk the source roots (local dirs + S3 prefixes). For each file record `(path, size, mtime, etag)`. Skip if unchanged since the last run. Emit one `asset_ingest_job` per new/changed file. Crawl state is a cursor table, so killing the process mid-crawl loses nothing.

**Step 2 — Identity and dedup.** Compute `sha256` of the bytes → `content_hash`. If that hash already exists, register the new path as an alias and stop. Then compute a **perceptual video hash**: pHash of 8 evenly-spaced frames concatenated into a 512-bit signature. Near-duplicates (Hamming distance < 40) group into a `dup_group`; only the highest-quality member is retrievable, the rest become shadow rows. On a real scraped library this step alone typically removes 30–50% of the volume.

**Step 3 — Probe** (`ffprobe`): duration, fps, resolution, codec, pix_fmt, bitrate, **alpha channel present** (`yuva*`/`rgba`, or a `.mov` carrying ProRes 4444), audio track present. Anything unreadable → `status=rejected` with the reason logged, never retried unless the file itself changes.

**Step 4 — Quality gate.** Reject: height < 720 for full-frame roles, duration < 0.4s, fps < 20, detected watermark (from Step 6), single-colour frames. Cheap, and it stops garbage from polluting retrieval forever.

**Step 5 — Proxy generation** — the step that makes everything downstream cheap:

- `preview.mp4` — 480p h264, capped at 10s
- `sprite.webp` — 5×5 contact sheet of 25 frames
- `key_0.jpg / key_1.jpg / key_2.jpg` — frames at 10%, 50%, 90%
- `thumb.jpg` — 320px poster
- `alpha_check.png` — mid-frame composited over a checkerboard, if alpha is present

Proxies land in `s3://<bucket>/motion-library/<hash[:2]>/<content_hash>/`. **The original file is never read again after this step.**

**Step 6 — Visual analysis** (local, cheap, no LLM):

- **Motion energy** — mean optical-flow magnitude over sampled frame pairs → `motion_energy` 0–1. Separates a calm background loop from a whip transition.
- **Dominant motion vectors** — mean flow direction over the first and last 0.3s → `motion_in`, `motion_out` (unit vectors). This is what lets assembly pick a transition whose direction *continues* the outgoing shot.
- **Loopability** — SSIM(first frame, last frame) > 0.92 → `is_loopable`.
- **Palette** — k-means (k=5) over sampled frames → 5 hex colours with weights.
- **Coverage** — fraction of the frame that is non-transparent and non-black. Tells us overlay vs. full-frame background.
- **Text presence** — fast OCR (tesseract) on the 3 keyframes. Catches both usable kinetic-text assets and watermarks (text in a corner, present in every frame → watermark → reject).
- **Safe-area map** — where the asset leaves room for a subject, so overlays never cover a talking head.

**Step 7 — Semantic tagging (LLM, once per asset, forever).** Send `sprite.webp` plus the probe facts to **Gemini 2.5 Flash** (cheap, vision, high throughput) with a **closed-vocabulary** structured-output schema. Closed vocabulary is non-negotiable — free-text tags make retrieval unusable at this scale.

```jsonc
{
  "role": "transition|background_loop|overlay_fx|lower_third|callout|kinetic_text|
           icon_burst|frame_mask|particle|light_leak|glitch|data_viz|logo_sting",
  "subjects": ["money","fitness","tech","food","travel","abstract", ...],  // closed list, ~80
  "style":    ["3d","2d_flat","hand_drawn","glitch","neon","minimal","grunge","corporate","y2k","liquid"],
  "mood":     ["energetic","calm","dramatic","playful","serious","luxurious","urgent"],
  "camera":   "static|push_in|pull_out|pan|orbit|handheld|none",
  "best_use": "hook|emphasis|scene_change|background|outro|stat_reveal",
  "caption":  "one sentence describing the asset literally",
  "quality":  1-5,
  "has_watermark": true,
  "text_in_asset": "none|placeholder|baked"
}
```

`quality` and `has_watermark` from the model are cross-checked against Step 6's mechanical signals; disagreement sends the asset to a quarantine queue for a human spot-check rather than silently including it.

**Step 8 — Embeddings.** Two vectors per asset, stored in **pgvector**:

- `visual_vec` (768d) — SigLIP/CLIP image embedding of the mid keyframe (mean of all 3 if they differ substantially).
- `text_vec` (768d) — embedding of `caption + role + subjects + style + mood`.

**Step 9 — Publish.** The row flips to `status=ready`. Only `ready` rows are retrievable.

Every step above is a pure function of the file bytes, so **re-running the entire indexer is safe and nearly free** — each step short-circuits on `content_hash`.

### 2.2 Throughput

Steps 1–6 are CPU/IO bound and embarrassingly parallel: a worker pool sharded by `content_hash[:2]` (256 shards) lets you run N machines with zero coordination. Step 7 is API bound: batch ~20 assets per request behind a rate-limited queue, roughly $0.0003/asset. **100k assets ≈ $30 and one weekend.** Paid once, reused by every job forever.

### 2.3 Catalog schema

```sql
motion_assets (
  id uuid primary key,
  content_hash char(64) unique,
  dup_group_id uuid,            -- null if unique; points to the canonical row
  is_canonical bool,
  source_uri text, aliases jsonb,
  -- probe
  duration_s float, fps float, width int, height int, aspect text,
  has_alpha bool, has_audio bool, codec text,
  -- analysis
  motion_energy float, motion_in vector(2), motion_out vector(2),
  is_loopable bool, palette jsonb, coverage float, safe_area jsonb,
  phash bit(512),
  -- semantics
  role text, subjects text[], style text[], mood text[],
  camera text, best_use text, caption text, quality smallint,
  text_in_asset text, has_watermark bool,
  -- vectors
  visual_vec vector(768), text_vec vector(768),
  -- ops
  license text, status text, proxy_prefix text,
  usage_count int default 0, win_rate float,   -- fed by Subsystem 10
  created_at timestamptz, updated_at timestamptz
);

CREATE INDEX ON motion_assets USING hnsw (text_vec   vector_cosine_ops);
CREATE INDEX ON motion_assets USING hnsw (visual_vec vector_cosine_ops);
CREATE INDEX ON motion_assets USING gin  (subjects);
CREATE INDEX ON motion_assets (role, status, has_alpha, duration_s);
```

---

## 3. SUBSYSTEM 2 — Ingest (mostly existing)

Reuses the current `PipelineOrchestrator` steps: `DOWNLOAD → AUDIO_EXTRACTION → AI_NOISE_CANCELLATION → TRANSCRIPTION`.

Output contract into the new work:

```jsonc
{
  "video_path": "...",
  "duration_s": 3612.4,
  "segments": [
    {"start": 0.0, "end": 4.2, "text": "...", "speaker": "SPK_0",
     "words": [{"w": "the", "s": 0.10, "e": 0.22, "conf": 0.98}, ...]}
  ]
}
```

Word timings are load-bearing — assembly snaps every cut to a word boundary using the existing `content_intelligence/word_snapper.py`.

---

## 4. SUBSYSTEM 3 — Narrative understanding

Before asking for scenes we build a compact structured view of the source. Long videos don't fit in one request, which is exactly what `content_intelligence/transcript_windows.py` was built for — reuse it, don't re-solve it.

**Map** (per window, Groq/Haiku-class, parallel): extract `claims`, `stories`, `numbers/stats`, `emotional_peaks`, `quotable_lines`, each with timestamps.

**Reduce** (Claude Sonnet 5, one call): merge into a **Narrative Map**:

```jsonc
{
  "topic": "...", "category": "fitness",
  "audience": "...", "tone": "...",
  "candidate_hooks": [
    {"t": 412.0, "line": "...", "why": "contrarian claim", "strength": 0.91}
  ],
  "arcs": [
    {"start": 410.0, "end": 468.0, "thesis": "...", "payoff": "...", "completeness": 0.86}
  ],
  "key_visual_needs": ["barbell", "macro plate", "calendar countdown"],
  "brand_palette_hint": ["#0B1F3A", "#F2A900"]
}
```

`arcs` are the candidate reels. The existing `highlighter.py` + `scorer.py` rank them; we take the top K and **one arc becomes one reel**. This is the join point between the old pipeline and the new one.

---

## 5. SUBSYSTEM 4 — Scene Planner (Claude)

**Model:** `claude-opus-5` for planning — this is the creative bottleneck, don't cheap out here. `claude-sonnet-5` for the high-volume variant and re-rank passes.

**Input:** one arc's transcript slice with word timings, the Narrative Map, the user's brand kit, and — critically — **the retrieval vocabulary** (the closed tag lists from §2.1 Step 7). Feeding the planner the exact vocabulary the catalog uses is the trick that makes binding actually hit: the planner asks for things that exist.

**Output:** strict JSON, schema-validated, retry-on-invalid.

```jsonc
{
  "reel": {
    "target_duration_s": 42,
    "aspect": "9:16",
    "hook_strategy": "contrarian_claim",
    "thesis": "...",
    "pacing_curve": "fast_hook_then_settle"
  },
  "scenes": [
    {
      "id": "s1",
      "order": 1,
      "role": "hook",                                  // hook|setup|evidence|turn|payoff|cta
      "source_span": {"start": 412.30, "end": 420.10}, // word-snapped
      "vo_text": "Most people fail at this because...",
      "duration_s": 7.8,
      "visual_intent": "one sentence: what the viewer must SEE",
      "master_prompt": "<the Veo prompt — see §7.2>",
      "negative_prompt": "text, watermark, logos, distorted hands, subtitles",
      "keyframe_prompt": "<Gemini Flash Image prompt for the conditioning frame>",
      "camera": "slow push_in",
      "palette": ["#0B1F3A", "#F2A900"],
      "continuity": {"from": null, "to": "s2", "match_on": "color+motion_left"},
      "asset_query": {                                 // what binding searches the catalog for
        "role": "background_loop",
        "subjects": ["fitness", "abstract"],
        "style": ["3d", "neon"],
        "mood": ["energetic"],
        "needs_alpha": false,
        "min_duration_s": 7.8
      },
      "overlay_query": {                               // separate, alpha, composited on top
        "role": "kinetic_text",
        "text": "90% FAIL HERE",
        "needs_alpha": true
      },
      "generate": "auto",                              // auto|always|never
      "priority": 1                                    // regeneration budget order
    }
  ],
  "b_roll_budget": {"max_generated_scenes": 5, "max_cost_usd": 2.50}
}
```

**Hard rules, stated in the prompt and re-checked in code:**

- Every scene is 6.0–10.0s; the sum lands within ±10% of `target_duration_s`.
- `source_span` must sit on word boundaries and must not overlap another scene.
- `master_prompt` never requests legible text, logos, or a real person's likeness.
- The hook is scene 1 and must be visually resolvable in under 1.5s.
- Scenes marked `generate: "never"` are pure library composites (free).

**Validation layer** (`broll/planner.py`): schema check → temporal check (no overlap, in-bounds, word-snapped) → duration check → content-policy check. Up to 2 repair round-trips with the specific violations fed back to the model, then hard-fail the job with a legible reason. Failing *here* is cheap; failing after generation is not.

---

## 6. SUBSYSTEM 5 — Asset Binding (retrieval)

For each scene, resolve `asset_query` and `overlay_query` against the catalog. This stage decides **generate vs. reuse**, which decides the cost of the entire job.

**Stage 1 — Hard filter (SQL).**
`status='ready' AND is_canonical AND role = ? AND duration_s >= scene.duration_s * 0.9 AND has_alpha = ? AND license IN (allowed) AND NOT has_watermark AND quality >= 3`, plus aspect compatibility — a 16:9 background is usable for 9:16 only if `coverage` and `safe_area` survive the crop.

**Stage 2 — Hybrid recall (→ top 200).** Three independent retrievers:

- **Lexical** — BM25 over `caption || subjects || style || mood`.
- **Dense (text)** — cosine kNN on `text_vec` against the embedding of `visual_intent`.
- **Dense (visual)** — cosine kNN on `visual_vec` against the embedding of the **generated keyframe**, when one exists. This is why keyframes are produced before final selection.

Fuse with **Reciprocal Rank Fusion** (k=60). RRF beats score-normalisation here because the three scorers live on incomparable scales.

**Stage 3 — Feature re-rank (200 → 20).** Linear model over: RRF score; palette distance to `scene.palette` (CIEDE2000); motion-energy match to the scene's slot in the pacing curve; alignment of this asset's `motion_in` with the previous scene's `motion_out`; `win_rate` from Subsystem 10; and a **recency-diversity penalty** so the same asset isn't reused within the reel or across the user's last 5 reels.

**Stage 4 — LLM re-rank (20 → 3).** One Claude Sonnet call per scene, given the 20 captions plus thumbnails: return 3 ranked picks with a one-line reason each. Cheap, and it catches the semantic misses embeddings make ("barbell" vs "barbershop").

**Stage 5 — Global MMR pass.** Maximal Marginal Relevance across all scenes' top-3 lists, so the final selection is varied reel-wide rather than six near-identical neon loops.

**Stage 6 — Generate-or-reuse decision.**

```
if scene.generate == "never":         → reuse top-1
elif scene.generate == "always":      → generate
elif top1_confidence >= 0.78:         → reuse top-1            (free, instant)
elif top1_confidence >= 0.55:         → reuse AND generate; QA picks the winner
else:                                 → generate
```

`top1_confidence` is the calibrated re-rank score. **This threshold is the cost dial** — raise it for margin, lower it for quality.

**Overlays (kinetic text, lower thirds, transitions) are always library assets, never generated.** Veo cannot render text reliably, and this is precisely what a GB-scale motion-graphics library is *good* at. The generator handles the cinematic background; the library handles everything with an edge, a mask, or a letter in it.

---

## 7. SUBSYSTEM 6 — B-roll generation

### 7.1 Two-step generation

**Step A — Keyframe (Gemini 2.5 Flash Image).** One still from `keyframe_prompt`, conditioned on the brand palette. Fast (~3s), ~$0.04, and it buys three things at once: a cheap preview to show the user before spending on video, a conditioning image that sharply improves Veo's prompt adherence, and a `visual_vec` that feeds Stage-2 retrieval refinement.

**Step B — Video (Veo 3.x on Vertex AI, image-to-video).** `master_prompt` + keyframe + `negative_prompt` + duration + 9:16. A long-running operation: submit → poll → fetch.

### 7.2 Master prompt compiler (`broll/prompt_compiler.py`)

Claude writes the creative core; code deterministically assembles the final string, so every prompt has the same structural quality floor:

```
[SHOT]      medium shot, {camera}
[SUBJECT]   {subject from visual_intent}
[ACTION]    {what changes across the {duration}s}
[SETTING]   {environment}
[LIGHT]     {lighting}, {mood}
[PALETTE]   dominated by {palette hex → colour names}
[LENS]      {35mm|85mm|anamorphic}, shallow depth of field
[GRADE]     cinematic, filmic contrast, subtle grain
[MOTION]    continuous single take, no cuts
[NEGATIVE]  text, letters, captions, watermarks, logos, deformed hands,
            extra fingers, morphing faces, flicker, jump cuts
```

Deterministic assembly also makes the prompt hashable:

```
gen_cache_key = sha256(provider, model, prompt, keyframe_hash, duration, aspect, seed)
```

Identical scenes across projects hit the cache and cost $0. At scale on a single niche, this is a meaningful fraction of requests.

### 7.3 Orchestration

- **Queue** — durable job table plus a worker pool. Scene generations fan out with `asyncio.gather` bounded by a semaphore (default 4) behind a **global token-bucket rate limiter** shared across tenants.
- **Cost guard** — the plan's `max_cost_usd` is checked before every submit. Exceeding it degrades gracefully: remaining scenes fall back to library assets rather than failing the reel.
- **Retries** — exponential backoff on 429/5xx. On a content-policy rejection, exactly **one** automatic prompt-softening pass (strip the flagged element, resubmit), then library fallback.
- **Idempotency** — every generation keyed by `gen_cache_key`, so a crashed worker resubmitting produces a cache hit, not a double charge.
- **Timeout** — per-scene wall clock, default 6 minutes. Timed-out scenes fall back to the library; the reel always ships.

```python
class BrollProvider(Protocol):
    async def keyframe(self, req: KeyframeRequest) -> KeyframeResult: ...
    async def generate(self, req: VideoRequest) -> VideoJobHandle: ...
    async def poll(self, handle: VideoJobHandle) -> VideoJobStatus: ...
    async def fetch(self, handle: VideoJobHandle) -> LocalClip: ...

# implementations: VertexVeoProvider (default), GeminiFlashImageProvider, FlowProvider (stub)
```

---

## 8. SUBSYSTEM 7 — QA gate

Nothing enters assembly unscored. Every generated clip gets:

| Check | Method | Fail action |
|---|---|---|
| **Prompt adherence** | CLIP cosine(mean of 5 sampled frames, `master_prompt`) ≥ τ (τ ≈ 0.24, calibrated) | regenerate with a tightened prompt |
| **Aesthetic** | LAION aesthetic predictor on 3 frames, ≥ 5.0 | regenerate |
| **Liveness** | frame-diff variance > ε — catches frozen/static output | regenerate |
| **Black / blank** | mean luma within [8, 247] | regenerate |
| **Unwanted text** | OCR finds text when none was requested | regenerate |
| **Face / hand artifacts** | face-landmark confidence variance spike | regenerate |
| **Flicker** | temporal luma stddev across consecutive frames | reject → library fallback |
| **Continuity** | palette ΔE and `motion_out → motion_in` against neighbours | reorder, or insert a transition |

**Bounded regeneration:** at most 2 regen attempts per scene and at most N total per reel (default 4), spent in `priority` order — the hook gets fixed before scene 5 does. Once the budget is gone, the scene falls back to its top library asset. **The reel always renders.**

**Final holistic pass.** Once the EDL exists, one Claude call sees the storyboard (contact sheet of all scenes + the VO text) and returns `{verdict, scene_fixes[]}`. Only the named scenes are touched. This is the check that catches "technically fine, but scene 3 visually contradicts what the voiceover is saying."

---

## 9. SUBSYSTEM 8 — Assembly intelligence (the EDL builder)

This is the "combine them using AI intelligence" step. Its output is an **Edit Decision List** — a pure data structure. Rendering is then a dumb, deterministic function of it, which makes the whole thing debuggable, diffable, and directly editable from the frontend timeline.

**9.1 Rhythm grid.** Beat-track the music bed (`librosa.beat.beat_track`) → beat timestamps. Compute the speech-energy envelope from the VO. Candidate cut points = (word boundaries from `word_snapper.py`) ∩ (beats ± 80ms) ∩ (VO pauses > 120ms). Cuts landing on beats *and* on speech is what makes an edit feel intentional instead of mechanical.

**9.2 Pacing curve.** Target shot length as a function of position in the reel:

- **0–3s (hook)** — 0.7–1.2s cuts, highest motion-energy assets, hardest transitions
- **3s → 60%** — 1.8–2.6s, settle, let the claims land
- **60% → 90%** — tighten back to 1.2–1.8s approaching the payoff
- **last 10%** — one held shot plus the CTA overlay

Scene clips are **sub-cut** to hit this: an 8s Veo clip becomes three 1.4s punches with speed ramps, not one long boring shot. This is the single biggest retention lever in the whole system.

**9.3 Transition selection.** At each junction, query the catalog for `role='transition'`, `duration ≤ 0.5s`, ranked by how well the transition's `motion_in` aligns with the outgoing shot's `motion_out` and its `motion_out` with the incoming shot's entry. Whip-pan out → whip transition → whip-pan in. Low-energy junctions get a match-cut or a 4-frame dissolve instead of an effect — not every cut deserves a graphic.

**9.4 Overlay layer.** Per scene: a kinetic-text asset (alpha) carrying the scene's key phrase, positioned inside `safe_area` so it never covers the speaker; stat-reveal graphics bound to `numbers` from the Narrative Map; brand lower-third on scene 1; a progress bar; an end card.

**9.5 Audio bed.** Original VO normalised to −16 LUFS, plus a music bed sidechain-ducked −9dB under speech, plus SFX (whoosh/impact from the library) on each transition, beat-aligned. Final master at −14 LUFS, true peak −1 dBTP.

**9.6 The EDL.**

```jsonc
{
  "reel_id": "...", "aspect": "9:16", "fps": 30, "duration_s": 42.0,
  "tracks": {
    "video": [
      {"t": 0.0, "dur": 1.1, "src": {"kind": "generated", "clip_id": "g_s1"},
       "in": 0.4, "speed": 1.0,
       "transform": {"scale": 1.06, "pan": [0, -0.02]}, "grade": "lut_warm_02"},
      {"t": 1.1, "dur": 0.35, "src": {"kind": "asset", "asset_id": "a_whip_14"},
       "blend": "screen"}
    ],
    "overlay": [
      {"t": 0.2, "dur": 2.4, "src": {"kind": "asset", "asset_id": "a_kt_07"},
       "text": "90% FAIL HERE", "anchor": "lower_third"}
    ],
    "captions": [{"t": 0.0, "dur": 42.0, "style_id": "...", "mode": "depth"}],
    "audio": [
      {"t": 0.0, "src": {"kind": "vo"}, "gain_db": 0},
      {"t": 0.0, "src": {"kind": "music", "asset_id": "m_12"}, "duck": true}
    ]
  }
}
```

The EDL is persisted and versioned. The frontend timeline reads and writes it. "Regenerate scene 3" mutates one entry and re-renders.

---

## 10. SUBSYSTEM 9 — Render

`assembly/renderer.py` compiles the EDL into a single ffmpeg filter graph, extending the existing `video_processor/ffmpeg_service.py`:

1. Decode, trim, and speed-ramp each video entry
2. Scale/crop to the target aspect using the entry's transform — reuse `content_intelligence/crop_strategy.py` and `reframing.py` for any shots sourced from the original video
3. Apply the per-shot LUT for grade continuity
4. `overlay` the alpha assets in z-order
5. Burn captions via the existing `subtitle_styling` / `depth_captions` modules
6. `amix` + `sidechaincompress` for the audio bed
7. Encode: h264 high, CRF 18, yuv420p, `+faststart`, 30fps

**Multi-aspect:** render the 9:16 master, then derive 1:1 and 16:9 by re-running the graph with different crop transforms — the EDL already carries per-shot safe areas. The poster frame is extracted at the highest-saliency frame for `poster_url`.

Outputs land in the existing `GeneratedClip` table, with new columns for `edl_json` and `reel_kind`.

---

## 11. SUBSYSTEM 10 — Growth layer

The stated goal is channel growth, so the pipeline has to close the loop rather than just emit a file.

- **Hook variants.** Render 3 alternative first-3-second openings from the same EDL (different scene-1 asset, different kinetic text). Ship them as A/B candidates.
- **Metadata.** Extend `content_intelligence/metadata_gen.py`: 3 title variants, description, 15 hashtags, per-platform caption, and a best-post-time drawn from the user's own analytics.
- **Thumbnail.** Highest-saliency frame plus a generated text overlay, 3 variants.
- **Predicted retention curve.** A model over hook strength, cut density, motion energy per second, caption coverage, and payoff position. Surfaced in the UI as a curve with the weak second flagged, so the user can fix it before publishing.
- **Feedback loop.** `analytics/` ingests real platform performance per published reel and attributes it back to `motion_assets.win_rate`, the re-rank model's weights, and `ClipScorer`'s weights.

**Every reel published makes the next retrieval better.** That is the actual moat here — the library is just files until it has win-rate data attached to it.

---

## 12. Data model additions

```sql
-- asset plane
motion_assets       -- see §2.3
asset_ingest_jobs   (content_hash, stage, status, error, attempts, updated_at)
asset_usage         (asset_id, reel_id, scene_id, published, views, retention_3s, created_at)

-- content plane
narrative_maps      (project_id, map_json, model, created_at)
reel_plans          (id, project_id, arc_id, plan_json, status, model, cost_usd)
reel_scenes         (id, reel_plan_id, "order", role, source_start, source_end,
                     duration_s, master_prompt, negative_prompt, keyframe_prompt,
                     asset_query jsonb, generate_mode, status)

-- generation plane
generated_broll     (id, scene_id, gen_cache_key unique, provider, model,
                     keyframe_s3, video_s3, duration_s, cost_usd,
                     qa_scores jsonb, qa_verdict, attempt, status)

-- assembly plane
reel_edls           (id, reel_plan_id, edl_json, version, created_at)
reel_renders        (id, edl_id, aspect, s3_key, poster_url, duration_s, status, ffmpeg_log)
```

New `PipelineStepType` values: `NARRATIVE_MAP`, `SCENE_PLANNING`, `ASSET_BINDING`, `BROLL_GENERATION`, `BROLL_QA`, `EDL_ASSEMBLY`, `REEL_RENDER`. Add them via an Alembic migration that extends the `pipeline_step_type` enum — follow the pattern already in `20260911000000_fix_missing_pipeline_step_enum_values.py`.

---

## 13. Module layout

```
backend/
  motion_library/          # SUBSYSTEM 1 — offline, its own worker process
    crawler.py  prober.py  dedup.py  proxy.py  visual_features.py
    tagger.py   embedder.py  index.py  retriever.py
    model.py  repository.py  schema.py  route.py  worker.py
  broll/                   # SUBSYSTEMS 4, 5, 6, 7
    planner.py             # Claude scene plan + validation/repair loop
    prompt_compiler.py     # deterministic master-prompt assembly
    binder.py              # retrieval + generate-or-reuse decision
    generator.py           # queue, cache, cost guard, fan-out
    providers/
      base.py  vertex_veo.py  gemini_image.py  flow.py
    qa.py                  # per-clip gates + holistic storyboard pass
    model.py  repository.py  schema.py
  assembly/                # SUBSYSTEMS 8, 9
    rhythm.py  transitions.py  overlays.py  audio_mix.py
    edl.py     renderer.py    schema.py
  content_intelligence/
    narrative.py           # NEW — map/reduce built on transcript_windows.py
  pipeline/
    service.py             # extended: new steps wired into step_order
```

Conventions match what's already in the repo: `service.py` orchestrates, `repository.py` owns SQL, `schema.py` holds Pydantic models, `route.py` exposes FastAPI, `model.py` holds SQLAlchemy.

---

## 14. API surface

```
POST  /motion-library/ingest      {source_uri}            → job_id      (admin)
GET   /motion-library/stats                               → counts by role/status
POST  /motion-library/search      {query, filters}        → assets      (debug/UI)

POST  /reels/plan                 {project_id, arc_id}    → reel_plan
GET   /reels/{id}/plan                                    → scenes + keyframe previews
PATCH /reels/{id}/scenes/{sid}    {master_prompt?, asset_id?, duration_s?}
POST  /reels/{id}/generate        {scene_ids?}            → starts Subsystem 6
GET   /reels/{id}/edl                                     → EDL
PATCH /reels/{id}/edl                                     → user timeline edits
POST  /reels/{id}/render          {aspects[]}             → render jobs
GET   /reels/{id}/status                                  → per-stage progress
WS    /ws/reels/{id}                                      → live progress events
```

Progress reuses the existing `ProgressCallback` signature, so the frontend's current progress UI keeps working unchanged.

---

## 15. Failure handling, idempotency, resume

Every stage is keyed and cached, so the pipeline is **resumable at any point** — matching the `resume=True` behaviour already in `PipelineOrchestrator`.

| Stage | Cache key | On failure |
|---|---|---|
| Ingest | `content_hash` | per-file; one bad file never blocks the crawl |
| Narrative | `project_id + transcript_hash` | retry with smaller windows |
| Plan | `arc_id + model + prompt_version` | 2 repair loops, then hard fail with a legible reason |
| Binding | `scene_id + catalog_version` | if nothing passes the filters → force `generate` |
| Generation | `gen_cache_key` | retry → soften prompt → library fallback |
| QA | `generated_broll.id` | bounded regeneration → library fallback |
| EDL | `reel_plan_id + version` | deterministic; always recomputable |
| Render | `edl_id + aspect` | re-render only; never re-generate |

**Governing principle: no failure past the planner may abort the reel.** Every downstream failure degrades to a library asset. The user gets either a finished reel or a clear pre-generation error — never a half-finished job that burned $4.

---

## 16. Cost and latency budget (one 45s reel, 6 scenes, 4 generated)

| Stage | Latency | Cost |
|---|---|---|
| Transcript (existing) | 60–180s | ~$0.02 |
| Narrative map | 15–40s | ~$0.05 |
| Scene plan (Opus 5) | 20–35s | ~$0.12 |
| Binding (retrieval + rerank) | 3–8s | ~$0.01 |
| Keyframes ×4 | ~10s (parallel) | ~$0.16 |
| Veo ×4 @ 8s | 90–240s (parallel) | **~$1.60–3.20** |
| QA | 10–20s | ~$0.03 |
| EDL | <2s | $0 |
| Render ×3 aspects | 40–90s | compute only |
| **Total** | **≈ 5–10 min** | **≈ $2.00–3.60** |

Veo is ~85% of the cost. The two levers that matter: raising the reuse-confidence threshold in §6 Stage 6 (each avoided generation saves roughly $0.50), and `gen_cache_key` hits across users working in the same niche.

---

## 17. Build order

| Phase | Deliverable | Why in this position |
|---|---|---|
| **P0** | `motion_library` steps 1–6 (crawl → proxy → features), no LLM tagging yet | Nothing works until the GBs are addressable. Pure infra, testable offline, zero API cost. |
| **P1** | Tagging + embeddings + `retriever.py`, plus a debug search UI | Prove retrieval quality by hand before anything depends on it. If search is bad, everything above it is bad. |
| **P2** | `narrative.py` + `planner.py`, surfaced as a storyboard in the UI — **no generation** | Validates the creative core cheaply. Iterate the planner prompt here, not against $3 Veo calls. |
| **P3** | Library-only reels: binder + EDL + renderer, `generate: "never"` everywhere | A complete, shippable, near-zero-cost product. A large share of reels will be good enough on library assets alone. |
| **P4** | `generator.py` + Veo provider + QA gate | Add generation on top of a working editor, so you can A/B generated vs. library and prove it earns its cost. |
| **P5** | Growth layer + analytics feedback into `win_rate` and rerank weights | The compounding advantage. Requires published-reel data, so it has to come last. |

**P3 is the milestone that matters: a fully working product with zero generation cost.** Generation then becomes a quality upgrade you can price, not a dependency you can't ship without.

---

## 18. Open decisions

1. **Vector store** — pgvector (simplest, you already run Postgres) vs. Qdrant (better past ~5M vectors). Recommend pgvector until the catalog exceeds ~2M assets.
2. **Veo access** — Vertex AI requires a GCP project with Veo quota, and that quota is not instant. Start the request now; it is the longest-lead-time item in the plan.
3. **Music licensing** — the library needs a cleared music-bed pool tracked in `motion_assets.license`. Blocking for commercial launch.
4. **Embedding model** — self-hosted SigLIP-so400m (free, needs a GPU) vs. a hosted embedding API (simpler, but per-asset cost is non-trivial at 100k+ assets).
5. **Human-in-the-loop** — does the user approve the scene plan before generation spends money? Recommend yes by default, with a "full auto" toggle for power users.
