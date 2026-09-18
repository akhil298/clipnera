# Clipnera — AI B-Roll Reel Engine
## End-to-end architecture: raw motion-graphics library + user video → auto-generated, auto-edited short

**Status:** design spec, v2 (free-stack constraint)
**Owner:** Akhil
**Target:** a single pipeline run that takes (a) a user's long video and (b) a multi-GB unorganized motion-graphics library, and emits a finished 9:16 reel/short whose only job is to make the channel grow.

**Cost policy (v2):** the **only** paid services in this system are **Claude** and **Gemini 2.5 Flash** (text + image). Everything else — every model, every library, every data source — is free, open-source, or self-hosted. `groq` is dropped from `requirements.txt`.

---

## 0. Assumptions and constraints

| # | Assumption | Consequence |
|---|---|---|
| A1 | The motion-graphics library is **GBs of unstructured files** (mp4, mov+alpha, webm, gif, AE renders). No reliable filenames, no tags. | We cannot search it at request time. It **must** be indexed offline into a searchable catalog first. This is Subsystem 1 and it is the highest-leverage piece in the system. |
| A2 | **No paid video-generation API.** Veo/Flow, Runway, Kling, Luma are all out. There is no free production-grade text-to-video API. | "Generate B-roll" becomes **source + synthesize** — a four-tier ladder (§7): your library → your own footage → free stock APIs → Gemini Flash Image stills animated into 2.5D motion locally. A self-hosted open-weights video model is an optional Tier 4, off by default. |
| A3 | Paid budget is **Claude + Gemini 2.5 Flash only**. | Claude does narrative reasoning, scene planning, and re-ranking. Gemini Flash does bulk vision tagging and still-image generation. Every other model (CLIP, depth, aesthetic, OCR, optical flow, beat tracking, ASR) runs locally on free weights. |
| A4 | "Free" means **no per-call API cost**. Self-hosted models still cost compute. | The default path is **CPU-only** and genuinely zero-marginal-cost. Anything needing a GPU is explicitly marked optional. Nothing in the default path requires a GPU. |
| A5 | Model **licenses** matter as much as price — "free to download" ≠ "free to use commercially". | Every self-hosted model in §19 is pinned to a commercially-usable license, with the non-commercial variant named so nobody grabs the wrong checkpoint. |
| A6 | The existing pipeline (`backend/pipeline/service.py::PipelineOrchestrator`) already does download → audio → WhisperX transcript → analysis → clips. | We extend `PipelineStepType`; we don't fork the orchestrator. WhisperX, librosa, opencv, scipy are already in `requirements.txt` and already free. |

---

## 1. System at a glance

```
                      ┌──────────────────────────────────────────────────┐
  OFFLINE / CONTINUOUS│  SUBSYSTEM 1 — UNIFIED VISUAL CATALOG            │
  (own schedule, never│  your motion library  +  free stock mirrors      │
   in the request path)│  crawl → dedup → probe → proxy → features →     │
                      │  tag (Gemini Flash) → embed (CLIP) → pgvector    │
                      └───────────────────────┬──────────────────────────┘
                                              │  one queryable catalog
                                              ▼
  ┌────────────┐   ┌──────────────┐   ┌───────────────┐   ┌──────────────┐
  │ S2 INGEST  │──▶│ S3 NARRATIVE │──▶│ S4 SCENE PLAN │──▶│ S5 SOURCING  │
  │ video →    │   │ transcript → │   │ Claude →      │   │ ladder:      │
  │ audio →    │   │ hooks,claims,│   │ 6–10s scenes  │   │ T0 library   │
  │ transcript │   │ arcs         │   │ + master      │   │ T1 own video │
  │ (existing, │   │ (Claude)     │   │ prompts       │   │ T2 free stock│
  │  local)    │   │              │   │               │   │ T3 synthesize│
  └────────────┘   └──────────────┘   └───────────────┘   └──────┬───────┘
                                                                 │
                    ┌────────────────────────────────────────────┘
                    ▼
  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
  │ S6 SYNTHESIS │──▶│ S7 QA GATE   │──▶│ S8 ASSEMBLY  │──▶│ S9 RENDER    │
  │ Gemini still │   │ CLIP+aesth., │   │ EDL: rhythm, │   │ ffmpeg graph │
  │ → depth →    │◀──│ local, free, │   │ transitions, │   │ + captions   │
  │ 2.5D motion  │   │ bounded retry│   │ overlays,mix │   │ + aspects    │
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

- **Asset plane** — the unified visual catalog (your library + mirrored free stock). Long-lived, shared across all users and jobs.
- **Content plane** — one user video: transcript, narrative map, scene plan. Per-project.
- **Synthesis plane** — Gemini stills and the videos derived from them. Content-addressed, cacheable *across* projects.
- **Assembly plane** — the EDL and the render. Fully deterministic given the first three.

The first three planes are all **replayable**. If a render fails you re-render. If a scene fails QA you re-source one scene, never the reel.

---

## 2. SUBSYSTEM 1 — The unified visual catalog

This is where "we have GBs of raw data, pick the correct one" lives. Runs **offline, continuously, idempotently**. A reel job never touches raw files — only the catalog.

The key v2 change: **free stock footage is indexed into the same catalog as your motion graphics.** One schema, one retriever, one ranking model. A scene query doesn't care whether the winner is your particle overlay or a Pexels drone shot — it just returns the best visual for the intent.

### 2.1 Ingest pipeline

```
crawl → identity → probe → quality gate → proxy → analyze → tag → embed → publish
```

**Step 1 — Crawl.** Walk the source roots (local dirs + S3 prefixes, and the stock connectors in §2.4). Record `(path, size, mtime, etag)` per file; skip if unchanged. Emit one `asset_ingest_job` per new/changed file. Crawl state is a cursor table, so killing the process mid-crawl loses nothing.
*Free: stdlib + boto3.*

**Step 2 — Identity and dedup.** `sha256` of the bytes → `content_hash`. If it already exists, register the path as an alias and stop. Then a **perceptual video hash**: pHash of 8 evenly-spaced frames concatenated into a 512-bit signature. Near-duplicates (Hamming < 40) group into a `dup_group`; only the best member is retrievable. On a real scraped library this removes 30–50% of the volume.
*Free: `hashlib` + OpenCV DCT (already installed).*

**Step 3 — Probe** (`ffprobe`): duration, fps, resolution, codec, pix_fmt, bitrate, **alpha present** (`yuva*`/`rgba`, or `.mov` with ProRes 4444), audio present. Unreadable → `status=rejected` with the reason logged; never retried unless the file changes.
*Free: ffmpeg.*

**Step 4 — Quality gate.** Reject height < 720 for full-frame roles, duration < 0.4s, fps < 20, detected watermark, single-colour frames. Cheap, and it permanently keeps garbage out of retrieval.

**Step 5 — Proxy generation** — the step that makes everything downstream cheap:

- `preview.mp4` — 480p h264, capped at 10s
- `sprite.webp` — 5×5 contact sheet of 25 frames
- `key_0/1/2.jpg` — frames at 10%, 50%, 90%
- `thumb.jpg` — 320px poster
- `alpha_check.png` — mid-frame over a checkerboard, if alpha present

Proxies go to `s3://<bucket>/catalog/<hash[:2]>/<content_hash>/`. **The original is never read again after this step.**
*Free: ffmpeg.*

**Step 6 — Visual features** (local, CPU, no API):

| Feature | Method | Used by |
|---|---|---|
| `motion_energy` 0–1 | mean Farneback optical-flow magnitude | pacing-curve matching |
| `motion_in`, `motion_out` | mean flow direction over first/last 0.3s | **transition continuity** (§9.3) |
| `is_loopable` | SSIM(first frame, last frame) > 0.92 | background loops |
| `palette` | k-means k=5 over sampled frames | brand/scene colour match |
| `coverage` | non-transparent, non-black frame fraction | overlay vs. background |
| `text_in_asset` | Tesseract OCR on 3 keyframes | kinetic-text detection **and** watermark rejection |
| `safe_area` | saliency + edge density map | overlay placement that never covers a face |
| `phash` | DCT of 8 frames | dedup |

*Free: OpenCV, scipy, scikit-image, Tesseract — all already installed or pip-free.*

**Step 7 — Semantic tagging — Gemini 2.5 Flash (paid, allowed).** Send `sprite.webp` + probe facts with a **closed-vocabulary** structured-output schema. Closed vocabulary is non-negotiable; free-text tags make retrieval unusable at this scale.

```jsonc
{
  "role": "transition|background_loop|overlay_fx|lower_third|callout|kinetic_text|
           icon_burst|frame_mask|particle|light_leak|glitch|data_viz|logo_sting|
           live_action|aerial|macro|timelapse",
  "subjects": ["money","fitness","tech","food","travel","abstract", ...],  // closed list, ~80
  "style":    ["3d","2d_flat","hand_drawn","glitch","neon","minimal","grunge",
               "corporate","y2k","liquid","cinematic","documentary"],
  "mood":     ["energetic","calm","dramatic","playful","serious","luxurious","urgent"],
  "camera":   "static|push_in|pull_out|pan|orbit|handheld|aerial|none",
  "best_use": "hook|emphasis|scene_change|background|outro|stat_reveal",
  "caption":  "one sentence describing the asset literally",
  "quality":  1-5,
  "has_watermark": true,
  "text_in_asset": "none|placeholder|baked"
}
```

The model's `quality` and `has_watermark` are cross-checked against Step 6's mechanical signals; disagreement sends the asset to a quarantine queue rather than silently including it.

**Step 8 — Embeddings — self-hosted, free.** Two vectors per asset into **pgvector**:

- `visual_vec` (512d) — **OpenCLIP ViT-B/32** (`laion2b_s34b_b79k`) on the mid keyframe. Runs on CPU at ~50ms/image; no GPU required.
- `text_vec` (512d) — same model's text tower, over `caption + role + subjects + style + mood`.

Using one model for both towers means image and text land in the same space, which is what makes the cross-modal retrieval in §6 work at all.
*Free: `open_clip_torch`, MIT-licensed weights.*

**Step 9 — Publish.** Row flips to `status=ready`. Only `ready` rows are retrievable.

Every step is a pure function of the file bytes, so **re-running the whole indexer is safe and nearly free** — each step short-circuits on `content_hash`.

### 2.2 Throughput and cost

Steps 1–6 and 8 are CPU-bound and embarrassingly parallel: shard the worker pool by `content_hash[:2]` (256 shards) and run N machines with zero coordination. Step 7 is the only API cost: batch ~20 assets per Gemini Flash request behind a rate-limited queue, roughly **$0.0003/asset**.

**100k assets ≈ $30, one weekend, no GPU.** Paid once, reused by every job forever.

### 2.3 Catalog schema

```sql
visual_assets (
  id uuid primary key,
  content_hash char(64) unique,
  dup_group_id uuid,            -- null if unique; points to the canonical row
  is_canonical bool,
  -- provenance
  tier smallint,                -- 0=owned library, 1=user's own footage, 2=free stock
  source text,                  -- 'library' | 'pexels' | 'pixabay' | 'coverr' | 'project:<id>'
  source_uri text, source_id text, aliases jsonb,
  license text not null,        -- 'owned' | 'pexels' | 'pixabay' | 'cc0' | 'cc-by' | ...
  license_attribution text,     -- rendered into the description when required
  -- probe
  duration_s float, fps float, width int, height int, aspect text,
  has_alpha bool, has_audio bool, codec text,
  -- features
  motion_energy float, motion_in vector(2), motion_out vector(2),
  is_loopable bool, palette jsonb, coverage float, safe_area jsonb,
  phash bit(512),
  -- semantics (Gemini Flash)
  role text, subjects text[], style text[], mood text[],
  camera text, best_use text, caption text, quality smallint,
  text_in_asset text, has_watermark bool,
  -- vectors (OpenCLIP, local)
  visual_vec vector(512), text_vec vector(512),
  -- ops
  status text, proxy_prefix text,
  usage_count int default 0, win_rate float,   -- fed by Subsystem 10
  created_at timestamptz, updated_at timestamptz
);

CREATE INDEX ON visual_assets USING hnsw (text_vec   vector_cosine_ops);
CREATE INDEX ON visual_assets USING hnsw (visual_vec vector_cosine_ops);
CREATE INDEX ON visual_assets USING gin  (subjects);
CREATE INDEX ON visual_assets (role, status, tier, has_alpha, duration_s);
```

### 2.4 Free stock connectors (new in v2)

This is what replaces most of what Veo was going to do. Real cinematic footage, free, commercially licensed.

| Source | API | License | Notes |
|---|---|---|---|
| **Pexels Video** | free key, ~200 req/hr | Pexels License — commercial use, no attribution required | Best quality. Primary source. |
| **Pixabay Video** | free key | Pixabay Content License — commercial use | Large volume, more variable quality. |
| **Coverr** | free | CC0-like | Strong for abstract/atmospheric backgrounds. |
| **Mixkit** | scrape/manual | Mixkit Free License | Good motion graphics overlap. |
| **Openverse** | free API | aggregates CC-licensed media | Use only `cc0`/`cc-by`; store attribution. |

**Ingestion strategy — do not mirror their whole library.** Several of these permit use but prohibit redistributing the raw files as a competing stock service. So:

1. **Harvest metadata + thumbnails only** across broad topical seed queries, into `visual_assets` with `tier=2`, `status='indexed_remote'`.
2. Generate proxies and embeddings from the **thumbnail/preview** stream, not the full-res original.
3. **Fetch the full-res original lazily**, only when an asset is actually selected for a reel, then cache it for 30 days under `content_hash`.

This keeps you inside the terms, keeps storage bounded, and still gives the retriever a searchable index of hundreds of thousands of real shots.

**Attribution pipeline:** assets with `license_attribution` set propagate their credit line into the reel's description field automatically in §11. Never make this a manual step — it's how licensing compliance quietly breaks.

---

## 3. SUBSYSTEM 2 — Ingest (existing, already free)

Reuses the current `PipelineOrchestrator` steps: `DOWNLOAD → AUDIO_EXTRACTION → AI_NOISE_CANCELLATION → TRANSCRIPTION`. WhisperX and faster-whisper run locally on free weights — no change needed.

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

Word timings are load-bearing — assembly snaps every cut to a word boundary via the existing `content_intelligence/word_snapper.py`.

---

## 4. SUBSYSTEM 3 — Narrative understanding (Claude)

Long videos don't fit in one request, which is what `content_intelligence/transcript_windows.py` already solves — reuse it.

**Map** (per window, parallel) — **Claude Haiku 4.5**. This is where `groq` used to sit; Haiku is the cheap high-throughput replacement and is inside the allowed budget. Extract `claims`, `stories`, `numbers/stats`, `emotional_peaks`, `quotable_lines`, each timestamped.

**Reduce** (one call) — **Claude Sonnet 5**. Merge into a **Narrative Map**:

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

`arcs` are the candidate reels. The existing `highlighter.py` + `scorer.py` rank them; top K are taken and **one arc becomes one reel**. This is the join between the old pipeline and the new one.

**Prompt caching** on the Narrative Map + vocabulary block cuts the planner's input cost by ~90% across the per-arc calls that follow.

---

## 5. SUBSYSTEM 4 — Scene Planner (Claude)

**Model:** `claude-opus-5` for planning — the creative bottleneck, worth the spend. `claude-sonnet-5` for variants and re-ranking.

**Input:** one arc's transcript slice with word timings, the Narrative Map, the brand kit, and — critically — **the catalog's closed tag vocabulary** from §2.1 Step 7. Feeding the planner the exact vocabulary the catalog uses is the trick that makes sourcing hit: the planner asks for things that exist.

**New in v2:** the planner is told the sourcing ladder exists and marks each scene's expected tier. A scene whose visual is "a real person deadlifting" should target free stock (tier 2); "abstract neon energy flowing" should target your library (tier 0); "a specific metaphor nothing exists for" targets synthesis (tier 3).

```jsonc
{
  "reel": {
    "target_duration_s": 42, "aspect": "9:16",
    "hook_strategy": "contrarian_claim", "thesis": "...",
    "pacing_curve": "fast_hook_then_settle"
  },
  "scenes": [
    {
      "id": "s1", "order": 1,
      "role": "hook",                                  // hook|setup|evidence|turn|payoff|cta
      "source_span": {"start": 412.30, "end": 420.10}, // word-snapped
      "vo_text": "Most people fail at this because...",
      "duration_s": 7.8,
      "visual_intent": "one sentence: what the viewer must SEE",
      "preferred_tier": 2,                             // planner's hint, not a mandate
      "asset_query": {
        "role": "live_action",
        "subjects": ["fitness"], "style": ["cinematic"], "mood": ["dramatic"],
        "needs_alpha": false, "min_duration_s": 7.8
      },
      "overlay_query": {                               // alpha, always from the library
        "role": "kinetic_text", "text": "90% FAIL HERE", "needs_alpha": true
      },
      "synthesis": {                                   // only used if the ladder reaches T3
        "still_prompt": "<Gemini Flash Image prompt>",
        "camera_move": "slow_push_in",
        "parallax_strength": 0.35
      },
      "camera": "slow push_in",
      "palette": ["#0B1F3A", "#F2A900"],
      "continuity": {"from": null, "to": "s2", "match_on": "color+motion_left"},
      "priority": 1
    }
  ],
  "budget": {"max_synthesized_scenes": 3, "max_cost_usd": 0.40}
}
```

**Hard rules, in the prompt and re-checked in code:**

- Every scene is 6.0–10.0s; the sum lands within ±10% of `target_duration_s`.
- `source_span` sits on word boundaries and never overlaps another scene.
- `still_prompt` never requests legible text, logos, or a real person's likeness.
- The hook is scene 1 and must resolve visually in under 1.5s.

**Validation layer** (`broll/planner.py`): schema → temporal (no overlap, in-bounds, word-snapped) → duration → content policy. Up to 2 repair round-trips with the specific violations fed back, then hard-fail with a legible reason. Failing here is cheap.

---

## 6. SUBSYSTEM 5 — Sourcing (retrieval)

Resolve each scene's `asset_query` and `overlay_query` against the unified catalog. This decides where on the ladder each scene lands.

**Stage 1 — Hard filter (SQL).**
`status='ready' AND is_canonical AND role = ? AND duration_s >= scene.duration_s * 0.9 AND has_alpha = ? AND license IN (allowed_for_this_user) AND NOT has_watermark AND quality >= 3`, plus aspect compatibility — a 16:9 shot works for 9:16 only if `coverage` and `safe_area` survive the crop.

**Stage 2 — Hybrid recall (→ top 200).** Three retrievers, all free:

- **Lexical** — Postgres full-text / BM25 over `caption || subjects || style || mood`.
- **Dense (text→text)** — cosine kNN on `text_vec` vs. the OpenCLIP embedding of `visual_intent`.
- **Dense (text→image)** — cosine kNN on `visual_vec` vs. the same query embedding. Cross-modal, and it works precisely because §2.1 Step 8 used one model for both towers.

Fuse with **Reciprocal Rank Fusion** (k=60) — it beats score normalisation here because the three scorers live on incomparable scales.

**Stage 3 — Feature re-rank (200 → 20).** A small linear/GBDT model (scikit-learn, free) over: RRF score; palette distance to `scene.palette` (CIEDE2000); motion-energy fit to the scene's slot in the pacing curve; alignment of this asset's `motion_in` with the previous scene's `motion_out`; `win_rate` from Subsystem 10; a **tier preference bonus** from `preferred_tier`; and a **recency-diversity penalty** so the same asset isn't reused inside the reel or across the user's last 5 reels.

**Stage 4 — LLM re-rank (20 → 3) — Claude Sonnet 5.** One call per scene over the 20 captions + thumbnails: 3 ranked picks, one-line reason each. Catches the semantic misses embeddings make ("barbell" vs "barbershop").

**Stage 5 — Global MMR pass.** Maximal Marginal Relevance across all scenes' shortlists, so the selection is varied reel-wide rather than six near-identical neon loops.

**Stage 6 — Ladder decision.**

```
overlays / transitions / kinetic text  → ALWAYS tier 0 (your library). Never synthesized.

for each visual scene:
  if top1_confidence >= 0.72:            → use it                    (free, instant)
  elif tier-1 candidate exists ≥ 0.60:   → use user's own footage     (free, most relevant)
  elif tier-2 candidate exists ≥ 0.58:   → fetch free stock original  (free, ~2s)
  else:                                  → SYNTHESIZE (§7)           (~$0.04)
```

`top1_confidence` is the calibrated re-rank score. **This is the cost dial** — and note that unlike v1 the entire dial now ranges from $0.00 to $0.04, not $0.00 to $0.50.

**Tier 1 — the user's own footage — deserves special mention.** A 60-minute source video contains hundreds of usable B-roll seconds that aren't in the reel's arc: the speaker gesturing, the product on the desk, the whiteboard. Index the source video into the catalog at ingest time (`tier=1`, `source='project:<id>'`, scoped to that user). It's free, perfectly on-brand, perfectly relevant, and no generative model can match it. **Check this tier before reaching for stock.**

---

## 7. SUBSYSTEM 6 — Synthesis (the free replacement for Veo)

Reached only when the ladder finds nothing — typically 1–3 scenes out of 6.

### 7.1 Default path: Gemini still → depth → 2.5D motion (CPU, no GPU)

**Step A — Generate the still. Gemini 2.5 Flash Image** (paid, allowed). One 9:16 image from `still_prompt`, conditioned on the brand palette. ~3s, ~$0.04. Image models are far more reliable than video models at composition, lighting, and prompt adherence — we're playing to the strength.

**Step B — Estimate depth. Depth Anything V2 Small** (local, free). Monocular depth map at 518px. **Use the Small checkpoint — it is Apache-2.0. Base and Large are CC-BY-NC-4.0 and cannot be used commercially.** MiDaS (MIT) is the fallback if you prefer a permissive-by-default lineage. Runs in ~0.4s on CPU.

**Step C — Animate.** Displace the still along the depth map while moving a virtual camera, producing genuine parallax rather than a flat zoom:

| Move | Implementation | Reads as |
|---|---|---|
| `slow_push_in` | camera −Z, depth-weighted displacement | dolly in |
| `pull_out` | camera +Z | reveal |
| `orbit` | camera X arc + depth warp | 3D turnaround |
| `pan` | camera X translate, foreground faster | tracking shot |
| `rack_focus` | depth-masked Gaussian blur ramp | focus pull |

Implemented as a per-frame mesh warp: build a triangle grid, offset vertices by `depth * camera_delta`, remap with `cv2.remap`, inpaint disocclusions with a fast Telea fill from the background layer. 30fps × 8s = 240 frames at roughly 15ms each → **~4 seconds per scene, CPU only.**

**Step D — Composite for life.** A still with parallax still reads as a still. Layer from the library: a light leak or dust-particle overlay (`blend=screen`, 8% opacity), a subtle film-grain plate, and a 0.3% breathing scale oscillation. This is what pushes it from "animated photo" to "shot."

The result is a 6–10s cinematic clip at **$0.04, no GPU, ~8s wall clock.** For the B-roll role — atmosphere, metaphor, texture under a voiceover — it is genuinely competitive with generative video, and strictly more controllable.

### 7.2 Procedural fallbacks (fully free, no API at all)

When even Gemini is unavailable or the budget is exhausted:

- **Data-viz scenes** — render the Narrative Map's `numbers` as animated charts with matplotlib/Cairo → frames → video. Free, and for stat reveals it beats any generated footage.
- **Typographic scenes** — the quote from `vo_text` as kinetic type over a library background loop, using your existing `subtitle_styling` typography engine.
- **Abstract scenes** — procedural shader-style generators (flow fields, particle systems, gradient meshes) in numpy/OpenCV, seeded from the scene palette. Infinite, free, on-brand.

These aren't just degradation paths. For stats and quotes they're the *preferred* choice, and the planner should select them directly.

### 7.3 Optional Tier 4: self-hosted generative video (GPU, off by default)

If you later add a GPU, true I2V slots in behind the same interface. License is the deciding factor:

| Model | License | Verdict |
|---|---|---|
| **Wan 2.2** (T2V/I2V) | **Apache-2.0** | ✅ Cleanest commercial choice |
| **LTX-Video** | LTXV license, commercial under a revenue cap | ⚠️ Check the cap against your revenue |
| **CogVideoX** | varies by size; 2B Apache-2.0, 5B restricted | ⚠️ 2B only |
| **Stable Video Diffusion** | Stability membership required for commercial | ❌ Not free |

~20GB VRAM, ~60–120s per clip. Zero API cost, real infra cost. Keep it off by default; enable per-workspace.

### 7.4 Provider interface

```python
class BrollSynthesizer(Protocol):
    async def still(self, req: StillRequest) -> StillResult: ...      # Gemini Flash Image
    async def animate(self, still: StillResult, move: CameraMove,
                      duration_s: float) -> LocalClip: ...            # local depth + warp

# implementations:
#   GeminiStill + DepthParallaxAnimator   (default, CPU, ~$0.04/scene)
#   ProceduralSynthesizer                 (charts / type / abstract — $0.00)
#   WanI2VSynthesizer                     (optional, GPU, $0.00 API)
```

Everything is keyed by `synth_cache_key = sha256(still_prompt, camera_move, duration, aspect, seed)`. Identical scenes across projects are cache hits at $0.

---

## 8. SUBSYSTEM 7 — QA gate (entirely local and free)

Nothing enters assembly unscored. Every check below runs on CPU with free weights — and the CLIP embedding is computed once and reused by three of them.

| Check | Method | Fail action |
|---|---|---|
| **Intent adherence** | OpenCLIP cosine(mean of 5 frames, `visual_intent`) ≥ τ (τ≈0.24, calibrated) | drop a tier, re-source |
| **Aesthetic** | LAION aesthetic predictor (MIT) — a tiny MLP head on the CLIP embedding already computed, ≥ 5.0 | re-source |
| **Liveness** | frame-diff variance > ε — catches frozen output | re-animate with stronger parallax |
| **Black / blank** | mean luma within [8, 247] | re-source |
| **Unwanted text** | Tesseract finds text when none was requested | re-source |
| **Face artifacts** | OpenCV/MediaPipe landmark confidence variance | re-source |
| **Flicker** | temporal luma stddev across consecutive frames | reject → next candidate |
| **Continuity** | palette ΔE + `motion_out → motion_in` vs. neighbours | reorder, or insert a transition |

**Bounded retry:** at most 2 attempts per scene, at most 4 per reel, spent in `priority` order — the hook is fixed before scene 5. Because re-sourcing is free, the retry budget exists to bound *latency*, not cost. Once spent, the scene falls back to its best library asset. **The reel always renders.**

**Final holistic pass — Claude Sonnet 5.** Once the EDL exists, one call sees the storyboard (contact sheet of all scenes + VO text) and returns `{verdict, scene_fixes[]}`. Only the named scenes are touched. This catches "technically fine, but scene 3 visually contradicts the voiceover."

---

## 9. SUBSYSTEM 8 — Assembly intelligence (the EDL builder)

The "combine them with AI intelligence" step. Output is an **Edit Decision List** — pure data. Rendering is then a deterministic function of it, which makes the system debuggable, diffable, and editable from the frontend timeline. All free (librosa and opencv are already installed).

**9.1 Rhythm grid.** Beat-track the music bed (`librosa.beat.beat_track`) → beat timestamps. Compute the VO speech-energy envelope. Candidate cut points = (word boundaries from `word_snapper.py`) ∩ (beats ± 80ms) ∩ (VO pauses > 120ms). Cuts landing on beats *and* on speech is what makes an edit feel intentional rather than mechanical.

**9.2 Pacing curve.** Target shot length by position:

- **0–3s (hook)** — 0.7–1.2s cuts, highest motion-energy assets, hardest transitions
- **3s → 60%** — 1.8–2.6s, settle, let claims land
- **60% → 90%** — tighten to 1.2–1.8s approaching the payoff
- **last 10%** — one held shot plus the CTA overlay

Scene clips are **sub-cut** to hit this: an 8s clip becomes three 1.4s punches with speed ramps, not one long boring shot. This is the single biggest retention lever in the system.

**9.3 Transition selection.** At each junction, query `role='transition'`, `duration ≤ 0.5s`, ranked by how well the transition's `motion_in` aligns with the outgoing shot's `motion_out`, and its `motion_out` with the incoming shot's entry. Whip-pan out → whip transition → whip-pan in. Low-energy junctions get a match-cut or a 4-frame dissolve — not every cut deserves a graphic.

**9.4 Overlay layer.** Per scene: kinetic text carrying the key phrase, placed inside `safe_area` so it never covers a face; stat reveals bound to `numbers` from the Narrative Map; brand lower-third on scene 1; progress bar; end card. All from your library — which is exactly the thing generative video could never do well, and the reason the library is the centrepiece rather than a fallback.

**9.5 Audio bed.** VO normalised to −16 LUFS, music sidechain-ducked −9dB under speech, library SFX on transitions, beat-aligned. Master at −14 LUFS, true peak −1 dBTP.
*Free: ffmpeg `loudnorm` + `sidechaincompress`.*

**Music sourcing (free):** curate a cleared pool into `visual_assets`-style rows with per-track licenses — Pixabay Music (commercial OK), Free Music Archive (filter to CC0/CC-BY), YouTube Audio Library (free, some require attribution). Attribution propagates to the description automatically.

**9.6 The EDL.**

```jsonc
{
  "reel_id": "...", "aspect": "9:16", "fps": 30, "duration_s": 42.0,
  "attribution": ["Video by Jane Doe on Pexels"],
  "tracks": {
    "video": [
      {"t": 0.0, "dur": 1.1, "src": {"kind": "asset", "asset_id": "px_8812", "tier": 2},
       "in": 0.4, "speed": 1.0,
       "transform": {"scale": 1.06, "pan": [0, -0.02]}, "grade": "lut_warm_02"},
      {"t": 1.1, "dur": 0.35, "src": {"kind": "asset", "asset_id": "a_whip_14", "tier": 0},
       "blend": "screen"},
      {"t": 1.45, "dur": 2.2, "src": {"kind": "synth", "clip_id": "sy_s3"}}
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

Persisted and versioned. The frontend timeline reads and writes it. "Re-source scene 3" mutates one entry.

---

## 10. SUBSYSTEM 9 — Render (ffmpeg, free)

`assembly/renderer.py` compiles the EDL into a single ffmpeg filter graph, extending `video_processor/ffmpeg_service.py`:

1. Decode, trim, speed-ramp each video entry
2. Scale/crop to target aspect via the entry's transform — reuse `content_intelligence/crop_strategy.py` and `reframing.py` for tier-1 shots from the source video
3. Per-shot LUT for grade continuity
4. `overlay` alpha assets in z-order
5. Burn captions via existing `subtitle_styling` / `depth_captions`
6. `amix` + `sidechaincompress` for audio
7. Encode: h264 high, CRF 18, yuv420p, `+faststart`, 30fps

**Multi-aspect:** render the 9:16 master, derive 1:1 and 16:9 by re-running the graph with different crop transforms — the EDL already carries per-shot safe areas. Poster frame extracted at the highest-saliency frame.

Outputs land in the existing `GeneratedClip` table, plus `edl_json`, `reel_kind`, and `attribution_text`.

---

## 11. SUBSYSTEM 10 — Growth layer

The goal is channel growth, so the pipeline closes the loop rather than just emitting a file.

- **Hook variants.** Render 3 alternative first-3-second openings from the same EDL. Free — it's the same EDL with one entry swapped.
- **Metadata (Claude).** Extend `content_intelligence/metadata_gen.py`: 3 title variants, description, 15 hashtags, per-platform caption, best-post-time from the user's own analytics. **Required license attributions are appended here automatically.**
- **Thumbnail.** Highest-saliency frame + generated text overlay, 3 variants. Free (local saliency + your typography engine).
- **Predicted retention curve.** A scikit-learn model over hook strength, cut density, motion energy per second, caption coverage, and payoff position. Shown as a curve with the weak second flagged, so the user fixes it before publishing. Free.
- **Feedback loop.** `analytics/` ingests published-reel performance and attributes it to `visual_assets.win_rate`, the Stage-3 re-rank weights, and `ClipScorer`.

**Every reel published makes the next retrieval better.** With a free stack this is the *only* moat — you're not buying an advantage from a model vendor, so the advantage has to be your catalog plus its win-rate data.

---

## 12. Data model additions

```sql
-- asset plane
visual_assets       -- see §2.3 (your library + user footage + free stock, unified)
asset_ingest_jobs   (content_hash, stage, status, error, attempts, updated_at)
asset_usage         (asset_id, reel_id, scene_id, published, views, retention_3s, created_at)
stock_harvest_state (source, seed_query, cursor, last_run_at)

-- content plane
narrative_maps      (project_id, map_json, model, created_at)
reel_plans          (id, project_id, arc_id, plan_json, status, model, cost_usd)
reel_scenes         (id, reel_plan_id, "order", role, source_start, source_end,
                     duration_s, visual_intent, preferred_tier, asset_query jsonb,
                     synthesis jsonb, resolved_tier, resolved_asset_id, status)

-- synthesis plane
synthesized_broll   (id, scene_id, synth_cache_key unique, synthesizer,
                     still_s3, video_s3, duration_s, cost_usd,
                     qa_scores jsonb, qa_verdict, attempt, status)

-- assembly plane
reel_edls           (id, reel_plan_id, edl_json, version, created_at)
reel_renders        (id, edl_id, aspect, s3_key, poster_url, duration_s,
                     attribution_text, status, ffmpeg_log)
```

New `PipelineStepType` values: `NARRATIVE_MAP`, `SCENE_PLANNING`, `ASSET_SOURCING`, `BROLL_SYNTHESIS`, `BROLL_QA`, `EDL_ASSEMBLY`, `REEL_RENDER`. Add via an Alembic migration extending the `pipeline_step_type` enum — follow `20260911000000_fix_missing_pipeline_step_enum_values.py`.

---

## 13. Module layout

```
backend/
  visual_catalog/          # SUBSYSTEM 1 — offline, own worker process
    crawler.py  prober.py  dedup.py  proxy.py  visual_features.py
    tagger.py              # Gemini Flash, closed vocabulary
    embedder.py            # OpenCLIP, local, CPU
    connectors/            # free stock sources
      base.py  pexels.py  pixabay.py  coverr.py  openverse.py
    index.py  retriever.py
    model.py  repository.py  schema.py  route.py  worker.py
  broll/                   # SUBSYSTEMS 4, 5, 6, 7
    planner.py             # Claude scene plan + validation/repair loop
    sourcer.py             # hybrid retrieval + ladder decision
    synth/
      base.py
      gemini_still.py      # Gemini 2.5 Flash Image
      depth.py             # Depth Anything V2 Small (Apache-2.0) / MiDaS
      parallax.py          # 2.5D mesh warp camera moves
      procedural.py        # charts / kinetic type / abstract generators
      wan_i2v.py           # optional GPU tier, off by default
    qa.py                  # local CLIP + aesthetic + artifact gates
    model.py  repository.py  schema.py
  assembly/                # SUBSYSTEMS 8, 9
    rhythm.py  transitions.py  overlays.py  audio_mix.py
    edl.py     renderer.py    schema.py
  content_intelligence/
    narrative.py           # NEW — map/reduce on transcript_windows.py, Claude Haiku
  pipeline/
    service.py             # extended: new steps wired into step_order
```

Conventions match the repo: `service.py` orchestrates, `repository.py` owns SQL, `schema.py` holds Pydantic, `route.py` exposes FastAPI, `model.py` holds SQLAlchemy.

---

## 14. Dependency changes

```diff
- groq>=0.31.0                    # dropped — replaced by Claude Haiku
+ anthropic>=0.40.0               # paid, allowed
+ google-genai>=1.0.0             # paid, allowed (Flash text + image)
+ open_clip_torch>=2.24.0         # free, MIT — embeddings + QA
+ pgvector>=0.3.0                 # free
+ scikit-learn>=1.5.0             # free — rerank model, retention model
+ scikit-image>=0.24.0            # free — SSIM, features
+ pytesseract>=0.3.13             # free — OCR / watermark detection
+ transformers>=4.44.0            # free — Depth Anything V2 Small
+ torch                           # free — CPU build is sufficient
+ matplotlib>=3.9.0               # free — procedural data-viz scenes
# already present and free: librosa, opencv-contrib-python-headless, scipy,
#                           faster-whisper, whisperx, boto3, ffmpeg (system)
```

Every added package is CPU-viable. **No GPU is required anywhere in the default path.**

### 14.1 Groq migration surface

Dropping `groq` is not a one-line change — it is imported by 7 modules today:

| File | Usage | Migration |
|---|---|---|
| `clients/ai/groq.py` | the client itself | delete; `clients/ai/anthropic.py` already implements `BaseAI` |
| `clients/ai/__init__.py` | registry entry | remove `"groq"` from `_REGISTRY` |
| `content_intelligence/transcript_windows.py` | imports `estimate_tokens` | **move `estimate_tokens` to `clients/ai/base.py`** — it is provider-agnostic and shouldn't have lived in the Groq module |
| `content_intelligence/service.py` | constructs `Groq()` and injects it into 4 collaborators | swap to `get_ai("anthropic")`; the constructors already take a `BaseAI` |
| `content_intelligence/highlighter.py` | LLM calls | model swap only |
| `content_intelligence/research.py` | LLM calls | model swap only |
| `clip_generation/service.py` | LLM calls | model swap only |
| `depth_captions/planner.py` | LLM calls | model swap only |
| `tests/test_structured_clip_analysis.py` | mocks `Groq` | re-point the mock at `BaseAI` |

Because everything already depends on the `BaseAI` interface rather than the concrete client, this is mostly a factory-argument change. Do it as its own commit **before** P0 — it's a prerequisite, not part of the new work.

**Note on Groq's free tier:** Groq does offer a genuinely free rate-limited tier. If you want to keep it for the high-volume map stage in §4 and stay inside the "free only" rule, that's legitimate — but the rate limits make it unreliable for production throughput, which is why the default here is Claude Haiku. Keeping the client behind `BaseAI` means the choice stays reversible either way.

---

## 15. API surface

```
POST  /catalog/ingest             {source_uri}            → job_id      (admin)
POST  /catalog/harvest            {source, seed_queries}  → job_id      (admin)
GET   /catalog/stats                                      → counts by role/tier/status
POST  /catalog/search             {query, filters}        → assets      (debug/UI)

POST  /reels/plan                 {project_id, arc_id}    → reel_plan
GET   /reels/{id}/plan                                    → scenes + candidate previews
PATCH /reels/{id}/scenes/{sid}    {asset_id?, still_prompt?, duration_s?}
POST  /reels/{id}/source          {scene_ids?}            → runs the ladder
GET   /reels/{id}/edl                                     → EDL
PATCH /reels/{id}/edl                                     → user timeline edits
POST  /reels/{id}/render          {aspects[]}             → render jobs
GET   /reels/{id}/status                                  → per-stage progress
WS    /ws/reels/{id}                                      → live progress events
```

Progress reuses the existing `ProgressCallback` signature, so the current frontend progress UI keeps working unchanged.

---

## 16. Failure handling, idempotency, resume

Every stage is keyed and cached, so the pipeline is **resumable at any point** — matching the `resume=True` behaviour already in `PipelineOrchestrator`.

| Stage | Cache key | On failure |
|---|---|---|
| Ingest | `content_hash` | per-file; one bad file never blocks the crawl |
| Stock harvest | `source + seed_query + cursor` | resumable cursor; rate-limit backoff |
| Narrative | `project_id + transcript_hash` | retry with smaller windows |
| Plan | `arc_id + model + prompt_version` | 2 repair loops, then hard fail with a reason |
| Sourcing | `scene_id + catalog_version` | drop a tier; nothing found → synthesize |
| Stock fetch | `asset_id` | 3 retries → next candidate (never blocks: the shortlist has 3) |
| Synthesis | `synth_cache_key` | retry → procedural fallback |
| QA | `synthesized_broll.id` | bounded retry → best library asset |
| EDL | `reel_plan_id + version` | deterministic; always recomputable |
| Render | `edl_id + aspect` | re-render only; never re-source |

**Governing principle: no failure past the planner may abort the reel.** Every downstream failure drops one rung down the ladder. The user gets a finished reel or a clear pre-planning error — never a half-finished job.

---

## 17. Cost and latency budget (one 45s reel, 6 scenes)

Typical resolution: 2 scenes from your library, 1 from the user's own footage, 2 from free stock, 1 synthesized.

| Stage | Latency | Cost | Free? |
|---|---|---|---|
| Transcript (WhisperX, local) | 60–180s | $0.00 | ✅ |
| Narrative map (Haiku + Sonnet) | 15–40s | ~$0.04 | 💲 |
| Scene plan (Opus 5, cached prefix) | 20–35s | ~$0.09 | 💲 |
| Sourcing: SQL + CLIP + RRF + rerank | 3–8s | $0.00 | ✅ |
| LLM re-rank ×6 (Sonnet) | 6–10s | ~$0.03 | 💲 |
| Stock originals fetch ×2 | 3–6s | $0.00 | ✅ |
| Synthesis ×1 (Gemini still + parallax) | 8–12s | ~$0.04 | 💲 |
| QA (local CLIP + aesthetic) | 8–15s | $0.00 | ✅ |
| Holistic QA (Sonnet) | 5–8s | ~$0.02 | 💲 |
| EDL | <2s | $0.00 | ✅ |
| Render ×3 aspects (ffmpeg) | 40–90s | $0.00 | ✅ |
| **Total** | **≈ 3–7 min** | **≈ $0.22** | |

**v1 (Veo): ~$2.00–3.60/reel. v2 (free stack): ~$0.22/reel — about 12× cheaper, and faster**, because free stock retrieval takes 3 seconds where Veo took 2–4 minutes.

**Catalog build-out (one-time):** ~$30 per 100k assets, Gemini Flash tagging only.

---

## 18. Build order

| Phase | Deliverable | Why in this position |
|---|---|---|
| **P0** | `visual_catalog` steps 1–6 + 8 (crawl → proxy → features → OpenCLIP embeddings), no LLM tagging | Nothing works until the GBs are addressable. Pure infra, testable offline, **$0**. |
| **P1** | Gemini Flash tagging + `retriever.py` + a debug search UI | Prove retrieval quality by hand before anything depends on it. If search is bad, everything above it is bad. |
| **P2** | Stock connectors (Pexels first) + tier-1 indexing of the user's own footage | Multiplies catalog coverage for **$0**. This is what makes the no-Veo constraint a non-issue. |
| **P3** | `narrative.py` + `planner.py` → storyboard in the UI, **no sourcing yet** | Validates the creative core cheaply. Iterate the planner prompt here. |
| **P4** | `sourcer.py` + EDL + renderer — ladder tiers 0–2 only, no synthesis | **A complete, shippable product at ~$0.16/reel.** Most reels will be good on retrieval alone. |
| **P5** | `synth/` — Gemini still + depth parallax + procedural generators | Closes the coverage gap for the 1–2 scenes retrieval can't serve. |
| **P6** | Growth layer + analytics feedback into `win_rate` and rerank weights | The compounding advantage. Needs published-reel data, so it's last. |

**P4 is the milestone.** A fully working product before a single synthesized frame exists.

---

## 19. Model and license register

Every non-Claude, non-Gemini component, pinned:

| Component | Model / lib | License | Runs on |
|---|---|---|---|
| ASR | WhisperX + faster-whisper | MIT / BSD | CPU (GPU optional) |
| Embeddings | OpenCLIP ViT-B/32 `laion2b_s34b_b79k` | MIT | CPU |
| Aesthetic score | LAION aesthetic predictor v2 | MIT | CPU (reuses CLIP embedding) |
| Depth | **Depth Anything V2 Small** | **Apache-2.0** ⚠️ Base/Large are CC-BY-NC — do not use | CPU |
| Depth (alt) | MiDaS small | MIT | CPU |
| OCR | Tesseract | Apache-2.0 | CPU |
| Optical flow / CV | OpenCV | Apache-2.0 | CPU |
| Beat tracking | librosa | ISC | CPU |
| Segmentation | SAM (existing `depth_captions`) | Apache-2.0 | GPU optional |
| Vector search | pgvector | PostgreSQL license | CPU |
| Rerank / retention | scikit-learn | BSD-3 | CPU |
| Encode / audio | ffmpeg | LGPL/GPL ⚠️ build flags matter | CPU |
| Optional I2V | **Wan 2.2** | **Apache-2.0** | GPU |

⚠️ **ffmpeg licensing:** a build with `--enable-gpl` or `--enable-nonfree` (x264, libfdk-aac) carries GPL obligations. For a hosted SaaS this is generally fine, but if you ever ship a desktop binary, use an LGPL build with `libopenh264` or hardware encoders.

---

## 20. Open decisions

1. **"Free" and GPUs.** The default path is CPU-only and truly zero-marginal-cost. If a GPU box is acceptable, Tier 4 (Wan 2.2, Apache-2.0) adds real generative video at $0 API cost. **Confirm which you mean** — it's the only open question that changes the build.
2. **Stock ToS diligence.** Pexels/Pixabay permit commercial use but restrict redistributing files as a competing stock service. The lazy-fetch design in §2.4 is built to stay inside that, but get the terms read properly before harvesting at scale.
3. **Music pool.** Needs curation with per-track licenses. Currently the least-solved free component and a launch blocker.
4. **Vector store.** pgvector (you already run Postgres) until ~2M assets, then reassess Qdrant.
5. **Human-in-the-loop.** At $0.22/reel, auto-run is affordable in a way it wasn't at $3. Recommend auto by default with plan review as an opt-in.
