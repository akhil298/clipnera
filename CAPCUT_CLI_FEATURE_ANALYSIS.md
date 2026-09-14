# capcut-cli Feature Analysis for Clipnera

## What is capcut-cli

capcut-cli (v0.23.0) is a zero-dependency Node.js CLI that directly reads/writes
CapCut/JianYing draft JSON files (`draft_content.json`, `draft_info.json`,
`template-2.tmp`). It produces **editable CapCut project files** — not final MP4s.
Users open the result in the CapCut GUI, review/adjust, then render.

**Key difference from Clipnera**: Clipnera renders final MP4s with FFmpeg
(burned-in subtitles, hard filters). capcut-cli produces editable project files
where subtitles are text tracks, styling is editable presets, and the user
does the final creative pass in the GUI.

---

## Full Feature Inventory (68 commands)

### Read / Inspect
- **info** — Project overview: duration, resolution, fps, tracks, segments, material summary
- **tracks** — List all tracks with type, name, segment count, duration
- **segments** — List segments with timing; `--track` filter by type
- **texts** — List all text/subtitle content
- **materials** — Material type counts; `--type` filter for one type
- **segment <id>** — Full detail for one segment + its material
- **material <id>** — Full detail for one material
- **version** — Detect CapCut/JianYing version, schema flags, support status, write guard
- **lint** — Schema-aware checks (overlaps, line length, missing files, gaps); exit 0/1/2 for CI; `--fix`
- **timeline** — ASCII bar visualization of track/segment layout
- **diff <A> <B>** — Compare two drafts: segments/materials added/removed/changed
- **projects** — List CapCut/JianYing draft folders on disk
- **diagnose** — Inspect canonical files, divergence, editor-write safety, nested evidence

### Create
- **init <name>** — Create empty draft from template (`--template bundled|auto|<dir>`, `--ratio`, `--width/height`)
- **quickstart <name>** — One-command: init + add one input + lint + print open-in-CapCut step
- **compile <spec.json>** — Build draft from declarative JSON spec; `--data <rows.jsonl>` for mass production

### Add Media
- **add-video** — Copy media into `assets/video/`, create video material + segment. Wikimedia URLs supported (license-checked).
- **add-audio** — Same for audio track
- **add-text** — Create text segment with styling (`--color`, `--font-size`, `--align`, `--x/--y`, `--preset`)
- **tts** — Synthesize voiceover via `--tts-cmd` (piper/say/espeak), creates audio segment
- **add-sticker** — Sticker on own track with transform
- **add-sfx** — Sound effect on dedicated track
- **add-cover** — Set project thumbnail

### Edit / Animate
- **set-text** — Change text segment content (handles CapCut 8.9+ caption templates)
- **shift** / **shift-all** — Shift segment(s) in time
- **speed** — Change playback speed
- **volume** — Set audio volume (0.0-1.0)
- **trim** — Trim to source window
- **opacity** — Set clip opacity (0.0-1.0)
- **keyframe** — Add keyframe (position/scale/rotation/alpha/volume); `--batch` JSONL support
- **transition** — Add transition between segments
- **mask** — Apply mask (linear/circle/heart/etc.) with geometry flags; `--off` removes
- **bg-blur** — Background blur level 1-4; `--off` removes
- **text-style** — Style text: alpha, shadow, border, background box
- **text-anim** — Intro/outro/combo text animations
- **image-anim** — Intro/outro/combo image animations
- **mix-mode** — Set blend mode
- **audio-fade** — Fade in/out
- **crop** — Read/set source-material crop (`--ratio`, `--rect`, `--reset`)
- **matting** — Smart background removal
- **chroma** — Green-screen key (`--color`, `--intensity`); `--off` removes
- **text-ranges** — Byte-accurate multi-style ranges (`--styles @file.json`)
- **duplicate** — Duplicate segment onto track above
- **remove** — Remove segment + orphaned materials
- **prune** — Remove unreferenced materials
- **cut** — Extract time range into new standalone draft
- **batch** — Multiple edits from stdin JSONL, transactional

### Subtitles & Captions
- **caption** — Transcribe via whisper shell-out to real CapCut caption-track segments. Supports `--script`, `--karaoke`, `--style-ref`, `--preset`, `--highlight-words`, `--color-cycle`, `--max-chars/words/gap`
- **import-srt** — Import SRT/stdin as text segments per cue; supports `--style-ref`, `--clone-style`, `--time-offset`
- **import-ass** — Import ASS/SSA with inline overrides to per-range styles
- **export-srt** — Export to SRT or VTT (`--format vtt`, `--granularity line|word` for karaoke)
- **export-ass** — Styled ASS with per-range overrides and `--karaoke` word timing
- **export-timeline** — CapCut to OpenTimelineIO JSON for NLE handoff
- **import-timeline** — OTIO JSON to new draft (`--out`) or append (`--into`)

### Store / Registration
- **register** — Repair `draft_meta_info.json` + `root_meta_info.json` entry. `--materials` registers media. Plan-only by default; `--apply` writes with `.bak`.
- **rename** — Transactional folder rename + metadata path rewrite
- **relink** — Repair broken media paths (`--dir`, `--from/--to`, `--stage`)
- **replace-media** — Swap segment source keeping timing/effects. `--retime` adjusts duration.
- **sync-timelines** — Reconcile drifted mirrors from read-only `draft_content.json`. `--nested`, `--apply`, `--force-write`.
- **restore** — Undo from `.bak` or snapshot history (`--step N`, `--list`)

### Detection & Media Processing
- **detect-scenes** — ffmpeg scene-change detection; prints cuts + segments
- **detect-silence** — ffmpeg silence detection; prints silences + keep segments
- **detect-retakes** — Repeated-take detection via windowed word-similarity (`--window`, `--similarity`, `--min-words`)
- **render** — Low-res ffmpeg proxy preview; `--dry-run` returns plan without executing
- **translate** — Clone draft into another language via Anthropic API
- **migrate** — Schema version migrations (`--from-store`, `--like <project>`)
- **export** — EXPERIMENTAL UI-automated render queue (macOS)

### Utility
- **serve** — Stateless JSONL job queue (`--queue`, `--workers`, `--retries`, `--timeout`)
- **doctor** — Environment preflight (Node, whisper, ffmpeg, API key)
- **decrypt** — Detect JianYing 6.0+ encryption
- **enums** — List enum slugs by category
- **catalogue <query>** — Cross-category resource search
- **harvest-enums** — Learn store resource IDs into catalogue (`--sync`, `--add`)
- **templates** — List bundled templates
- **save-template** / **apply-template** — Extract/stamp reusable segment templates
- **make-preset** — Extract text styling as portable preset JSON
- **config** — Show resolved `.capcutrc` + effective defaults
- **describe** — Emit full command surface as JSON (machine-readable tool spec)
- **completions** — Generate shell completions (bash/zsh/fish)

---

## How capcut-cli Supports / Helps Clipnera

### 1. ASS / Karaoke Caption Generation (Clipnera IMPLEMENTATION_PLAN.md P1 #1)

capcut-cli has mature implementations with 100+ tests.

| Feature | capcut-cli file | Lines | How to port/use |
|---------|-----------------|-------|-----------------|
| Word-by-word karaoke | `caption.ts` | 146-210 | Creates one segment per word with `TextRangeInput` highlighting; `--color-cycle` rotates base color |
| ASS export with karaoke | `ass.ts` | full file | `cmdExportAss` renders `[Script Info]`, `[V4+ Styles]`, `[Events]` with `{\k}` word timing |
| Font scaling (em -> ASS) | `decorators.ts` | `DEFAULT_KEYWORD_SIZE`, `buildEmphasisRanges` | Multiplier on base font size, default 1.08x |
| Safe-area margins | `lint.ts` | `safeAreaFraction` option | Vertical safe zone from center outward (default 0.75) |
| Hook title pill | Not in capcut-cli | N/A | Use `add-text` with `--bg-style`, `--bg-color`, `--bg-alpha`, `--bg-round-radius` |

**Key algorithm** (`caption.ts:146-210`): karaoke mode creates one text segment per word, then sets a `TextRangeInput` highlighting only that word:
```typescript
const karaokeRange: TextRangeInput = {
  start, end,
  font_color: KARAOKE_HIGHLIGHT_COLOR,
  font_size: Number(cueStyle.font_size ?? 15) * 1.08,
  bold: true,
};
```

### 2. Caption Templates (Clipnera P1 #3)

| Feature | capcut-cli file | How to use |
|---------|-----------------|------------|
| Preset application | `preset.ts` | `applyTextPreset(draft, segId, preset)` — mirrors font, size, color, shadow, border, background box |
| Template application | `factory.ts` | `applyTemplate(draft, path, start, duration, {text, x, y})` — stamps a saved segment template |
| Preset extraction | `preset.ts` | `extractTextPreset` — `make-preset` extracts a segment's styling as portable JSON |
| Style fields | `factory.ts` | `STYLE_FIELDS` — 40+ fields (font_id, bold, italic, shadow_*, border_*, background_*, etc.) |

### 3. Phrase-Aware Segmentation (Clipnera P1 #2)

| Feature | capcut-cli file | How to port |
|---------|-----------------|-------------|
| Script-to-whisper alignment | `align.ts` | `alignScript(lines, recognizedWords)` produces `AlignmentReport` with match_ratio, matched, script_words |
| Cue grouping by constraints | `caption.ts:200+` | `groupWords(words, maxWords, maxChars, maxGapMs)` — groups by max words, max chars, max gap |
| Phrase segmentation | `caption.ts:106-119` | With `--script`: one cue per script line, split only at `> --max-chars` |
| Script matching warning | `index.ts` | `match_ratio < 0.5` triggers stderr warning |

### 4. Word-Snapping for Clip Boundaries (Clipnera P1 #4)

| Feature | capcut-cli file | How to port |
|---------|-----------------|-------------|
| Scene detection | `scenes.ts` | ffmpeg `select='gt(scene,T)'` filter, threshold 0.4, min-gap, limit |
| Silence detection | `silence.ts` | ffmpeg `silencedetect`, dBFS -30, min duration, pad |
| Retake detection | `retakes.ts` | Windowed word-sequence similarity, `--similarity 0.8`, `--min-words 4` |
| Time parsing | `time.ts` | `parseTimeInput` handles `+0.5s`, `1:30`, `500ms`, bare seconds |

### 5. Virality Scoring (Clipnera P2 #5)

capcut-cli does NOT have virality scoring, but has detection tools that feed scoring:

| Feature | capcut-cli file |
|---------|-----------------|
| Scene changes (hook candidates) | `scenes.ts` |
| Silence gaps (engagement drops) | `silence.ts` |
| Repeated takes (content quality) | `retakes.ts` |
| Caption overlap/gap (readability) | `lint.ts` — `caption-overlap`, `caption-gap-too-small` codes |

### 6. Emoji Annotations (Clipnera P2 #6)

| Feature | capcut-cli file | How to use |
|---------|-----------------|------------|
| Keyword highlighting | `index.ts:keywordEmphasisFromFlags` | `--highlight-words w1,w2,...` or `@file` with one word/phrase per line |
| Color cycling | `caption.ts` / `index.ts` | `--color-cycle #FF0000,#00FF00` rotates base color per cue |
| Rate limiting | (implicit) | One match per cue; `buildEmphasisRanges` returns match count |
| Case-insensitive matching | `decorators.ts:buildEmphasisRanges` | `word.toLowerCase()` comparison |

### 7. Pipeline Orchestration

| Feature | capcut-cli file |
|---------|-----------------|
| Declarative pipeline | `compile.ts` — `compileDraft(spec)` reads JSON spec with clips/segments/transitions |
| Job queue | `serve.ts` — stateless JSONL runner; `--workers`, `--retries`, `--timeout`, `--fail-fast` |
| Batch operations | `index.ts:cmdBatch` — transactional: each op runs against a clone; first failure aborts with no writes |

### 8. Testing Strategy

| Concern | capcut-cli approach |
|---------|---------------------|
| Test runner | `node:test` (Node.js built-in, no framework) |
| Build | `tsc` + `enums.json` copy to `dist/` |
| Fixtures | `test/fixtures/` with real CapCut draft JSON |
| Assertions | `node:assert/strict` — exact JSON shape comparisons |
| Pattern | Load fixture -> run command -> assert JSON output shape |

---

## Strategic Opportunities

### A. capcut-cli as an alternative output target
Instead of burning subtitles into MP4s, produce a **CapCut project file** where:
- Subtitles are editable text tracks (not baked pixels)
- Karaoke highlighting is native CapCut animations (word-by-word color)
- Caption styles are editable presets (not force_style strings)
- User can manually adjust timing, positioning in the GUI before final render

### B. capcut-cli as a reference library
`lib.ts` exports `loadDraft`, `saveDraft`, `lintDraft`, `detectVersion`,
`findSegment`, `extractText` — a pure TypeScript API for CapCut JSON
manipulation with mature schema types and write-safety logic.

### C. Cross-pollination of algorithms
- Scene/silence/retake detection: `scenes.ts` + `silence.ts` + `retakes.ts`
- ASS generation: `ass.ts` (200+ lines of battle-tested ASS rendering)
- Word alignment: `align.ts` solves the script-to-whisper problem
