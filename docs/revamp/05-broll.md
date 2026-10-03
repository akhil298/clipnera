# Clipnera UI revamp — Wave 4: the two B-roll libraries

Date: 3 October 2026. Branch `clipnera` at `38f9bd5`. Builds on [00-audit.md §6.2](00-audit.md), [01-experience-principles.md](01-experience-principles.md), [audit/06 §4](audit/06-reels-brand-social.md), [audit/07 §4](audit/07-settings-billing-admin.md) and [research/cardboard.md §7](research/cardboard.md).

This is the product and backend design for:

- **A. The Clipnera library.** Footage the company curates for every user, optionally tiered by plan.
- **B. Your library.** Each user's private uploads.

Both libraries share one search, one preview path, one way into the timeline, and one picker that the AI uses.

**Status of the contracts in this document.** The shapes are **provisional**. They are aligned with the two documents written at the same time:

- [architecture/backend.md](architecture/backend.md): envelope with `meta` for lists, error object, cursor pagination, job classes, `media_assets` and `/uploads`, CloudFront signed cookies, workspace tenancy, admin audit log.
- [06-flags.md](06-flags.md): flag definitions, remote-config keys, plan promises read through entitlements.

§7.1 records each alignment and what remains open.

Rules followed: documentation only, no repo file changed except this one; secrets are referred to by setting name only.

---

## 0. Decisions at a glance

| # | Decision | Why |
|---|---|---|
| D1 | **Keep `broll_assets` as the unit you search and place (one shot).** Add a parent `broll_sources` table (one row per file: a stock clip, an admin upload or a user upload). | Every existing consumer works on shot ids and keeps working: cutaways, reels, usage and swap signals, AI shots. Stock ingest already splits one clip into up to six shots that share `(source, source_id)` (`broll/ingest.py:209-231`). `broll_sources` gives that grouping a row of its own. |
| D2 | **One table for both libraries; the scope comes from ownership.** `owner_user_id IS NULL` is the Clipnera library. A set owner is a user's library, which belongs to a **workspace** (`workspace_id`, the uploader's personal workspace by default). This follows today's code (`broll/model.py:75-78`, `broll/repository.py:81`) and the workspace tenancy in [backend.md §8.2](architecture/backend.md). | No second search stack and no data copy. Tenant isolation lives in one repository predicate (§11). "Private by default" holds because the default workspace is personal. |
| D3 | **Semantic search uses text embeddings in pgvector inside the existing Postgres.** The text is title, tags, admin caption and an **AI-written visual caption** of each shot. Embeddings come from the hosted Gemini embedding model the code already calls (`broll/embeddings.py`), at 768 dimensions. | Cheapest path that also fixes the two real failures: queries with no shared keyword, and Hindi or Telugu queries. No new service, no GPU, no model in the API process. CLIP-style frame embeddings are deferred behind the same interface (§4.2). |
| D4 | **Search is hybrid.** Full-text and vector results are merged with reciprocal rank fusion, then re-scored with today's quality and swap-rate signals. | Today a query with no keyword overlap returns nothing even with embeddings on ([audit 06 §4.5](audit/06-reels-brand-social.md)). Keeping full text preserves exact-word precision. |
| D5 | **Auto-tagging reuses the 3×3 contact-sheet vision call** (`edit_engine/vision.py:1-6, 52-60, 76-94`). One call captions nine shots and returns caption, tags, mood, people, text or logos, and an NSFW flag. | About one ninth of the calls of per-frame tagging. It is already proven in footage reels and fills `has_people` and `has_logos`, which ingest never writes today ([audit 06 §4.1](audit/06-reels-brand-social.md)). |
| D6 | **New platform content goes to `in_review` before it goes live.** Existing live assets are grandfathered as live and flagged as never reviewed. | The brief asks for a review queue. Grandfathering keeps every existing placement and every search result as it is. |
| D7 | **Add a `retired` status**: hidden from search and from AI picks, but **existing placements keep rendering**. `blocked` and `taken_down` keep today's meaning (dropped from future renders, `broll/cutaways.py:205`). | Curation needs a soft "stop offering this" that doesn't change anyone's video. Takedown must stay hard. |
| D8 | **Library assets enter the editor's Timeline v1 unchanged, through a reference key `broll:<asset_id>`.** The Timeline asset id is `b_<asset_id>`. The renderer and the preview resolve the key server-side to the rendition that fits the project's aspect ratio. | No Timeline schema version bump and no change to the shared fixtures. Masters are never exposed (the policy at `broll/model.py:5-7`). A takedown is honoured at render time. |
| D9 | **Drag and drop goes through the existing ops endpoint.** The client builds `add_asset` + `add_item` from the `timeline_asset` that search returns. The server checks every `broll:` key for tenant and status. **The prompt path uses one composite agent tool, `place_broll`**, which writes the same ops plus a "why" record. | One mutation path (`POST /editor/projects/{id}/ops`, `editor/route.py:47-50`), so undo and versions cover both. The composite tool keeps model tokens and failure modes down. |
| D10 | **User uploads ride the generic upload and media pipeline** ([backend.md §6.2–6.3](architecture/backend.md)): `/uploads` with resume, `media_assets`, `media.probe`, `media.proxy` (540p, 1 s GOP), poster, sprite. The library adds only a thin init (quota, rights, duplicates) and a `broll`-class job that turns a ready media asset into library shots. **Originals above 1080p or a bitrate cap are replaced by a 1080p mezzanine** (remote config, on by default). Quota counts stored bytes. | One upload stack instead of a fourth bespoke one. The owner is cost-sensitive, and phone 4K originals are the main storage cost; the user keeps the original on their device. |
| D11 | **Quota is reserved at upload start**, atomically, in a per-workspace counter row (`library_storage`). | A quota can't be overrun mid-upload or by parallel tabs. The "quota exceeded mid-upload" case becomes a refusal at init with a clear message. |
| D12 | **Plan limits are remote-config keys marked `plan_promise`, read through entitlements** ([06-flags §5.3](06-flags.md)). Errors are plan error codes, so the existing upsell path handles them. | The brief asks for remote config. The audit and 06-flags keep entitlements and flags separate. |
| D13 | **Two flags: `broll_platform_library` and `broll_user_library`** (kind `release`, parent `broll_studio`, as catalogued in [06-flags §9.1](06-flags.md)). Turning either off hides its UI and stops new uploads or new picks. It **never** breaks an existing placement or export. | Kill switches must not damage users' work. |
| D14 | **Previews go through CloudFront `media.clipnera.com` with signed cookies** from `GET /media/session` ([backend.md §6.1](architecture/backend.md)). A CloudFront signed-cookie policy covers one resource pattern, and the workspace cookie covers `w/{workspace_id}/*`. So Clipnera library proxies are served from a second hostname, `library.media.clipnera.com` (same distribution, separate cookie domain). `/media/session` sets that cookie too, with policy `broll/*`. User-library files live under the workspace path. **Until that infrastructure ships**, the fallback is S3 presigned URLs with expiry rounded to a 15-minute bucket, so URLs are stable and cacheable. | Signed cookies suit grids of hundreds of hover previews: there are no per-URL signatures and the edge cache works. The fallback needs no new infrastructure. |
| D15 | **Admins don't browse users' private libraries.** Moderation shows only items that were flagged or reported. Curation needs the `content` admin role ([backend.md §8.3](architecture/backend.md)). Every admin mutation writes `admin_audit_log`. | Privacy. Today's admin list mixes private AI shots into the "library" (`broll/repository.py:122-131` has no owner filter), and today's status change records no actor (`broll/route.py:51-54`). |

---

## 1. Where we start

From the code, confirming [audit 06 §4](audit/06-reels-brand-social.md) and [audit 07 §4](audit/07-settings-billing-admin.md).

| Area | Today | Reference |
|---|---|---|
| Asset model | One row per shot. Kinds `stock / template / generated / user`; statuses `ingesting / live / blocked / taken_down / failed`; `owner_user_id` null means shared; `embedding` is `ARRAY(Float)` with no index | `broll/model.py:24-85` |
| Licence | 1:1 `broll_licenses` row with code, URL, author, attribution, `commercial_ok`, S3 copy of the source record | `broll/model.py:88-104` |
| Usage | `broll_usage` per placement, `swapped` as the quality signal | `broll/model.py:107-119`, `repository.py:106-116` |
| Ingest | Queued job `broll.ingest`. Downloads ≤300 MB, de-duplicates by SHA-256, gates on resolution and length, splits into ≤6 shots of ≤15 s, renders vertical/proxy/thumb, **inserts as `LIVE`** | `broll/service.py:28,48-50,158-162`, `ingest.py:182-231` (status at `:222`) |
| Renditions | 1080×1920 centre-crop master, 540×960 proxy, 360×640 thumb; audio stripped; vertical only | `broll/renditions.py:15-16,35-58,90-96` |
| Storage | `s3://{bucket}/broll/assets/{asset_id}/…` and `broll/records/{source}/{source_id}.json` | `ingest.py:139-149,202` |
| Search | FTS `websearch_to_tsquery('english')`, live only, owner null or caller, min duration, top 60 → Python re-score; cosine re-rank only if `EMBEDDINGS_PROVIDER="gemini"` (default `"none"`) | `repository.py:60-99`, `retrieval.py:86-128`, `core/config.py:125` |
| User search | `GET /broll/search` → at most 4 `BrollPreview`; shared library only; behind `broll_studio.cutaways` | `broll/route.py:29,92-98`, `service.py:133-136` |
| Placements | Clip cutaways stored as JSON on the clip (`Placement`), swap/remove/generate only | `cutaways.py:45-64`, `service.py:92-131` |
| Render | Downloads `vertical_key` of each live asset and overlays it; skips non-live silently; never fails the export | `cutaways.py:164-226` (status check `:205`) |
| Reels | Picks per scene with the same retriever (includes caller's private assets); renders from `vertical_key` | `reels/jobs.py:135-150,177-197` |
| AI shots | Veo, Pro, 120 credits, refunded on failure, daily quota; stored as private `generated` asset | `broll/generation.py:92-139`, `generation_job.py:20-34` |
| Admin | List/search/status filter, block/take down/restore, ingest by topic; no owner filter, no actor recorded | `broll/route.py:40-60`, `AdminBrollView.tsx:18-178` |
| Studio mock | Four Unsplash stills, no backend | `studio/panels/BrollPanel.tsx:9-30,81-98` |
| Uploads | Browser-to-S3 multipart: init → part URLs → complete → background probe; size and duration gates | `uploads/service.py:71-179`, `uploads/schema.py` |
| Jobs | `Job(kind, payload)`, in-process or SQS with heartbeat; handlers must be idempotent | `jobs/queue.py:1-11,31-59`, `jobs/worker.py:67-95` |
| Editor | Timeline v1 in frames; `Asset{id,kind,key,proxy,frames,width,height,has_audio}`; 13 ops incl. `add_asset`, `replace_asset`; versioned ops log with author | `editor/timeline.py:47-56`, `editor/ops.py:106-155`, `editor/service.py:57-79`, `editor/model.py:33-44` |
| Agent tools | `get_timeline`, `apply_edits` | `editor/agent_tools.py:79-85` |
| Account deletion | Deletes S3 prefixes `videos, clips, social, reels, payment screenshots` under `/{user_id}/` | `user/service.py:20-26,127-145` |

Two existing defects matter for this design:

1. **AI-shot files survive account deletion.** They live under `broll/assets/{asset_id}/` (`generation.py:105`, `ingest.py:142`), which is not in `USER_FILE_PREFIXES` (`user/service.py:20`). The DB row cascades away (`model.py:76-78`) and the files are orphaned. The user library phase must fix this (§10.9).
2. **Hand search excludes the user's private assets** (`service.py:133-136`), but auto-pick includes them (`cutaways.py:108-110`, `reels/jobs.py:141-143`). Once user uploads exist as assets, AI picks would start using them with no flag check and no rendition the renderer can read. Guarded in §8.6.

---

## 2. Vocabulary

| Term | Meaning | Table |
|---|---|---|
| **Source** | One file: a stock clip, an admin upload, a user upload, an AI shot | `broll_sources` (new) |
| **Shot** (asset) | A searchable, placeable span of a source. A stock shot has its own renditions; a user-upload shot points into its source's renditions | `broll_assets` (existing) |
| **Clipnera library** | Live shots with `owner_user_id IS NULL` | — |
| **Your library** | Shots whose source belongs to the user: uploads and AI shots | — |
| **Collection** | Named, ordered set of shots; platform (curated, may be featured) or personal | `broll_collections` |
| **Favourite** | A user's heart on a shot | `broll_favourites` |
| **Pick** | One AI choice of a shot for a timeline position, with its reasons and alternates | `broll_picks` (new) |

UI names: **"Clipnera library"**, **"Your uploads"**, **"AI shots"**, **"Favourites"**, **"Collections"**. The word "stock" is not shown to users; "Library" is the panel name. The landing's "real footage" line problem ([00 §7 #27](00-audit.md)) is the kind of claim this naming avoids.

---

## 3. Product design

### 3.1 Where the libraries appear

| Surface | What it shows | Flag |
|---|---|---|
| **Editor → Library panel** (left rail tab, beside Media) | Search, filters, tabs: Clipnera · Your uploads · Favourites · Collections. Drag to timeline; `+` adds at playhead | `broll_platform_library` (Clipnera tab), `broll_user_library` (Your uploads tab, upload). Both also need `agent_editor` |
| **Clip studio → B-roll tool** | Today's "AI cutaways" section unchanged, plus **"Search library"** using the new search in place of the 4-result search, plus "Add cutaway at playhead". The four Unsplash stills are removed only with the owner's confirmation (they are a visible control; [00 §8 #3](00-audit.md)) | `broll_studio.cutaways` (existing) + new flags for the richer search |
| **Image reel board** | Scene alternates as today, plus a search box per B-roll scene (the gap at `ReelsView.tsx:247`) | `broll_studio.reels` + `broll_platform_library` |
| **`/dashboard/library`** (new route) | Full-page library: browse, upload, storage meter, collections, trash | either flag; each tab hides on its own |
| **Prompt bar** | `/broll` slash command, Asset chip, "why this clip" line and swap on the result message ([01 §4, §13](01-experience-principles.md)) | `broll_platform_library` or `broll_user_library` |
| **Admin → B-roll** (`/admin/broll`) | Curation console (§3.6) | none (admin-only, available while user flags are off, as today: `broll/route.py:28`) |
| **Settings → Usage / Billing** | Storage meter and plan limits | `broll_user_library` |

### 3.2 The Clipnera library: user view

**Browse (empty query).** Featured collections as horizontal rows ("City at night", "Business & finance", "India"), then categories as chips, then "Popular this week" (from `broll_usage` with low swap rate). On Free, with tiering on, Pro-tier shots show a `ProLockBadge`. Clicking one opens the existing upgrade modal through `promptUpgrade(reason)` ([audit 07 §5.2](audit/07-settings-billing-admin.md)).

**Search.** One box. Placeholder: "Search footage — try 'drone shot of a city at night'". Results are ranked by meaning, not only words. A small "Matches by meaning" label appears when the top results came from vector recall with no keyword hit, so the user isn't puzzled by a tile that lacks their word.

**Tile.** Thumbnail at the shot's own aspect ratio (9:16, 1:1, 16:9; a masonry grid keeps rows tidy), duration badge bottom-right, lock badge if gated, heart on hover.
- **Hover:** after 150 ms the proxy plays muted in place ([01 §10](01-experience-principles.md)). Preload starts on pointer approach (`preload="none"` until then, as `AdminBrollView.tsx:23` already does).
- **Long user files:** horizontal pointer position scrubs a sprite strip instead.
- **Touch:** first tap previews, second tap opens details.
- **Keyboard:** focusable. Space toggles preview, Enter adds at playhead, F favourites.

**Details drawer.** Larger preview with play controls, title, tags, duration, resolution, orientation, mood, colour swatches. **Licence block**: author, licence name and link, attribution line with **Copy**, and "Use in your videos: yes. Download: not available — Clipnera library footage is only used inside your exports." **Similar shots** strip (vector neighbours). Actions: Add at playhead · Add to collection · Report a problem.

### 3.3 Your library: user view

**Upload.**
- Ways in: a drop zone on `/dashboard/library`, a drop onto the editor's Library panel, an **Upload** button, and a drop onto the prompt bar (01 §4's attach button routes video files here when the user library is on).
- Several files at once. Accepted: MP4, MOV, WebM, MKV, plus HEVC inside MP4/MOV (the same content types as `uploads/schema.py:7`). Images and audio are out of scope for this wave (owner question Q6).
- **First upload only:** a one-time rights confirmation. "I own this footage or have permission to use it." Stored per source as `rights_attested_at`, with the time of the first confirmation on the user row (§10.1).

**Upload tray** (global, in the shell; survives navigation; collapses to a pill in the header activity indicator from 01 §9):

| Row state | Shows | Actions |
|---|---|---|
| Checking | name, size | Cancel |
| Duplicate | "Already in your library as 'Beach run'" | Use existing · Upload anyway |
| Too big / too long / over quota | the limit and the plan | Upgrade · Free up space · Remove |
| Uploading | progress %, MB/s, time left | Pause · Cancel |
| Paused (offline or user) | "Paused — resumes when you're back online" | Resume · Cancel |
| Needs file again (after reload) | "Choose 'beach.mov' again to resume" | Choose file · Cancel |
| Processing | step text: "Preparing preview", "Finding shots", "Describing scenes" | — |
| Ready | thumbnail, "Ready · 6 shots" | Open · Add to project |
| Held | "Held for review" (§10.2) | Learn more |
| Failed | plain reason: "We couldn't read this video. Try MP4 or MOV." | Retry · Remove |

**Resumable, honestly stated.** Uploads use backend.md's resumable `/uploads` flow (the client keeps `upload_id` in IndexedDB; `GET /uploads/{id}` lists the parts S3 already has). Parts already uploaded survive a reload. The browser cannot re-read a file after a reload without the user choosing it again. On return, the tray lists unfinished uploads. Choosing the same file (matched by fingerprint, §10.6) resumes from the first missing part.

Up to 3 files upload at once, with 4 parts in flight per file. Concurrency is remote config.

**Your uploads grid.** Same tiles as the Clipnera library. A file is one tile; a **"6 shots"** badge expands it inline to its shots (moments), each a tile with its own caption. Search results show moments directly with "in Beach run · 0:42". Cardboard returns timestamped thumbnails for semantic hits the same way ([cardboard §7](research/cardboard.md)).

**Details drawer (own item).** Editable title and tags (AI tags shown as removable chips), shot list, technical details, size on storage, **Used in** (projects, with links), **Download** (the original, or the mezzanine if it was compacted; a signed attachment URL, backend.md §6.1), **Delete**.

**Storage meter.** In the library header and in Settings: "3.2 GB of 25 GB · 48 clips". Neutral below 80%, amber from 80%, rose at 100% with "Uploads paused — free up space or upgrade". Hovering shows a breakdown of uploads, AI shots and trash.

**Delete and trash.**
- Delete moves the item to **Recently deleted** for 30 days (remote config). The trash still counts against storage, so the dialog offers "Delete now" to free space at once.
- If the item is used: "Used in 2 projects. Those projects will show 'Missing clip' where it was. Videos you've already exported or published don't change." Buttons: Delete / Cancel.
- Restore puts it back.

**AI shots** appear in Your library under an "AI shots" filter. These are today's private Veo assets (`generation.py:107-115`). They count against storage at their rendition size.

### 3.4 Shared: search, filters, favourites, collections

**Filters** (chips row; on mobile, a bottom sheet):

| Filter | Values | Backed by |
|---|---|---|
| Orientation | Vertical · Square · Horizontal · **Fits this project** (default inside the editor) | `orientation` (existing) + project aspect (§5.2) |
| Duration | Any · <5 s · 5–10 s · 10–20 s · >20 s, or a range slider | `duration_s` |
| Resolution | Any · HD (≥720) · Full HD (≥1080) · 4K (≥2160), on the short side | `width`, `height` |
| Colour | Warm · Cool · Neutral · Black & white · Vivid, plus swatch pick | `color_family`, `dominant_colors` (§5.3) |
| Mood | Calm · Energetic · Dramatic · Hopeful · Dark · Playful · Professional | `mood` (vision call) |
| People | Any · With people · No people | `has_people` |
| Source | Clipnera library · Your uploads · AI shots, and per provider for admins | `owner_user_id`, `kind`, `source` |
| Licence (admin only, and an optional user toggle "No attribution needed") | per licence code | `broll_licenses.license_code` |

**Favourites.** A heart on any tile or drawer. Lists under the Favourites tab. Favourites are private. A taken-down favourite disappears; a retired one shows "No longer offered", still usable where already placed.

**Collections.**
- *Personal*: create, rename, delete, reorder, add from tile menu or by multi-select.
- *Platform*: curated by admins and shown as "Featured". Users can't edit them but can "Save a copy".
- A collection can be passed to the AI: "use B-roll from my 'Product shots' collection" resolves through the Asset chip (§8.4).

### 3.5 Inserting into the timeline

**Drag and drop.**
1. Drag a tile. The ghost shows the thumbnail and duration in timeline units.
2. Drop on an overlay track. If none exists, dropping on the empty area below the video track creates `overlay` track `broll` (`add_track`).
3. Snapping to playhead, markers and item edges.
4. On drop the client builds one batch, as one version (01 §3 "one prompt, one version" applied to hand edits):
   - `add_asset` (skipped if `b_<id>` is already in the project)
   - `add_item`: a clip at the drop frame
   - `src_in` = the shot's start and `src_out` = start + min(shot length, 4 s by default, remote config)
   - `volume` 0
   - `transition_in` fade, 4 frames

   It then posts the batch to the existing ops endpoint.
5. If the drop would overlap an item, the client nudges to the next free slot or asks to replace (overlap is refused by `editor/timeline.py:227-228`).

**Add at playhead.** `+` on a tile, or Enter, does the same at the playhead.

**Mobile.** No drag. The tile's action sheet has "Add at playhead" and "Add to…" (opens a time picker).

**Clip studio (non-Editor).** "Add cutaway at playhead" creates a new `Placement` on the clip's `broll_plan` through a new endpoint (§7.4). It is the counterpart of today's swap/remove (`service.py:92-112`). Exports pick it up unchanged (`cutaways.py:182-226`).

### 3.6 Admin curation console (`/admin/broll`)

Replaces `AdminBrollView` (REBUILD per [00 §5.6](00-audit.md)). Tabs:

| Tab | Purpose | Key interactions |
|---|---|---|
| **Library** | All Clipnera library shots (`owner_user_id IS NULL` only) | Grid ↔ table toggle. Facets: status, source, kind, category, tier, licence, commercial, orientation, resolution, duration, people/logos, reviewed or not, date added, swap rate. Multi-select (click, shift-click, "select all N matching"). Bulk bar: Approve · Retire · Block · Take down · Restore · Set tier · Add/remove tags · Set category · Add to collection |
| **Review queue** | Shots in `in_review` | Focus mode: big preview, AI suggestions (caption, tags, category, mood, flags) pre-filled and editable. Keys: **A** approve, **R** reject (reason picker), **E** edit, **J/K** next/prev, **T** set tier. Grid mode for batch approval. A counter in the tab |
| **Upload** | Admin uploads of company-owned or licensed footage | Same uploader as users, larger limits. A **licence form applied to the batch**: licence (from registry, §10.4), author, author URL, licence URL, commercial OK, attribution text, proof file (PDF or image of the licence or invoice), notes. Lands in review unless "Approve on upload" is ticked |
| **Ingest** | Stock provider ingest | Topic, sources (checkboxes, today's request already supports `sources`, `broll/schema.py:36-39`), per-source count 1–20. **Runs table**: topic, who, state, added/skipped/failed per source, errors, duration. Auto-refresh while running |
| **Categories & collections** | Taxonomy and featured rows | Tree of categories (two levels). Collections with drag ordering, cover shot, featured toggle and schedule (featured from/until) |
| **Moderation** | User content that was flagged or reported, and reports on Clipnera shots | Queue with reason, flags, reporter. Actions: Dismiss · Keep held · Release · Take down (with message to owner). **No browse of private libraries** (D15) |
| **Takedowns** | Legal log | Claim: claimant, contact, reference, date, assets, decision, who acted. Shows "affected projects" count from `broll_usage` |

**Asset drawer (admin).** Every field: title, caption, tags, category, tier, mood, colour, people/logos/text, quality score, orientation. The full licence record: every `broll_licenses` column, a signed link to the stored source record JSON (`source_record_key`), proof file, verified-by and when, and licence expiry. Usage: placements, swap rate (`repository.py:106-116`), last used. **History** from `broll_events`: who, what, when, reason. Status actions need a reason from a picker plus a note. This replaces `window.prompt` (`AdminBrollView.tsx:95`).

**Status meaning (shown in the console as a legend):**

| Status | In search and AI picks | Existing placements render | Files |
|---|---|---|---|
| `ingesting` | no | n/a | being made |
| `in_review` (new) | no | n/a | kept |
| `live` | yes | yes | kept |
| `retired` (new) | no | **yes** | kept |
| `rejected` (new) | no | n/a | deleted after 30 days; row kept so the same source isn't re-ingested (`repository.py:23-29`) |
| `blocked` | no | **no** (today's behaviour, `cutaways.py:205`) | kept |
| `held` (new, user items) | no (owner sees it with a banner) | no | kept |
| `taken_down` | no | **no** | deleted after the evidence period (remote config), record kept |
| `failed` | no | n/a | cleaned up |

### 3.7 States per screen

| Screen | Empty | Loading | Error | Mobile |
|---|---|---|---|---|
| Library panel, Clipnera tab | Can't be empty for users (featured rows). With no search results: "No shots match 'x'. Try fewer words, or describe what's on screen." plus 3 suggested queries from the nearest categories | Skeleton tiles at the expected aspect ratios; the first page renders progressively | "The library didn't load. Your project is safe." + Retry | 2-column grid; filters in a bottom sheet; preview on first tap |
| Your uploads | Illustrated drop zone: "Upload your own footage — it stays private to you." Limits shown below: "Up to 25 GB on Pro" | Skeletons; processing items show their step | Same pattern; upload errors stay per row in the tray | File picker; uploads continue while the screen is on. Background tabs can be throttled by the OS; stated in the tray |
| Favourites | "Tap ♥ on any clip to keep it here." | skeleton | as above | as above |
| Collections | "Group clips for a project or a series." + New collection | skeleton | as above | list view |
| Details drawer | n/a | preview poster first, metadata streaming in | "Couldn't load details." + Retry | full-screen sheet |
| Upload tray | hidden | per-row | per-row, with one action | full-width sheet from the bottom |
| Storage meter | "0 of 25 GB" | thin skeleton bar | hidden (never blocks the page) | in Settings |
| Admin review queue | "Nothing to review. New ingests and uploads appear here." | skeleton | banner + Retry | Admin works on tablet width and up; on phone, read-only list with Approve/Reject buttons |
| Admin ingest runs | "No ingests yet." | row skeleton | per-run error text | table → cards |

Every error follows 01 §8: what happened, what is still safe, one next action. No "Something went wrong".

### 3.8 Licence display and credits

- **Tiles:** none. **Drawer:** full licence block (§3.2).
- **Export dialog:** a "Credits" section appears when the export uses Clipnera library shots whose licence needs or recommends attribution (registry flag, §10.4). It lists them as a ready-to-paste block with **Copy**. This mirrors music credits on footage reels (`FootageReelBoard.tsx:192-199` per [audit 06 §4.6](audit/06-reels-brand-social.md)). The block is stored with the export so it can be shown again.
- **Publish composer:** optional "Add credits to the description" toggle. It is on by default when any used licence **requires** attribution (CC BY).
- **Pexels / NASA / CC0 / public domain:** no credit required. The credit line is still offered.
- Users never receive Clipnera library files. That policy is unchanged (`broll/model.py:5-7`, `service.py:65-67`).

---

## 4. Search and ranking

### 4.1 Requirements

- "drone shot of a city at night" finds aerial city-night shots even if they are tagged "skyline, evening, aerial".
- Hindi, Telugu and Hinglish queries work; Clipnera's users caption in those languages (`editor/timeline.py:165-166`).
- No GPU, no new paid service, small marginal cost, and nothing heavy loaded into the API process.
- Filters combine with relevance. Paging is stable.
- One search serves the UI, the AI agent, clip cutaways and reels.

### 4.2 Options considered

| Option | Index cost | Query cost | Quality on "what's on screen" | Multilingual | Ops burden | Verdict |
|---|---|---|---|---|---|---|
| **A. Text embeddings (hosted Gemini, 768-d) of title + tags + AI visual caption, in pgvector** | One embed per shot at ingest: ~80 tokens → about $0.000012 per shot at $0.15 per 1M input tokens ([Google](https://developers.googleblog.com/gemini-embedding-available-gemini-api/)). 100k shots ≈ **$1.20 once** | ~20 tokens per query ≈ $0.000003; 100k queries/month ≈ **$0.30** | Good, **because** the vision caption describes the frames | Yes; the model is multilingual | An extension in the existing DB | **Chosen** |
| B. CLIP frame embeddings on CPU (open-weights) | ~0.3–1 s CPU per frame, 3 frames per shot; 100k shots ≈ tens of CPU-hours on the worker | The text encoder must run on every query: torch plus ~300–600 MB RAM in the API, or a round-trip to a worker | Best for pure visual queries | Weak (English-centric CLIP), unless a multilingual variant is used | New heavy dependency, memory pressure on a small EC2 | Deferred. Revisit if evals show visual misses that captions don't fix |
| C. Hosted multimodal (image) embeddings | Per-image API price at ingest | Per query | Best | Varies | New provider, key, vendor lock | Deferred; same slot as B |
| D. Separate vector service (managed vector DB) | Like A | Like A plus network hop | Like A | Like A | A second datastore, a second bill, sync jobs | Rejected at this scale |
| E. Keep FTS plus today's optional re-rank | none | none | Poor; no recall without keyword overlap | English only (`'english'` config, `model.py:47`) | none | Kept as one half of hybrid |

**Why A works without CLIP.** The contact-sheet call (§5.3) turns each shot into a 10–20-word description of what is on screen. Embedding that text captures most visual queries at text-embedding prices. Cardboard's "find by what's on screen" ([cardboard §7](research/cardboard.md)) is matched in kind, not in depth. The `Embedder` protocol (`broll/embeddings.py:24-25`) lets B or C be added later as a second column without changing callers.

**Dimension and storage.** `gemini-embedding-001` defaults to 3,072 dimensions and supports 768 through output dimensionality, with the same price ([Google](https://developers.googleblog.com/gemini-embedding-available-gemini-api/)). At 768 × 4 bytes, 100k shots ≈ 300 MB plus the HNSW index. If pgvector ≥0.7 is available, `halfvec(768)` halves that. The request must pass `outputDimensionality: 768`; today's embedder sends no dimension (`embeddings.py:40-42`), so its vectors are 3,072-d and are re-made, not converted (§12).

**Where vectors live.** pgvector in the existing PostgreSQL. HNSW index with `vector_cosine_ops`. Filtered queries rely on pgvector ≥0.8 iterative index scans; on older versions, over-fetch k = 200 and filter. Availability of the extension on the production database is owner question Q1.

**Fallback.** If `EMBEDDINGS_PROVIDER = "none"` or the embed call fails, search runs FTS only. Results are still correct, just without semantic recall. The UI never errors because of embeddings.

### 4.3 The search document

For each shot, rebuilt whenever an input changes. `search_doc_version` tracks the recipe.

```
{title}. {admin caption}. Shows: {vision caption}. Mood: {mood}. Tags: {tags joined}. Category: {category names}.
```

- `search_text` (FTS input, existing column) gets the same text, so FTS improves too.
- For user-upload shots, add the file title and, if the file has speech, the shot's transcript words (a later step; owner question Q7 on transcription cost).

### 4.4 Retrieval algorithm (`broll/retrieval.py` grows; the API stays `find()` plus a new `search()`)

1. **Visibility and filters first**, as SQL predicates:
   - status `live`
   - owner null or the caller (§11.1)
   - tier ≤ the caller's plan when tiering is on
   - filters from §3.4
   - aspect fit for the project (§5.2)
2. **Two recalls**, each top 100:
   - (a) FTS with `websearch_to_tsquery` over the existing GIN index (`model.py:47`). Use `'simple'` config as well as `'english'` for non-English words (an expression index; §6.3).
   - (b) Vector cosine over HNSW with the embedded query.
3. **Fuse** with reciprocal rank fusion: `rrf = Σ 1/(k + rank)`, k = 60 (remote config).
4. **Re-score** the fused top 60 with today's signals, generalised from `retrieval.py:86-90`:

   `score = 0.45·rrf_norm + 0.20·coverage + 0.15·quality + 0.10·(1 − swap_rate) + 0.10·fit`

   `fit` rewards matching orientation and enough length for the requested duration. Weights are remote config so they can be tuned without a deploy.
5. **Scope preference** (§8.5) and **diversity**: no two shots of the same source in one result page's top 8. This generalises the reel rule at `retrieval.py:103-127`.
6. **Paging:** an opaque cursor encodes `(query hash, offset)`. Results past 300 aren't served; the UI says "Refine your search".

**Cutaways and reels keep their thresholds.** `good_match` (`cutaways.py:137-142`) and `MIN_COVERAGE` stay for automatic placement: a wrong shot is worse than none. Hybrid recall only widens the candidates; the bar to place is unchanged at launch, then tuned with evals (§13 B-roll eval set).

### 4.5 Latency budget

| Step | Target p50 |
|---|---|
| Query embedding (hosted) | ≤150 ms; cached by normalised query text for 24 h (in-process LRU at launch; Redis is not in the stack) |
| FTS + vector SQL | ≤60 ms at 100k rows |
| Re-score, sign preview URLs | ≤40 ms (URL signing is local HMAC) |
| **Total** | **≤250 ms** server; results stream as they arrive with no spinner (01 §3.1) |

Search-as-you-type fires after 250 ms idle and runs FTS-only until Enter or until 600 ms idle, then runs hybrid. This avoids an embed per keystroke.

---

## 5. Media pipeline

### 5.1 Renditions

| Rendition | Clipnera library (new ingests, made by `broll.ingest`) | Your uploads (made by the media pipeline, [backend.md §6.3](architecture/backend.md)) | Today (unchanged for existing) |
|---|---|---|---|
| `master.mp4` | Per shot, **source aspect**, long side ≤1920, H.264 CRF 20, no audio | the original from `media_assets.original_key`; or `mezzanine.mp4` when compacted (below) | — |
| `vertical.mp4` | Per shot, 1080×1920 (kept so cutaways and reels work unchanged) | — | per shot (`renditions.py:35-42`) |
| `mezzanine.mp4` | — | Only when the original is above 1080p or above `storage.user_library_compact_bitrate`: H.264 CRF 20, long side ≤1920, AAC 128k, faststart. The original is then deleted (D10) | — |
| `proxy.mp4` | Per shot, the backend's edit-proxy spec: 540p short side, 24 fps, CRF 28, **1 s GOP**, no audio | `media.proxy`: same spec, with AAC 64k | 540×960, no fixed GOP (`renditions.py:45-51`) |
| `thumb.jpg` / poster | Per shot, 360 on the short side | `media.poster` per file, plus one thumb per shot cut by the library job | 360×640 |
| `sprite.jpg` | — | `media` sprite per file, for hover scrub | — |

The 1 s GOP matters because the browser compositor seeks to arbitrary shot starts inside a file ([backend.md §6.3](architecture/backend.md)).

Cutaway and reel renders keep reading `vertical_key` (`cutaways.py:205-208`, `reels/jobs.py:196-197`). New code paths resolve through one function, `rendition_for(asset, aspect) -> (key, offset_s)`:

| Asset | Returns |
|---|---|
| Stock shot with `master_key` | `master_key`; the renderer crops via the Timeline `Transform` (`editor/timeline.py:59-70`) |
| Legacy stock shot (vertical only) | `vertical_key`, but **only for 9:16 projects**; such shots are filtered out of search for other aspects |
| User shot | the source's `mezzanine_key`, or else its media asset's `original_key`, with `offset_s = start_s` |

Before user shots may enter cutaways or reels, those renderers must call `rendition_for` rather than `vertical_key` (§8.6).

### 5.2 Aspect fit

Search takes `aspect` (`9:16 | 1:1 | 4:5 | 16:9`, the editor's `AspectRatio`, `editor/schema.py:17`). A shot fits if it has a source-aspect master and its centre crop to the target keeps ≥ 56% of the short side. Otherwise it fits only if it is a legacy vertical shot and the target is 9:16. "Fits this project" is the default filter inside the editor.

### 5.3 Enrichment (auto-tag)

The enrich step of `broll.index` takes up to 9 shots and makes one contact sheet: the sharpest frame per shot, via `edit_engine/vision.py:52-60`. One vision call, extending `PROMPT` (`vision.py:33-36`), asks per tile for JSON:

```json
{"n": 1, "caption": "aerial view of a lit city skyline at night", "tags": ["aerial","city","night","skyline"],
 "mood": "dramatic", "people": false, "text_or_logo": false, "nsfw": false}
```

- Mood is constrained to the fixed list in §3.4; anything else becomes null.
- Each call is recorded in the usage ledger, as `vision.py:84-86` already does, so cost is measured, not guessed. Owner question Q8 asks for the per-call price check.
- **Colour** is computed locally: 5-cluster k-means on the thumbnail (OpenCV, already a dependency, `ingest.py:19`). It gives `dominant_colors` (hex), `color_family` by hue and saturation rules, and `brightness`.
- Failure never blocks going live. The shot keeps provider tags and can still be found.

### 5.4 Job types (job class `broll`, [backend.md §3.2](architecture/backend.md); each handler idempotent per `jobs/queue.py:1-11`)

Submission follows backend.md §3.3: a `jobs` row plus an SQS message with ids only. Status reaches the UI as job events on the shared stream, never by polling.

| Kind | Class | Payload | Does | Idempotency | Retries |
|---|---|---|---|---|---|
| `broll.ingest` (existing, extended) | `broll` | `{run_id, query, per_source, sources, review}` | Today's ingest. New shots get `in_review` when `review` is set (default from remote config). Writes the master as well as the vertical. Updates `broll_ingest_runs`. Enqueues `broll.index` | `(source, source_id)` uniqueness (`model.py:46`) | a run finishes as `partial` on errors |
| `media.probe` → `media.proxy` / `media.poster` / sprite (backend.md, unchanged) | `media` | `{media_asset_id}` | Validation, probe, SHA-256, proxy, poster, sprite for a library upload, exactly as for any upload. `on_ready: {library: {source_id}}` hands over to the next job | backend.md §3.3 | backend.md |
| `broll.library_ready` (new) | `broll` | `{source_id}` | Duplicate check on the full hash (§10.6). Optional compaction to mezzanine (D10). Shot detection (`shot_ranges`, `ingest.py:72-93`; for user files cap 60 shots, windows ≤15 s), shot thumbs, shot rows. Settles quota (`reserved` → `used`). Sets the source `ready`. Enqueues `broll.index` | `broll_sources.state` plus per-step checks | ×3, then source `failed` with a plain reason and the reservation released |
| `broll.index` (new; name from backend.md §3.2) | `broll` | `{asset_ids ≤ 100, steps: ["enrich","embed"]}` | **enrich** in groups of 9 (§5.3); **embed**: build the search doc, embed in one batch (`embeddings.py:35-45` already batches 100), write `text_embedding` and `search_doc_version` | skip shots with `enriched_at` set and a current `search_doc_version` | ×3; a failed enrich leaves the shot findable by its provider tags |
| `broll.backfill` (new, one-off) | `broll` | `{step, after_id}` | Pages through existing rows: create `broll_sources`, infer categories, enqueue `broll.index` | cursor `after_id` | resumable |
| `broll.sweep` (new, scheduled hourly by the scheduler service, backend.md §2.1) | `broll` | `{}` | Release expired reservations. Purge trash past retention. Delete files of rejected and taken-down items past retention. Retire shots whose licence expired. Recompute `library_storage` drift | time-based | — |
| `broll.generate` (existing) | `broll` | unchanged | AI shot. **Change:** store files under the workspace path (§10.9) and create a `broll_sources` row | unchanged | unchanged |

**CPU budget.** Library uploads use the shared `media` pool, so a burst of uploads competes with project uploads and not with renders. The compaction encode is the heaviest library-only step: a 10-minute 4K phone clip takes ~0.5–1× realtime at `veryfast` on 2 vCPUs. The daily upload-minutes cap (§9.2) and backend.md's per-user in-flight cap per class (`jobs.max_in_flight_per_user.<class>`) bound it. The `broll` class is low priority and scales to zero (backend.md §3.2).

### 5.5 Delivery (hover previews)

- **Target:** CloudFront signed cookies (D14).
  - User-library files are stored under `w/{workspace_id}/broll/{source_id}/…`, the `broll` area of backend.md §6.1.
  - Clipnera library files stay under `broll/assets/{asset_id}/…` (`ingest.py:142`) and are served from `library.media.clipnera.com`.
  - Proxies, thumbs and sprites are immutable per asset id: `Cache-Control: max-age=31536000, immutable`.
- **Fallback until 12.4 ships:** S3 presigned GET URLs as today (`service.py:65-67`). Expiry is set to **the end of the current 15-minute window plus 45 minutes**, so every request in a window gets the identical URL and browser caching works. Remote config `broll.preview.url_ttl_seconds` = 3600.
- **Loading:** thumbnails load at 1× and 2× from the one small file. **Proxies** load on hover intent only.

---

## 6. Data model

SQLAlchemy 2.0 style, matching `broll/model.py`. New columns on existing tables are nullable or have server defaults, so the migrations are additive and every existing reader keeps working.

### 6.1 Changes to existing tables

```python
# broll/model.py

class AssetStatus(str, enum.Enum):
    INGESTING = "ingesting"
    IN_REVIEW = "in_review"      # new
    LIVE = "live"
    RETIRED = "retired"          # new: hidden from search and picks; placements still render
    REJECTED = "rejected"        # new
    HELD = "held"                # new: user item held by moderation
    BLOCKED = "blocked"
    TAKEN_DOWN = "taken_down"
    FAILED = "failed"

# Statuses an existing placement may still render from (cutaways.py:205 today checks == live).
RENDERABLE = frozenset({AssetStatus.LIVE, AssetStatus.RETIRED})


class BrollAsset(Base):            # existing columns unchanged; additions below
    __tablename__ = "broll_assets"
    __table_args__ = (
        UniqueConstraint("source", "source_id", "shot_index", name="uq_broll_assets_source_shot"),
        Index("ix_broll_assets_search", text("to_tsvector('english', search_text)"), postgresql_using="gin"),
        Index("ix_broll_assets_search_simple", text("to_tsvector('simple', search_text)"), postgresql_using="gin"),  # new
        Index("ix_broll_assets_status_orientation", "status", "orientation"),
        Index("ix_broll_assets_owner_status", "owner_user_id", "status"),                                          # new
        Index("ix_broll_assets_ws_status", "workspace_id", "status"),                                              # new
        Index("ix_broll_assets_tags", "tags", postgresql_using="gin"),                                             # new
        Index("ix_broll_assets_review", "status", "created_at", postgresql_where=text("status = 'in_review'")),     # new
        Index("ix_broll_assets_embedding_hnsw", "text_embedding", postgresql_using="hnsw",                         # new
              postgresql_with={"m": 16, "ef_construction": 64}, postgresql_ops={"text_embedding": "vector_cosine_ops"}),
    )

    # --- new ---
    source_ref_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("broll_sources.id", ondelete="CASCADE"), nullable=True, index=True,
    )  # NOT NULL after backfill (migration M7)
    workspace_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=True,
    )  # copied from the source; null for the Clipnera library
    tier: Mapped[str] = mapped_column(String(10), default="free", server_default="free", nullable=False)  # free | pro
    master_key: Mapped[str | None] = mapped_column(String(500), nullable=True)   # source-aspect master (new ingests)
    vision_caption: Mapped[str | None] = mapped_column(Text, nullable=True)
    mood: Mapped[str | None] = mapped_column(String(20), nullable=True)
    color_family: Mapped[str | None] = mapped_column(String(12), nullable=True)  # warm|cool|neutral|mono|vivid
    dominant_colors: Mapped[list[str]] = mapped_column(ARRAY(String(7)), default=list, server_default="{}", nullable=False)
    brightness: Mapped[float | None] = mapped_column(Float, nullable=True)
    has_text: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    nsfw: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    enriched_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    text_embedding: Mapped[list[float] | None] = mapped_column(Vector(768), nullable=True)  # pgvector.sqlalchemy
    search_doc_version: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    reviewed_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # `embedding` (ARRAY(Float)) stays until retrieval reads text_embedding, then is dropped (M7).


class BrollLicense(Base):          # additions
    verified_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)   # licence end, if any
    proof_key: Mapped[str | None] = mapped_column(String(500), nullable=True)      # admin-uploaded licence proof
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class BrollUsage(Base):            # additions
    editor_project_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("editor_projects.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    surface: Mapped[str] = mapped_column(String(20), default="cutaway", server_default="cutaway", nullable=False)
    # cutaway | reel | editor
```

`pgvector` (Python package) becomes a dependency for the `Vector` type. It is not in `backend/requirements.txt` today.

### 6.2 New tables

```python
class SourceState(str, enum.Enum):
    UPLOADING = "uploading"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class BrollSource(Base):
    """One file: a stock clip, an admin or user upload, or an AI shot. Shots (BrollAsset) hang off it.

    User and admin uploads point at a media_assets row (backend.md §7.3), which owns the
    original, proxy, poster and sprite keys; this row adds what only the library needs.
    """

    __tablename__ = "broll_sources"
    __table_args__ = (
        UniqueConstraint("provider", "provider_id", name="uq_broll_sources_provider"),
        Index("uq_broll_sources_ws_hash", "workspace_id", "content_hash", unique=True,
              postgresql_where=text("workspace_id IS NOT NULL AND content_hash IS NOT NULL AND deleted_at IS NULL")),
        Index("ix_broll_sources_ws_created", "workspace_id", "created_at"),
        Index("ix_broll_sources_fingerprint", "workspace_id", "fingerprint"),
        Index("ix_broll_sources_purge", "purge_after", postgresql_where=text("purge_after IS NOT NULL")),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    # Null: the Clipnera library. Set: the library of that workspace (the personal one by default).
    workspace_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=True)
    # Who uploaded or paid for it; mirrors BrollAsset.owner_user_id, which existing code filters on.
    owner_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    media_asset_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("media_assets.id", ondelete="SET NULL"), nullable=True)
    kind: Mapped[AssetKind] = mapped_column(_enum(AssetKind, "broll_asset_kind"), nullable=False)  # stock|template|generated|user
    provider: Mapped[str] = mapped_column(String(40), nullable=False)         # pexels|nasa|wikimedia|pixabay|veo|upload|admin_upload
    provider_id: Mapped[str] = mapped_column(String(200), nullable=False)     # stock id, or this row's id for uploads
    title: Mapped[str] = mapped_column(String(300), default="", nullable=False)
    state: Mapped[SourceState] = mapped_column(_enum(SourceState, "broll_source_state"), default=SourceState.READY, nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)            # plain-language reason for the user
    stored_bytes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)  # original-or-mezzanine + renditions; what quota counts
    reserved_bytes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)  # held from init until ready/failed
    quota_exempt: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)  # pre-migration AI shots (§12)
    duration_s: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    width: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    height: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    has_audio: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)   # SHA-256 of the full file (media_assets.sha256)
    fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)    # quick client fingerprint (§10.6)
    mezzanine_key: Mapped[str | None] = mapped_column(String(500), nullable=True) # set when the original was compacted (D10)
    rights_attested_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    purge_after: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)


class BrollCategory(Base):
    __tablename__ = "broll_categories"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    slug: Mapped[str] = mapped_column(String(60), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    parent_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("broll_categories.id", ondelete="SET NULL"), nullable=True)
    sort: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)


class BrollAssetCategory(Base):
    __tablename__ = "broll_asset_categories"
    asset_id: Mapped[str] = mapped_column(String(36), ForeignKey("broll_assets.id", ondelete="CASCADE"), primary_key=True)
    category_id: Mapped[str] = mapped_column(String(36), ForeignKey("broll_categories.id", ondelete="CASCADE"), primary_key=True, index=True)
    # "admin" once a person confirms; "inferred" from backfill or the vision call.
    origin: Mapped[str] = mapped_column(String(10), default="admin", nullable=False)


class BrollCollection(Base):
    __tablename__ = "broll_collections"
    __table_args__ = (Index("ix_broll_collections_featured", "is_featured", "sort", postgresql_where=text("owner_user_id IS NULL")),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    owner_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)  # null = Clipnera curated
    workspace_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=True)  # reserved
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    cover_asset_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("broll_assets.id", ondelete="SET NULL"), nullable=True)
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    featured_from: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    featured_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    sort: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)


class BrollCollectionItem(Base):
    __tablename__ = "broll_collection_items"
    collection_id: Mapped[str] = mapped_column(String(36), ForeignKey("broll_collections.id", ondelete="CASCADE"), primary_key=True)
    asset_id: Mapped[str] = mapped_column(String(36), ForeignKey("broll_assets.id", ondelete="CASCADE"), primary_key=True, index=True)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    added_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)


class BrollFavourite(Base):
    __tablename__ = "broll_favourites"
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    asset_id: Mapped[str] = mapped_column(String(36), ForeignKey("broll_assets.id", ondelete="CASCADE"), primary_key=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)


class BrollEvent(Base):
    """Append-only history of every curation and moderation action (who, what, why)."""
    __tablename__ = "broll_events"
    __table_args__ = (Index("ix_broll_events_asset_created", "asset_id", "created_at"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    asset_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("broll_assets.id", ondelete="SET NULL"), nullable=True)
    source_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("broll_sources.id", ondelete="SET NULL"), nullable=True, index=True)
    actor_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    actor: Mapped[str] = mapped_column(String(40), nullable=False)       # "admin", "user", "system:enrich", "system:backfill"
    action: Mapped[str] = mapped_column(String(40), nullable=False)      # approve|reject|retire|block|take_down|restore|edit|hold|release|grandfathered
    from_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    to_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    reason: Mapped[str | None] = mapped_column(String(40), nullable=True)   # from a fixed list
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    details: Mapped[str] = mapped_column(Text, default="{}", nullable=False)  # JSON: changed fields, claim ref
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)


class BrollReport(Base):
    __tablename__ = "broll_reports"
    __table_args__ = (Index("ix_broll_reports_open", "state", "created_at"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    asset_id: Mapped[str] = mapped_column(String(36), ForeignKey("broll_assets.id", ondelete="CASCADE"), nullable=False, index=True)
    reporter_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    origin: Mapped[str] = mapped_column(String(20), nullable=False)   # user_report | auto_flag | rights_claim
    reason: Mapped[str] = mapped_column(String(30), nullable=False)   # wrong_tags|low_quality|offensive|copyright|nsfw|other
    note: Mapped[str] = mapped_column(Text, default="", nullable=False)
    claimant: Mapped[str | None] = mapped_column(String(300), nullable=True)   # for rights claims
    state: Mapped[str] = mapped_column(String(12), default="open", nullable=False)  # open | resolved | dismissed
    resolved_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)


class BrollIngestRun(Base):
    __tablename__ = "broll_ingest_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    query: Mapped[str] = mapped_column(String(200), nullable=False)
    sources: Mapped[list[str]] = mapped_column(ARRAY(String(40)), default=list, nullable=False)
    per_source: Mapped[int] = mapped_column(Integer, nullable=False)
    review: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    requested_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    state: Mapped[str] = mapped_column(String(12), default="queued", nullable=False)  # queued|running|done|partial|failed
    added: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    skipped: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    errors: Mapped[str] = mapped_column(Text, default="[]", nullable=False)   # JSON list, from IngestReport.errors
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)


class LibraryStorage(Base):
    """Per-workspace counters for atomic quota checks; recomputable from broll_sources (broll.sweep fixes drift).
    The quota itself is the plan of the workspace owner (plans belong to users today, audit 07 §5.4)."""
    __tablename__ = "library_storage"
    workspace_id: Mapped[str] = mapped_column(String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), primary_key=True)
    used_bytes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    reserved_bytes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    items: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    upload_seconds_today: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    upload_day: Mapped[date | None] = mapped_column(Date, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)


class BrollPick(Base):
    """An AI choice of a shot for one timeline item: what it chose, why, and what else it considered."""
    __tablename__ = "broll_picks"
    __table_args__ = (Index("ix_broll_picks_project_item", "editor_project_id", "item_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    editor_project_id: Mapped[str] = mapped_column(String(36), ForeignKey("editor_projects.id", ondelete="CASCADE"), nullable=False)
    item_id: Mapped[str] = mapped_column(String(40), nullable=False)       # Timeline item id
    version: Mapped[int] = mapped_column(Integer, nullable=False)          # project version the pick produced
    query: Mapped[str] = mapped_column(String(200), nullable=False)
    asset_id: Mapped[str] = mapped_column(String(36), ForeignKey("broll_assets.id", ondelete="CASCADE"), nullable=False)
    reasons: Mapped[str] = mapped_column(Text, default="[]", nullable=False)        # JSON list of reason codes + text
    alternates: Mapped[list[str]] = mapped_column(ARRAY(String(36)), default=list, nullable=False)
    swapped_to: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
```

### 6.3 Migrations

Revision ids are placeholders after the latest head `20261003010000` (`alembic/versions/20261003010000_add_editor_projects.py`). Other Wave 6 work may add revisions in between, so re-chain `down_revision` at build time.

| # | Revision | Content | Notes |
|---|---|---|---|
| M1 | `…_add_pgvector` | `CREATE EXTENSION IF NOT EXISTS vector` | Needs a role allowed to create extensions (`rds_superuser` on RDS). Downgrade: no-op (other objects may depend on it) |
| M2 | `…_extend_broll_status` | `ALTER TYPE broll_asset_status ADD VALUE IF NOT EXISTS 'in_review' / 'retired' / 'rejected' / 'held'` inside `op.get_context().autocommit_block()` | New enum values can't be used in the same transaction. Downgrade: documented no-op |
| M3 | `…_add_broll_sources` | Create `broll_source_state` and `broll_sources` (FK to `media_assets` once that table exists; otherwise added in a follow-up); add `broll_assets.source_ref_id`; **backfill**: one source per distinct `(source, source_id)` (title, provider, dims and `content_hash` from shot 0, owner from the shots, workspace = owner's personal workspace), then `UPDATE broll_assets SET source_ref_id` | Pure SQL, set-based; tens of thousands of rows run in seconds. Asset ids untouched |
| M4 | `…_add_broll_curation` | Asset columns (tier … reviewed_at), licence columns, usage columns; tables categories, asset_categories, collections, collection_items, favourites, events, reports, ingest_runs; `simple` FTS, tags GIN, owner_status, review partial index. Seed categories from `broll/seed.py` (11) | One `grandfathered` event per live asset |
| M5 | `…_add_broll_text_embedding` | `text_embedding vector(768)`; HNSW index built with `CREATE INDEX CONCURRENTLY` in an autocommit block **after** backfill embeds (or right away on an empty column; HNSW builds incrementally) | `halfvec` if pgvector ≥0.7 (decide at build from Q1) |
| M6 | `…_add_library_storage_and_picks` | `library_storage` (keyed by workspace), `broll_picks`, `broll_assets.workspace_id` + backfill from the owner's personal workspace | Follows backend.md 12.6's workspace backfill pattern (batched, outside the DDL transaction) |
| M7 | `…_finalise_broll_sources` (after the backfill job completes in production) | `source_ref_id SET NOT NULL`; drop `broll_assets.embedding` (ARRAY) | Separate deploy; guarded by a check that no nulls remain |

Every new model module is imported where Alembic's `env.py` gathers metadata, following the existing pattern. Per AGENTS.md, migrations ship in the same change as the model.

---

## 7. API contracts (provisional)

### 7.1 Conventions and alignment

Aligned with [backend.md §11–12](architecture/backend.md) and [06-flags.md §3.7, §5](06-flags.md):

- **Envelope.**
  - Success is `{data, message, error: null}`, plus `meta: {next_cursor, has_more}` on lists.
  - Failure is `{data: null, message, error: {code, message, details, request_id, retryable}}`.
  - The routes below return `ApiResponse[T]` (`core/responses.py:17-24`); `ok()` gains `meta` per backend.md.
- **Lists** return `data: T[]` and paginate by cursor: `?limit=` (default 30, max 100 there; **library search caps at 60**) and `?cursor=` (opaque, HMAC-signed).
  - Search cursors encode `(query hash, rank offset)`, not a keyset, because results are ranked. This is the one exception to backend.md's keyset rule, and it is still opaque and signed.
  - Admin lists keep `limit` / `offset` + `total` for one release, as backend.md §11.3 allows, so the current `AdminBrollView` keeps working (`broll/schema.py:31-33`).
- **Status and error codes used here.** Existing codes are reused where they fit. The new ones, marked *new*, are added to the documented `ErrorCode` set.

  | Situation | Status · code | `details` |
  |---|---|---|
  | Flag off | 403 `FEATURE_DISABLED` | `{feature}` |
  | Clipnera shot above the user's tier | 403 `PRO_REQUIRED` | `{feature: "broll_pro_library"}` |
  | Another workspace's item, purged item | 404 `NOT_FOUND` | — |
  | File too large for the plan | 413 `UPLOAD_TOO_LARGE` (plan error, 06-flags §5.3) | `{limit_bytes}` |
  | File too long for the plan | 403 `DURATION_NOT_ENTITLED` (existing, `uploads/service.py:126-138`) | `{limit_seconds}` |
  | Storage or item quota would be exceeded | 403 `STORAGE_QUOTA_EXCEEDED` (named in 06-flags §5.3; plan error → upsell) | `{quota_bytes, used_bytes, reserved_bytes, needed_bytes}` |
  | Daily upload minutes used up | 429 `LIMIT_REACHED` | `{limit: "library.upload_seconds_per_day", used, allowed}` |
  | Rights box not ticked | 422 `VALIDATION_FAILED` | `[{field: "body.rights_confirmed", issue: "required", message}]` |
  | `broll:` key not usable in an editor op | 422 `ASSET_NOT_AVAILABLE` (*new*) | `{op_index, asset_id, reason}` |
  | Timeline item locked by a run | 423 `ITEM_LOCKED` (backend.md) | — |
  | Editor version moved on | 409 `STALE_VERSION` (existing) | `{version}` |
  | Restore after purge | 404 `NOT_FOUND` | — |
  | Too many reports or searches | 429 `RATE_LIMITED` | `Retry-After` |

- **Headers.** `Idempotency-Key` on the upload init, collection create, placement create and swap POSTs. `client_batch_id` on hand-edit ops batches (backend.md §12).
- **Flags and access.** Flags are read through `RemoteConfig` (backend.md §9.2, 06-flags §3); plan limits through entitlements (06-flags §5.3). On the client, one `useAccess(feature)` helper (06-flags §3.7) decides between hiding a control (flag) and showing a lock (plan).
- **Dates.** ISO 8601 strings in TypeScript, `datetime` in Pydantic, as the existing B-roll types do.

New Pydantic models live in `broll/schema.py`; library routes go in a new `broll/library_route.py`. The TypeScript mirrors go in a new `frontend/lib/api/broll.ts`, or in `lib/api.ts` next to the existing B-roll types (`lib/api.ts:1975-2090`) if Wave 3 hasn't split `api.ts`. Names match field for field.

### 7.2 Shared shapes

```python
# broll/schema.py (new models)
from typing import Literal
from pydantic import BaseModel, Field

Scope = Literal["platform", "mine"]
Orientation = Literal["portrait", "landscape", "square"]
Aspect = Literal["9:16", "1:1", "4:5", "16:9"]
Mood = Literal["calm", "energetic", "dramatic", "hopeful", "dark", "playful", "professional"]
ColorFamily = Literal["warm", "cool", "neutral", "mono", "vivid"]
LibraryKind = Literal["stock", "upload", "generated"]
Tier = Literal["free", "pro"]


class LicenceInfo(BaseModel):
    code: str                                # registry key: pexels | pd_us_gov | cc0 | public_domain | cc_by | ai_generated | owned | licensed
    name: str                                # "Pexels License", "CC BY 4.0"
    url: str | None
    author: str | None
    author_url: str | None
    attribution_text: str | None
    attribution_required: bool
    commercial_ok: bool


class TimelineAssetRef(BaseModel):
    """Ready to send as the `asset` of an editor add_asset op (mirrors editor.timeline.Asset)."""
    id: str                                  # "b_<asset_id>"
    kind: Literal["video"]
    key: str                                 # "broll:<asset_id>"
    proxy: str | None                        # "broll:<asset_id>:proxy"
    frames: int                              # at the project's fps
    width: int | None
    height: int | None
    has_audio: bool


class LibraryItem(BaseModel):
    """One shot as a user sees it in a grid."""
    id: str
    scope: Scope
    kind: LibraryKind
    title: str
    caption: str | None                      # vision caption, for alt text and the "why" line
    duration_s: float
    start_s: float                           # into its source (0 for stock shots)
    source_id: str                           # broll_sources.id (groups moments of one upload)
    source_title: str | None                 # file title for user moments
    width: int
    height: int
    orientation: Orientation
    mood: Mood | None
    color_family: ColorFamily | None
    tier: Tier
    locked: bool                             # tier above the caller's plan
    favourite: bool
    thumb_url: str | None
    proxy_url: str | None
    sprite_url: str | None
    licence: LicenceInfo | None              # null for the caller's own uploads
    timeline_asset: TimelineAssetRef | None  # present when `aspect`/`fps` were given and the shot fits
    match: Literal["keyword", "meaning", "both"] | None   # only on search results


class LibrarySearchQuery(BaseModel):         # GET query params
    q: str | None = Field(None, max_length=200)
    scope: Literal["all", "platform", "mine"] = "all"
    kind: list[LibraryKind] | None = None
    orientation: list[Orientation] | None = None
    aspect: Aspect | None = None             # "fits this project"
    fps: Literal[24, 25, 30, 60] | None = None
    min_duration: float | None = Field(None, ge=0, le=600)
    max_duration: float | None = Field(None, ge=0, le=3600)
    min_short_side: int | None = Field(None, ge=0, le=4320)
    mood: list[Mood] | None = None
    color: list[ColorFamily] | None = None
    people: bool | None = None
    category: str | None = Field(None, max_length=60)   # slug
    collection_id: str | None = None
    favourites: bool = False
    attribution_free: bool = False
    cursor: str | None = None
    limit: int = Field(30, ge=1, le=60)                    # cursor/limit per backend.md §11.3
```

```ts
// frontend/lib/api/broll.ts (or lib/api.ts) — mirrors broll/schema.py
export type LibraryScope = 'platform' | 'mine';
export type Orientation = 'portrait' | 'landscape' | 'square';
export type Aspect = '9:16' | '1:1' | '4:5' | '16:9';
export type Mood = 'calm' | 'energetic' | 'dramatic' | 'hopeful' | 'dark' | 'playful' | 'professional';
export type ColorFamily = 'warm' | 'cool' | 'neutral' | 'mono' | 'vivid';
export type LibraryKind = 'stock' | 'upload' | 'generated';
export type Tier = 'free' | 'pro';

/** List responses carry `meta` beside `data` (backend.md §11.1). */
export interface ListMeta { next_cursor: string | null; has_more: boolean; }

export interface LicenceInfo {
  code: string; name: string; url: string | null; author: string | null; author_url: string | null;
  attribution_text: string | null; attribution_required: boolean; commercial_ok: boolean;
}

/** Same shape as Asset in lib/editor/timeline.ts, narrowed. */
export interface TimelineAssetRef {
  id: string; kind: 'video'; key: string; proxy: string | null; frames: number;
  width: number | null; height: number | null; has_audio: boolean;
}

export interface LibraryItem {
  id: string; scope: LibraryScope; kind: LibraryKind; title: string; caption: string | null;
  duration_s: number; start_s: number; source_id: string; source_title: string | null;
  width: number; height: number; orientation: Orientation; mood: Mood | null; color_family: ColorFamily | null;
  tier: Tier; locked: boolean; favourite: boolean;
  thumb_url: string | null; proxy_url: string | null; sprite_url: string | null;
  licence: LicenceInfo | null; timeline_asset: TimelineAssetRef | null;
  match: 'keyword' | 'meaning' | 'both' | null;
}

export interface LibrarySearchQuery {
  q?: string; scope?: 'all' | 'platform' | 'mine'; kind?: LibraryKind[]; orientation?: Orientation[];
  aspect?: Aspect; fps?: 24 | 25 | 30 | 60; min_duration?: number; max_duration?: number; min_short_side?: number;
  mood?: Mood[]; color?: ColorFamily[]; people?: boolean; category?: string; collection_id?: string;
  favourites?: boolean; attribution_free?: boolean; cursor?: string; limit?: number;
}
```

### 7.3 User endpoints (`/api/v1/library`)

Each route declares its flag with `require_flag(...)`. Search with `scope=all` needs at least one of the two flags; the service drops the scope whose flag is off.

| Method & path | Request | Response `data` | Errors | Flag |
|---|---|---|---|---|
| `GET /library/search` | `LibrarySearchQuery` | `list[LibraryItem]` + `meta` | 422 `VALIDATION_FAILED` | either |
| `GET /library/browse` | — | `LibraryBrowse` | — | `broll_platform_library` |
| `GET /library/items/{asset_id}` | — | `LibraryItemDetail` | 404 `NOT_FOUND` (also for others' private items — never 403, to avoid confirming existence) | either |
| `GET /library/media` | `?refs=broll:<id>,…&fps=30` (≤100) | `list[MediaRef]` | 404 per missing ref is omitted, not raised | either |
| `PUT /library/favourites/{asset_id}` | — | `{favourite: true}` | 404 | either |
| `DELETE /library/favourites/{asset_id}` | — | `{favourite: false}` | — | either |
| `GET /library/collections` | `?scope=mine\|featured` | `list[CollectionSummary]` | — | either |
| `POST /library/collections` | `CollectionCreate` | `CollectionSummary` | 429 `LIMIT_REACHED` (remote config max) | either |
| `PATCH /library/collections/{id}` | `CollectionUpdate` | `CollectionSummary` | 404 | either |
| `DELETE /library/collections/{id}` | — | `null` | 404 | either |
| `POST /library/collections/{id}/items` | `{asset_ids: string[] (1..100)}` | `CollectionSummary` | 404 | either |
| `DELETE /library/collections/{id}/items/{asset_id}` | — | `CollectionSummary` | 404 | either |
| `POST /library/items/{asset_id}/report` | `ReportCreate` | `{reported: true}` | 429 `RATE_LIMITED` (10/day) | either |
| `GET /library/usage` | — | `LibraryUsage` | — | `broll_user_library` |
| `POST /library/uploads` | `LibraryUploadInit` (+ `Idempotency-Key`) | `LibraryUploadInitResponse` | 413 `UPLOAD_TOO_LARGE`, 403 `DURATION_NOT_ENTITLED`, 403 `STORAGE_QUOTA_EXCEEDED`, 429 `LIMIT_REACHED`, 422 `VALIDATION_FAILED` | `broll_user_library` |
| `GET /uploads/{upload_id}` · `POST /uploads/{upload_id}/parts` · `POST /uploads/{upload_id}/complete` · abort | **The generic upload routes from backend.md §6.2, unchanged**: resume via `ListParts`, more part URLs, per-part checksums. Completing starts the media pipeline, then `on_ready` → `broll.library_ready` | as backend.md | as backend.md | the upload's `purpose` carries the flag check |
| `GET /library/sources` | `?state=&deleted=false&cursor=&limit=` | `list[LibrarySource]` + `meta` | — | `broll_user_library` |
| `GET /library/sources/{source_id}` | — | `LibrarySourceDetail` | 404 | `broll_user_library` |
| `PATCH /library/sources/{source_id}` | `{title?, tags?}` | `LibrarySource` | 404 | `broll_user_library` |
| `DELETE /library/sources/{source_id}` | `?now=false` | `LibrarySource` (with `deleted_at`) | 404 | `broll_user_library` |
| `POST /library/sources/{source_id}/restore` | — | `LibrarySource` | 404 `NOT_FOUND` (also after purge) | `broll_user_library` |
| `GET /library/sources/{source_id}/download` | — | `{url: string}` (15-minute signed attachment: the original, or the mezzanine if compacted) | 404, 409 `NOT_READY` | `broll_user_library` |

`MediaRef` lets the editor preview resolve `broll:` keys. It returns `{ref, proxy_url, thumb_url, renderable, reason}`; `renderable: false` with `reason: "taken_down" | "deleted" | "held"` drives the "Missing clip" placeholder.

```python
class LibraryBrowse(BaseModel):
    featured: list["CollectionSummary"]      # each with up to 12 preview items
    categories: list["CategoryOut"]
    popular: list[LibraryItem]

class CategoryOut(BaseModel):
    slug: str
    name: str
    parent: str | None
    count: int

class CollectionSummary(BaseModel):
    id: str
    name: str
    description: str
    curated: bool                            # true = Clipnera collection (read-only for users)
    count: int
    cover_thumb_url: str | None
    items: list[LibraryItem] = []            # filled only by browse

class CollectionCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    description: str = Field("", max_length=500)
    asset_ids: list[str] = Field(default_factory=list, max_length=100)
    copy_of: str | None = None               # "Save a copy" of a curated collection

class CollectionUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=120)
    description: str | None = Field(None, max_length=500)
    order: list[str] | None = Field(None, max_length=1000)   # asset ids in the new order

class ReportCreate(BaseModel):
    reason: Literal["wrong_tags", "low_quality", "offensive", "copyright", "other"]
    note: str = Field("", max_length=500)

class LibraryItemDetail(LibraryItem):
    tags: list[str]
    categories: list[CategoryOut]
    fps: float
    similar: list[LibraryItem]               # up to 8 vector neighbours, same visibility rules

class LibraryUsage(BaseModel):
    used_bytes: int
    reserved_bytes: int
    trash_bytes: int
    quota_bytes: int
    items: int
    max_items: int
    upload_seconds_today: float
    upload_seconds_per_day: int
    max_file_bytes: int
    max_file_seconds: int
    over_quota: bool

class LibraryUploadInit(BaseModel):
    """Checks plan limits, rights and duplicates, reserves quota, then opens a generic upload (backend.md §6.2)."""
    filename: str = Field(..., min_length=1, max_length=255)
    content_type: Literal["video/mp4", "video/quicktime", "video/webm", "video/x-matroska"]
    size_bytes: int = Field(..., gt=0)
    duration_seconds: float | None = Field(None, gt=0)
    fingerprint: str = Field(..., min_length=16, max_length=64)   # §10.6
    rights_confirmed: Literal[True]                               # 422 VALIDATION_FAILED unless ticked
    allow_duplicate: bool = False

class LibraryUploadInitResponse(BaseModel):
    source_id: str
    # The generic upload handle (backend.md §6.2: upload_id, part_size, first batch of part URLs).
    # Null when duplicate_of is set and allow_duplicate is false.
    upload: UploadInitResponse | None
    duplicate_of: "LibrarySource | None" = None

SourceStateOut = Literal["uploading", "processing", "ready", "failed"]

class LibrarySource(BaseModel):
    id: str
    title: str
    kind: LibraryKind
    state: SourceStateOut
    status: Literal["live", "held", "deleted"]   # user-facing roll-up of its shots
    error: str | None
    processing_step: str | None              # "Preparing preview" | "Finding shots" | "Describing scenes"
    duration_s: float
    width: int
    height: int
    has_audio: bool
    stored_bytes: int
    shot_count: int
    thumb_url: str | None
    proxy_url: str | None
    sprite_url: str | None
    deleted_at: datetime | None
    purge_after: datetime | None
    created_at: datetime

class UsedIn(BaseModel):
    kind: Literal["editor_project", "clip", "reel"]
    id: str
    title: str

class LibrarySourceDetail(LibrarySource):
    tags: list[str]
    shots: list[LibraryItem]
    used_in: list[UsedIn]
```

```ts
export interface LibraryBrowse { featured: CollectionSummary[]; categories: CategoryOut[]; popular: LibraryItem[]; }
export interface CategoryOut { slug: string; name: string; parent: string | null; count: number; }
export interface CollectionSummary {
  id: string; name: string; description: string; curated: boolean; count: number;
  cover_thumb_url: string | null; items: LibraryItem[];
}
export interface CollectionCreate { name: string; description?: string; asset_ids?: string[]; copy_of?: string | null; }
export interface CollectionUpdate { name?: string | null; description?: string | null; order?: string[] | null; }
export interface ReportCreate { reason: 'wrong_tags' | 'low_quality' | 'offensive' | 'copyright' | 'other'; note?: string; }
export interface LibraryItemDetail extends LibraryItem {
  tags: string[]; categories: CategoryOut[]; fps: number; similar: LibraryItem[];
}
export interface MediaRef {
  ref: string; proxy_url: string | null; thumb_url: string | null;
  renderable: boolean; reason: 'taken_down' | 'deleted' | 'held' | 'blocked' | null;
}
export interface LibraryUsage {
  used_bytes: number; reserved_bytes: number; trash_bytes: number; quota_bytes: number; items: number; max_items: number;
  upload_seconds_today: number; upload_seconds_per_day: number; max_file_bytes: number; max_file_seconds: number;
  over_quota: boolean;
}
export interface LibraryUploadInit {
  filename: string; content_type: 'video/mp4' | 'video/quicktime' | 'video/webm' | 'video/x-matroska';
  size_bytes: number; duration_seconds?: number | null; fingerprint: string; rights_confirmed: true;
  allow_duplicate?: boolean;
}
/** `UploadInitResponse` is the generic upload type defined with backend.md §6.2. */
export interface LibraryUploadInitResponse {
  source_id: string; upload: UploadInitResponse | null; duplicate_of: LibrarySource | null;
}
export type SourceStateOut = 'uploading' | 'processing' | 'ready' | 'failed';
export interface LibrarySource {
  id: string; title: string; kind: LibraryKind; state: SourceStateOut; status: 'live' | 'held' | 'deleted';
  error: string | null; processing_step: string | null; duration_s: number; width: number; height: number;
  has_audio: boolean; stored_bytes: number; shot_count: number;
  thumb_url: string | null; proxy_url: string | null; sprite_url: string | null;
  deleted_at: string | null; purge_after: string | null; created_at: string;
}
export interface UsedIn { kind: 'editor_project' | 'clip' | 'reel'; id: string; title: string; }
export interface LibrarySourceDetail extends LibrarySource { tags: string[]; shots: LibraryItem[]; used_in: UsedIn[]; }
```

### 7.4 Clip studio and editor endpoints

| Method & path | Request | Response | Notes |
|---|---|---|---|
| `GET /broll/search` (existing) | unchanged | `BrollPreview[]` (≤4) | **Kept unchanged** for `ClipBrollPanel` until its rebuild. Internally switches to hybrid retrieval |
| `POST /broll/clips/{clip_id}/placements` (new) | `BrollPlacementCreate {start: float, end: float, asset_id: str, query?: str}` (source-video seconds, as `Placement`) | `ClipBrollResponse` (existing) | Validates the asset like `service.py:101-103` plus `RENDERABLE` and tier; 409 `OVERLAP` if it overlaps another cutaway; records usage `surface="cutaway"` |
| `POST /editor/projects/{id}/ops` (existing) | `EditorOpsRequest` | `EditorOpsResponse` | **New server rule:** every `add_asset` with a `broll:` key must name a shot the caller may use (live, visible, tier allowed) and must match `frames` (±1) at the project fps. Otherwise 422 `ASSET_NOT_AVAILABLE` with `op_index`, the same shape as `TimelineError` (`editor/ops.py:158-174`). Writes `broll_usage` (`surface="editor"`) for each new `b_` item |
| `GET /editor/projects/{id}/broll-picks` (new) | — | `list[BrollPickOut]` | For the "why" line and swap |
| `POST /editor/projects/{id}/broll-picks/{pick_id}/swap` (new) | `{asset_id: str, base_version: int}` | `EditorOpsResponse` | Server builds `[add_asset?, replace_asset, trim_item]` as one version; marks `swapped_to`; records swap usage. Swapping by hand from the Library panel uses plain ops |

```python
class BrollPlacementCreate(BaseModel):
    start: float = Field(..., ge=0)
    end: float = Field(..., gt=0)
    asset_id: str
    query: str = Field("", max_length=120)

class PickReason(BaseModel):
    code: Literal["keyword", "meaning", "your_library", "fits_frame", "length_fits", "fresh", "collection", "chosen_by_you"]
    text: str                                # "matches 'coffee' and 'pour'"

class BrollPickOut(BaseModel):
    id: str
    item_id: str
    version: int
    query: str
    asset: LibraryItem
    reasons: list[PickReason]
    alternates: list[LibraryItem]            # up to 4, ready to swap
    swapped_to: str | None
```

```ts
export interface BrollPlacementCreate { start: number; end: number; asset_id: string; query?: string; }
export interface PickReason {
  code: 'keyword' | 'meaning' | 'your_library' | 'fits_frame' | 'length_fits' | 'fresh' | 'collection' | 'chosen_by_you';
  text: string;
}
export interface BrollPickOut {
  id: string; item_id: string; version: number; query: string; asset: LibraryItem;
  reasons: PickReason[]; alternates: LibraryItem[]; swapped_to: string | null;
}
export interface BrollPickSwapRequest { asset_id: string; base_version: number; }
```

### 7.5 Admin endpoints (`/api/v1/admin/broll`)

- **Access:** today `get_current_admin` (`broll/route.py:30`); after backend.md 12.5, `require_admin("broll.curate")` for the `content` role, and `superadmin` for takedowns.
- **Audit:** every mutating admin route writes **`admin_audit_log`** in the same transaction (backend.md §8.3), with before and after values and a reason. Today the actor is not recorded at all ([audit 07 §4.2](audit/07-settings-billing-admin.md)).
- **Asset history:** `broll_events` keeps the asset's own lifecycle, which includes non-admin actors (system enrich, backfill, user delete or restore, moderation holds). The asset drawer's History merges both sources by time.

| Method & path | Request | Response `data` |
|---|---|---|
| `GET /admin/broll/assets` (extended, backward compatible) | existing `q,status,limit,offset` + `kind, source, category, tier, licence, commercial, orientation, min_short_side, people, logos, reviewed, sort (newest\|most_used\|most_swapped\|quality)` | `BrollAssetListResponse` (existing; `items` gains optional fields below) |
| `GET /admin/broll/assets/{id}` | — | `AdminAssetDetail` |
| `PATCH /admin/broll/assets/{id}` | `AdminAssetUpdate` | `BrollAssetResponse` |
| `POST /admin/broll/assets/{id}/status` (existing) | `BrollStatusRequest` with `status` widened to `live\|retired\|blocked\|taken_down` and `reason_code` added (optional, keeps old clients valid) | `BrollAssetResponse` |
| `POST /admin/broll/review` | `ReviewDecisionBatch` | `BulkResult` |
| `POST /admin/broll/assets/bulk` | `BulkAction` | `BulkResult` |
| `POST /admin/broll/uploads` · `GET …/{source_id}/parts` · `POST …/{source_id}/complete` · `POST …/{source_id}/abort` | same shapes as user uploads + `AdminLicenceInput` on init | same |
| `POST /admin/broll/sources/{id}/licence-proof` | presigned PUT for a proof file | `{upload_url, key}` |
| `POST /admin/broll/ingest` (existing) | `BrollIngestRequest` + optional `review: bool` | `BrollIngestResponse` + `run_id` |
| `GET /admin/broll/ingest-runs` | `limit, offset` | `{items: IngestRunOut[], total}` |
| `GET/POST/PATCH/DELETE /admin/broll/categories[/{id}]` | `CategoryIn` | `CategoryOut` |
| `GET/POST/PATCH/DELETE /admin/broll/collections[/{id}]`, `POST …/{id}/items` | as user collections + `is_featured, featured_from, featured_until, sort` | `CollectionSummary` |
| `GET /admin/broll/reports` | `state, origin, limit, offset` | `{items: ReportOut[], total}` |
| `POST /admin/broll/reports/{id}/resolve` | `{action: dismiss\|hold\|release\|take_down, note}` | `ReportOut` |
| `POST /admin/broll/takedowns` | `TakedownCreate` | `{affected_assets, affected_projects}` |
| `GET /admin/broll/events` | `asset_id?, actor?, limit, offset` | `{items: EventOut[], total}` |

```python
class BrollAssetResponse(BaseModel):          # existing fields kept; new optional fields appended
    ...                                      # id … created_at as today (broll/schema.py:9-28)
    tier: Tier = "free"
    owner_user_id: str | None = None         # admin view only shows platform items; kept for completeness
    mood: Mood | None = None
    color_family: ColorFamily | None = None
    has_people: bool | None = None
    has_logos: bool | None = None
    nsfw: bool | None = None
    vision_caption: str | None = None
    categories: list[str] = []               # slugs
    reviewed_at: datetime | None = None
    usage_count: int | None = None
    swap_rate: float | None = None

class AdminLicenceInput(BaseModel):
    code: str = Field(..., max_length=40)    # must exist in the licence registry
    url: str | None = Field(None, max_length=1000)
    author: str | None = Field(None, max_length=300)
    author_url: str | None = Field(None, max_length=1000)
    attribution_text: str | None = Field(None, max_length=500)
    commercial_ok: bool
    expires_at: datetime | None = None
    notes: str | None = Field(None, max_length=2000)
    proof_key: str | None = None

class AdminAssetDetail(BrollAssetResponse):
    caption: str
    fps: float
    quality_score: float
    has_text: bool | None
    licence: LicenceInfo | None
    licence_record: dict | None              # verified_by, verified_at, expires_at, notes, proof_url, source_record_url
    usage: dict                              # {placements, swaps, last_used_at, by_surface}
    history: list["EventOut"]

class AdminAssetUpdate(BaseModel):
    title: str | None = Field(None, max_length=300)
    caption: str | None = Field(None, max_length=2000)
    tags: list[str] | None = Field(None, max_length=40)
    category_slugs: list[str] | None = None
    tier: Tier | None = None
    mood: Mood | None = None
    has_people: bool | None = None
    has_logos: bool | None = None
    has_text: bool | None = None
    quality_score: float | None = Field(None, ge=0, le=1)

class ReviewDecision(BaseModel):
    asset_id: str
    decision: Literal["approve", "reject"]
    reason_code: str | None = None
    note: str | None = Field(None, max_length=500)
    edits: AdminAssetUpdate | None = None

class ReviewDecisionBatch(BaseModel):
    decisions: list[ReviewDecision] = Field(..., min_length=1, max_length=200)

class BulkAction(BaseModel):
    asset_ids: list[str] | None = Field(None, max_length=1000)
    filter: dict | None = None               # the list filter, for "all N matching"; capped at 5,000
    action: Literal["set_status", "set_tier", "add_tags", "remove_tags", "set_category", "add_to_collection"]
    status: Literal["live", "retired", "blocked", "taken_down"] | None = None
    tier: Tier | None = None
    tags: list[str] | None = None
    category_slug: str | None = None
    collection_id: str | None = None
    reason_code: str | None = None
    note: str | None = Field(None, max_length=500)

class BulkResult(BaseModel):
    changed: int
    skipped: int
    errors: list[dict]                       # [{asset_id, code, message}]

class TakedownCreate(BaseModel):
    asset_ids: list[str] = Field(..., min_length=1, max_length=500)
    claimant: str = Field(..., max_length=300)
    reference: str = Field(..., max_length=200)
    note: str = Field("", max_length=2000)

class IngestRunOut(BaseModel):
    id: str
    query: str
    sources: list[str]
    per_source: int
    review: bool
    state: str
    added: int
    skipped: int
    failed: int
    errors: list[str]
    requested_by: str | None
    created_at: datetime
    finished_at: datetime | None

class EventOut(BaseModel):
    id: str
    asset_id: str | None
    actor: str
    actor_email: str | None
    action: str
    from_status: str | None
    to_status: str | None
    reason: str | None
    note: str | None
    created_at: datetime

class ReportOut(BaseModel):
    id: str
    asset: BrollAssetResponse
    origin: str
    reason: str
    note: str
    claimant: str | None
    state: str
    created_at: datetime
```

Matching TypeScript for the admin shapes follows the same one-to-one rule. Each interface carries the identical field list, with `datetime` → `string`, `dict` → `Record<string, unknown>`, and `X | None` → `X | null`. They are written in the same change as the routes (AGENTS.md "API Contracts"). They are omitted here only for length: there is no shape decision left in them.

---

## 8. Editor and AI integration

### 8.1 The reference key (D8)

- **Timeline asset:** `{id: "b_<asset_id>", kind: "video", key: "broll:<asset_id>", proxy: "broll:<asset_id>:proxy", frames, width, height, has_audio}`.
  - `Id` allows 40 characters (`editor/timeline.py:23`). `b_` plus a 36-character uuid is 38.
  - `key` is free text up to 500 characters (`timeline.py:50`).
- **Preview** resolves `broll:` refs via `GET /library/media`. Other assets keep whatever resolver Wave 3 defines.
- **Render** resolves via `rendition_for(asset, aspect)` (§5.1). A non-renderable asset renders as nothing on that overlay track; the result reports it (§10.5).
- **Fixtures:** `editor/fixtures` and `lib/editor/timeline.test.mts` need a case with a `broll:` asset. It's only a value, so the schema is unchanged.

### 8.2 Hand placement

See §3.5. The client batch is plain Timeline ops. The server-side `add_asset` check (§7.4) is the security boundary, because the client can send any key.

### 8.3 Prompt placement — "add B-roll of coffee being poured at 0:12"

New agent tools in `editor/agent_tools.py`, beside `get_timeline` and `apply_edits` (`:79-85`):

| Tool | Input | Output |
|---|---|---|
| `search_broll` | `{query, at_frame?, frames?, scope: "auto"\|"mine"\|"platform", limit ≤8}` | candidates: id, caption, duration, scope, fit, reasons. Read-only; also used in **Ask** mode |
| `place_broll` | `{query, at_frame, frames, track?: Id, asset_id?: str, base_version}` | `{version, item_id, pick_id, chosen, reasons, alternates}` or an error |

What `place_broll` does:

1. Runs the same retrieval as the UI with the project's aspect, fps and caller (`asset_id` given → validate it instead).
2. Applies the threshold (§8.5); with no good match it returns a tool error `NO_GOOD_MATCH` with the best three (a tool result the model reads, not an HTTP code). The agent then says so plainly (01 §3.6) and may suggest an AI shot with its credit cost (01 §3.10).
3. Builds ops: `add_track(overlay "broll")` if needed, `add_asset` if needed, `add_item` with `volume 0` and a 4-frame fade.
4. Applies them through `EditorService.apply(..., author="agent:editor")` (`editor/service.py:57-79`), so it is one version.
5. Writes a `broll_picks` row and returns.

**Why one composite tool.** The model need not hand-build a valid `TimelineAssetRef` or reason about overlap rules. The pick record is written in the same transaction as the ops. Overlap at the target frame is handled by trying the next free overlay track, then by shortening to fit.

**Timecode parsing** ("0:12", "12s", "at the part where she laughs") is the agent's job. It has `get_timeline` and, in Wave 3, transcript access. The tool takes frames only.

**Result message** (01 §5 step 9):

> Added B-roll at 0:12–0:16 — "Pouring coffee into a white mug" from **your uploads**.
> *Why:* matches "coffee" and "pour" · from your library · fits 9:16.
> [thumbnail] [Swap ▾] [Undo]

**Swap ▾** opens the alternates strip (4 tiles, hover preview) plus "Search for something else", which opens the Library panel prefilled with the query. One click on an alternate calls the swap endpoint (§7.4) and creates one new version named "Swapped B-roll at 0:12".

### 8.4 `/broll` and the Asset chip

- **`/broll`** inserts the template `Add B-roll of [what] at [time]` (01 §4: templates are filled, never run on selection).
  - With a **Range** chip present: `Add B-roll of [what] over 0:12–0:16`.
  - With an **Asset** chip present: `Use this clip at [time]`.
  - While the user types `[what]`, a small inline strip under the bar shows the top 4 search results. Clicking one turns it into an Asset chip.
- **Asset chip** (01 §4 table): added when a library tile is selected, dropped on the bar, or "Ask about this clip" is used. It carries `{kind: "asset", ref: "broll:<id>", title, thumb_url}`. A **Collection** variant carries `{kind: "collection", id, name}`. The agent receives chips as structured context and passes `asset_id` to `place_broll`, or constrains `search_broll` to the collection.

### 8.5 The AI pulls from both libraries, preferring yours when relevant

For each request, retrieval runs once over both scopes (subject to flags), then:

- `final = score + prefer_user_boost` for the caller's own shots, **only if** their own `score ≥ user_min_relevance`. Defaults: boost 0.15, minimum 0.55, both remote config. A weak match from your uploads never beats a strong stock match.
- An explicit "from my uploads" or a collection chip sets scope to `mine` only.
- The `your_library` reason is shown whenever an own shot wins.
- Automatic placement still needs `good_match` coverage (`cutaways.py:137-142`) **or** a vector similarity ≥ `semantic_min` (remote config, default from the eval set). This keeps today's "no cutaway beats a wrong one" rule (`cutaways.py:38-40`).

### 8.6 Cutaways and reels with user footage

Clip cutaways (`plan_project_broll`, `cutaways.py:77-134`) and image reels (`reels/jobs.py:135-150`) already call the retriever with `user_id`. They would include user shots the moment those rows exist. The rule:

1. Until `rendition_for` replaces direct `vertical_key` reads in `cutaways.apply_broll` (`:205-208`) and `reels/jobs._render` (`:196-197`), the retriever **excludes `kind = user` shots** from `find()`.
2. After that change, user shots are included only when `broll_user_library` is on **and** the user hasn't turned off "Use my uploads in AI edits" (a per-user setting, default on).
3. User shots carry audio. Cutaways overlay picture only (`-map 0:a?`, `cutaways.py:221`), so no change there.

### 8.7 Studio stock mock

`BrollPanel`'s "Add stock footage" (four Unsplash stills, `BrollPanel.tsx:9-30,81-98`) is a visible control. Per the UI rule it is **replaced, not removed, only with the owner's confirmation** (owner question Q10). The proposed replacement is the same section title with the real library search, which adds a cutaway at the playhead through §7.4.

---

## 9. Plans, quotas, flags

### 9.1 Flags (declared as in [06-flags §3.1, §9.1](06-flags.md))

Both flags are kind `release`, parent `broll_studio`, default off, `bucket_by="user"`, `live_update="immediate"`, owner Product owner, expiring 2027-03-31. These are the values 06-flags already catalogues. With the grandparent fix in 06-flags §3.5, turning `broll_studio` off turns both off.

| Key | Gates | Off means | Requires |
|---|---|---|---|
| `broll_platform_library` | Clipnera library browse and search UI; `/library/browse`; platform scope of `/library/search`; `/broll` and Asset chip for platform shots; drag from the Clipnera tab | UI hidden. **Existing placements still render. Clip cutaways keep working** (separate flag `broll_studio.cutaways`). Admin curation unaffected | — (editor surfaces are additionally behind `agent_editor`; that is a UI condition, not a flag `requires`) |
| `broll_user_library` | Uploads, Your uploads, storage meter, user scope of search, user shots in AI picks | New uploads refused (`403 FEATURE_DISABLED`). In-flight processing completes. Files are **not** deleted. Placed user shots still render. Users can still delete their files (the privacy right outlives the flag) | — |

**Rollout** (06-flags §12 runbook): internal users → 10% Pro → all Pro → everyone. A plan-targeted rule is only a rollout tactic, never the way to make the user library Pro-only (06-flags §3.7). Quotas do that.

### 9.2 Remote-config keys

`plan_promise` keys are read through entitlements (06-flags §5.3) and appear in the plan comparison. Storage values are this wave's pricing of the 06-flags placeholders (Free 2 GiB / Pro 50 GiB).

| Key | Kind · unit | Free | Pro | `plan_promise` | Notes |
|---|---|---|---|---|---|
| `storage.user_library_quota_bytes` (06-flags name) | int · bytes | **1 GiB** | **25 GiB** | yes | Pro Plus = Pro. At ~$0.023/GB-month S3 Standard, a full Pro library is ≈ $0.58/month against ₹699 revenue; most users will use a fraction. 50 GiB would double the worst case for little visible benefit |
| `storage.user_library_max_items` | int · count | 100 | 2,000 | yes | files, not shots |
| `uploads.library_max_file_bytes` | int · bytes | 500 MiB | 4 GiB | yes | `uploads.max_bytes` stays the hard ceiling |
| `uploads.library_max_file_seconds` | int · seconds | 300 | 1,800 | yes | B-roll, not full episodes |
| `uploads.library_seconds_per_day` | int · seconds | 1,800 | 14,400 | yes | Bounds compaction CPU |
| `storage.user_library_compact_originals` | bool | true | true | no | D10 |
| `storage.user_library_compact_bitrate` | int · bits/s | 12,000,000 | 12,000,000 | no | Above this (or above 1080p) the original is compacted |
| `storage.user_library_trash_days` | int · count (days) | 30 | 30 | no | |
| `broll.user.nsfw_action` | enum `hold`\|`flag` | `hold` | `hold` | no | |
| `broll.collections_max` | int · count | 10 | 200 | no | |
| `broll.platform.review_required` | bool | true | | no | global |
| `broll.platform.tiering_enabled` | bool | false | | no | global; off at launch, all live shots Free tier |
| `broll.search.semantic_enabled` | bool | true | | no | global kill for vector recall |
| `broll.search.rrf_k` · `broll.search.max_results` | int | 60 · 300 | | no | |
| `broll.search.weights` | string (JSON) | §4.4 | | no | Validated by its `TypeAdapter` |
| `broll.pick.prefer_user_boost` · `broll.pick.user_min_relevance` · `broll.pick.semantic_min` | float · ratio | 0.15 · 0.55 · from evals | | no | |
| `broll.place.default_seconds` | float · seconds | 4 | | no | |
| `broll.preview.url_ttl_seconds` | int · seconds | 3600 | | no | presigned fallback only |
| `broll.takedown.file_retention_days` · `broll.reject.file_retention_days` | int | 90 · 30 | | no | |

Over-quota behaviour is policy, not config: nothing is ever auto-deleted (Q4).

**How plans read them.** `SubscriptionService.get_entitlements` (`subscription/service.py:321`) reads the `plan_promise` keys through `flags.config(key, ctx_for_plan)` and returns them in a `library` block on the entitlements response:

`{quota_bytes, max_items, max_file_bytes, max_file_seconds, upload_seconds_per_day}`

`GET /subscription/plans` then shows "25 GB library" in the plan comparison. `STORAGE_QUOTA_EXCEEDED` and `UPLOAD_TOO_LARGE` join `PLAN_ERROR_CODES` (`lib/api.ts:496`), so the existing upsell path opens. The code defaults above are the fallbacks while remote config is not deployed (06-flags phase 1).

**Credits.** Browsing, search, favourites, uploads and hand placement cost no credits. Today's charges are unchanged: 5 credits per clip that gets cutaways (`BROLL_CREDITS_PER_CLIP`, `core/config.py:128`), and 120 per AI shot (`VEO_SCENE_CREDITS`, `:162`). AI placement inside an editor run is costed by the Wave 3 run pricing; this design adds no separate charge.

---

## 10. Licensing and abuse edge cases

### 10.1 Copyrighted uploads (user library)

- One-time rights confirmation (§3.3) plus Terms language (owner/legal, Q5). Stored on each source (`rights_attested_at`).
- The user library is private, and the user is the publisher of anything they export. We don't run content-ID matching; owner question Q5 covers whether to add an audio-fingerprint check later.
- **Rights claims** against a user's file (by email to the published contact) are logged as a `broll_reports` row with `origin="rights_claim"`. Admin can take down (§10.3). The owner gets an in-app notification with the reason and an appeal contact.
- Admin uploads to the Clipnera library **require** a licence from the registry and are proof-backed; there is no "unknown" licence.

### 10.2 NSFW and harmful content

- The enrichment call returns `nsfw`, a coarse signal.
- For **user items**: with `nsfw_action = hold`, flagged shots go `held`. The owner sees "Held for review — this clip can't be used until we check it", and it appears in the admin Moderation tab. With `flag`, the item stays usable by hand, is excluded from AI picks, and is listed for admins.
- For **Clipnera library** ingests: a flagged shot lands in review with the flag shown. It can't be auto-approved.
- The vision model is **not** a child-safety detector. Legal obligations (India IT Rules, reporting duties) are owner question Q5; a dedicated safety classifier may be required before broad launch of uploads.

### 10.3 Takedowns

- A **Clipnera library** takedown runs `POST /admin/broll/takedowns`:
  - status `taken_down` for the listed shots and their siblings from the same source, when the claim covers the source
  - removed from search immediately
  - dropped from future renders (today's behaviour)
  - `broll_events` written for each shot
  - files deleted after `broll.takedown.file_retention_days`; the licence record and claim are kept
- **Users who placed it** see a notice on affected projects: "A B-roll shot in this project is no longer available. Replace it." The affected list comes from `broll_usage` plus `broll_picks`. Already-exported and published videos are not altered; we cannot alter them. The takedown log records the count, and the policy is stated in the Terms.
- **Restore** (`live`) is possible after a mistaken takedown while files still exist.

### 10.4 Licence registry and display

A code-level registry (`broll/licences.py`, new):

| Code | Name | Attribution | Commercial |
|---|---|---|---|
| `pexels` | Pexels License | not required (credit line offered) | yes |
| `pd_us_gov` | Public domain (US government) | not required ("Courtesy NASA" offered) | yes |
| `cc0` | CC0 | no | yes |
| `public_domain` | Public domain | no | yes |
| `cc_by` | CC BY | **required** | yes |
| `pixabay` | Pixabay Content License | not required | yes |
| `ai_generated` | Generated for you | no | yes |
| `owned` | Clipnera-owned | no | yes |
| `licensed` | Licensed to Clipnera (contract) | per record | per record |

- The registry backs `LicenceInfo.attribution_required` and the export credits (§3.8).
- CC BY-SA and NC are already refused at ingest (`broll/sources/wikimedia.py:1-31`); admin upload enforces the same rule.
- **Licence expiry:** when `expires_at` passes, `broll.sweep` retires the shot. Placements keep rendering only if the licence permits use after expiry; otherwise it is blocked. This is a per-record choice in the admin form.

### 10.5 A user deletes a clip that a project uses

- Delete is soft for 30 days (§3.3).
- **Exported and published videos are unaffected:** they are rendered files (clips under `clips/…`, social posts reference those).
- **Draft editor projects** keep the timeline item. Preview shows a "Missing clip" placeholder from `MediaRef.renderable=false`, with **Replace** (opens Library filtered by the same query) and **Remove**. Rendering skips it and reports "1 clip was missing and left out".
- **Clip cutaways**: `apply_broll` already skips assets it can't render (`cutaways.py:204-206`). Rule: a soft-deleted user shot is `RENDERABLE = false`, so the export goes ahead without it. The clip studio's AI cutaways panel shows the placement as "Missing" with alternates.
- After purge, the asset rows are deleted (cascade from `broll_sources`). `broll_usage.asset_id` cascades (`model.py:113`), `broll_picks` cascade, and Timeline items keep an id that resolves to nothing, which is still the "Missing clip" state.

### 10.6 Duplicates

- **Before upload:** the client computes `fingerprint = sha256(size ‖ first 4 MB ‖ last 4 MB)` with WebCrypto. That is fast for any size, reading only 8 MB.
  - Init finds an existing non-deleted source with the same owner and fingerprint → `duplicate_of`, with Use existing / Upload anyway.
  - A fingerprint match against the user's own **trash** offers Restore.
- **After upload:** the worker computes the full SHA-256 while reading the file (as `ingest.py:121-136` does). On an exact match with another of the user's sources, the new one is linked to the existing source, its files are deleted, its quota is released, and the tray says "Already in your library — we kept the original". The unique index `uq_broll_sources_owner_hash` enforces this.
- Across users there is **no** de-duplication. It would leak that someone else holds the same file.
- Stock keeps today's cross-source hash check (`ingest.py:190-191`).

### 10.7 Quota exceeded mid-upload

- **Reservation at init** (D11), in one transaction:

  `SELECT … FROM library_storage WHERE workspace_id = :w FOR UPDATE` → check `used + reserved + size ≤ quota` → `reserved += size` → insert source and open the generic upload.

  Parallel tabs serialize on the row.
- **On ready** (`broll.library_ready`): `used += stored_bytes`, `reserved -= size`. The stored size is usually smaller than the original when compaction runs (§5.1), so users gain space.
- **On abort, failure or expiry** (24 h): the reservation is released by `abort` or `broll.sweep`. The bucket lifecycle rule from backend.md §6.1 aborts incomplete multipart uploads after 2 days.
- **Plan lapses** while over quota: nothing is deleted; uploads are blocked until under quota; "Over your Free storage — your clips are safe; delete some or upgrade to upload more."
- **Daily upload minutes:** counted at init from `duration_seconds` and corrected after probe. If the probe shows a longer file than declared and it is over the limit, the source fails with a plain message and nothing is charged.

### 10.8 Abuse of the library as free hosting

- No public links. Every URL is signed, short-lived and bound to the owner's session. Proxies are low resolution.
- Downloads of own uploads are capped at 50 a day (§11.4).
- Platform shots are never downloadable.

### 10.9 Account deletion and retention

- **New user-library files** live under the workspace path `w/{workspace_id}/broll/{source_id}/…` (backend.md §6.1). Deleting an account deletes the personal workspace's prefix. That step must be added to `delete_account` (`user/service.py:127-145`), which today deletes only the legacy per-user prefixes (`:20-26`).
- **Fix the existing AI-shot gap.**
  - New AI shots go to `w/{workspace_id}/broll/generated/{source_id}/…`.
  - For existing generated assets, `delete_account` first deletes the keys of the user's `broll_assets` where `owner_user_id = user` (they live under `broll/assets/{id}/`), then cascades.
  - This fix is small and can ship ahead of everything else (§13, step 7.1).
- **Audit rows outlive the account.** `broll_events`, `broll_reports` and `admin_audit_log` keep their rows with `SET NULL` actor and reporter, so the audit trail survives without personal data.

---

## 11. Security

### 11.1 Tenant isolation

- **One predicate**, `visible_to(principal)`, in `BrollRepository`. It takes the request principal from backend.md §8.2 (`user_id`, `workspace_id`, `plan`), not a raw user id, and every user-facing read uses it:

  `owner_user_id IS NULL AND status = 'live' AND tier allowed for principal.plan` **OR** `workspace_id = principal.workspace_id AND status IN visible statuses AND source not deleted`

  It generalises `repository.py:81` and `service.py:102`. Backend.md's route-coverage test covers the routes; a repository test asserts that no user-facing query on `broll_assets` / `broll_sources` bypasses the predicate.
- **Not found, not forbidden:** other workspaces' items return 404 everywhere (backend.md §8.2).
- **Workspace roles** (backend.md §8.2): `viewer` may browse and preview, but not upload, edit, delete or place. `member` may do everything except empty the trash permanently. `owner` may do all of it.
- **The editor ops check** (§7.4) applies the same predicate to `broll:` keys. Without it, a user could reference another workspace's private shot by id and have it rendered into their export.
- **Collections:** personal collections are scoped to the workspace. Curated collections only list shots that pass `visible_to`. Adding a shot to a collection re-checks visibility.
- **Admin:** the platform library list filters `owner_user_id IS NULL` (D15). User items reach admins only through reports and flags. Any admin read of a user item writes `admin_audit_log` (`action="broll.user_item.view"`). Curation routes require `require_admin("broll.curate")`, mapped to the `content` role (backend.md §8.3).
- **Team libraries.** In a personal workspace (the default), "workspace" means "you". Sharing a library in a team workspace is a consequence of backend.md's tenancy model and needs the owner's product call (Q3). Until then the UI only offers the library in personal workspaces.

### 11.2 Signed access

- **Previews:** CloudFront signed cookies per workspace path and for `broll/*` (D14). The presigned fallback serves proxy, thumb and sprite only, for ≤1 h with bucketed expiry (§5.5).
- **Masters:** masters of Clipnera shots are **never** exposed to users. Renders read them server-side.
- **Own uploads:** the download endpoint returns a 15-minute signed attachment URL (backend.md §6.1) for the user's own original or mezzanine.
- **Upload part URLs:** short-lived and per part, with checksums (backend.md §6.2, replacing today's 6 h, `core/config.py:103`).
- **Logging:** never log signed URLs (backend.md §8.4).

### 11.3 Upload validation

- **Server-side at init:** content type whitelist, size limits, declared duration limits, filename sanitised (stored as metadata only; S3 keys use ids, never names).
- **At complete:** stored size must equal declared (as `uploads/service.py:108-116`), and the media pipeline's validation runs (magic-byte sniff, ffprobe, decode test; backend.md §6.2).
- **At processing:**
  - `ffprobe` must find a video stream with sane dimensions (≥ 240 px short side, ≤ 8K) and duration ≤ plan limit.
  - Container/codec allow-list.
  - Any file ffmpeg can't decode fails with "We couldn't read this video".
  - ffmpeg runs with `-nostdin`, no network protocols (`-protocol_whitelist file`), inside a temporary directory (as `renditions.py:35-58` already does).
- **Never trust client duration or fingerprint** for anything but early refusal and duplicate hints.
- **Bucket CORS:** PUT from the app origin and expose `ETag`. Direct video uploads already need the same setting (`uploads/service.py:1-7`).

### 11.4 Other

- Rate limits: library search and upload init use the global per-route limits of 06-flags §5.2 (rate limits are global-only there). Reports (10/day) and own-upload downloads (50/day) are daily quotas counted with `consume_daily_quota`.
- Search query text is logged without user id, for tuning; the retention period is to be agreed (Q11).
- The licence proof files and source records are admin-only, signed for 10 minutes.

---

## 12. Migrating today's stock library without losing data

| Data | What happens | Loss risk and mitigation |
|---|---|---|
| `broll_assets` rows | Kept; same ids. `status` unchanged (live stays live). `tier = free`. `reviewed_at = null`; a `grandfathered` event is written | None. Placements in `generated_clips.broll_plan` and `reel_projects.scenes` reference these ids and keep working |
| S3 renditions `broll/assets/{id}/…` | Untouched. `master_key` null, so these shots are 9:16-only (§5.2) | None. Optional `broll.remaster` later re-fetches sources for a landscape master (from `source_url` and the stored record), only where the licence allows re-download |
| `broll_licenses` | Unchanged; new columns null | None |
| `source_record_key` JSON | Unchanged; now viewable by admins | None |
| `broll_usage` | Unchanged; `surface='cutaway'` default; reel rows can't be told apart historically | Cosmetic only |
| `embedding` (ARRAY) | Left alone until M7; `text_embedding` re-made by `broll.index` | Old vectors were 3,072-d, or absent with the provider off. Nothing is lost by re-embedding |
| Categories | Inferred by `broll.backfill` (matching `seed.py` topic lists to title and tags) as `origin = inferred`; admins confirm in bulk | Wrong guesses are visible and fixable; they don't affect search ranking until confirmed (weight 0 for inferred) |
| `has_people` / `has_logos` (never written) | Filled by the `broll.index` backfill | — |
| Private AI shots (`kind = generated`, owner set) | Get a `broll_sources` row (`provider = veo`, owner). Appear in Your library → AI shots once `broll_user_library` is on. `stored_bytes` counted into `library_storage`, but marked `quota_exempt` so files created before the migration don't count toward the quota check | Users must not be pushed over quota by past purchases |
| Admin page | `AdminBrollView` keeps calling the same three endpoints, which stay backward compatible, until the console replaces it | — |
| CLIs `broll.seed`, `broll.collect` | `seed` goes through `broll.ingest`; new shots land in review unless `--approve` (admin intent). `collect` untouched | Prevents a seed run from silently going live; bulk approve exists |

**Backfill cost.**
- **Embed:** a few cents per 100k shots (§4.2).
- **Enrich:** one vision call per 9 shots. 100k shots ≈ 11k calls, at a price to confirm from the usage ledger on a 1k-shot pilot first (Q8).
- Runs on the worker at low priority, paged and resumable.

**Order of operations in production.**
1. M1–M6.
2. Deploy code that reads the new columns, with all features off.
3. Run `broll.backfill` (sources, categories) → enrich → embed.
4. Verify counts (shots with `source_ref_id`, with `text_embedding`).
5. Turn on hybrid search for the existing `/broll/search` (internal users first).
6. M7.

---

## 13. Phased build plan (Wave 6 areas 6 and 7)

Each step ships behind its flag with tests (`backend/tests`, plus `lib/editor/timeline.test.mts` fixtures). Hard dependencies on other waves are noted.

### Area 6 — Clipnera library (platform)

| Step | Scope | Depends on |
|---|---|---|
| 6.1 Foundations | M1–M4, M6; `broll_sources` backfill; status enum; `RENDERABLE` in `cutaways.apply_broll` and the reel render; licence registry; `broll_events` written by the existing status endpoint (actor recorded) | pgvector availability (Q1) |
| 6.2 Enrichment and search | `broll.index` (enrich + embed), M5, hybrid retrieval behind `broll.search.semantic_enabled`; existing `/broll/search` switches internally; **B-roll eval set**: 100 queries (English, Hindi, Telugu, Hinglish) with judged results; ship only if hit@4 beats today's FTS | 6.1 |
| 6.3 Curation console | Review queue, asset drawer, edit, bulk actions, ingest runs, categories, collections, takedowns, moderation tab; ingest lands in review | 6.1; Wave 2 admin components |
| 6.4 User browse | `/library/search`, `/browse`, items, favourites, collections, media refs; Library panel (Clipnera tab) and `/dashboard/library` Clipnera view; hover preview with bucketed URLs | 6.2; Wave 2 grid, tile and drawer components; flag `broll_platform_library` (06-flags) |
| 6.5 Editor insertion | `broll:` key check in the ops endpoint; drag and drop; `search_broll`/`place_broll` tools; `broll_picks`; result message with why and swap; `/broll`; Asset chip | Wave 3 agent run stream and prompt bar; Editor preview resolver |
| 6.6 Clip studio | "Add cutaway at playhead"; library search in the B-roll tool; Unsplash mock replaced (after owner OK, Q10); export credits block | 6.4 |
| 6.7 Tiering | `tier` used in `visible_to`; lock badges; plan comparison row | remote config (06-flags); owner decision on which shots are Pro (Q2) |

### Area 7 — Your library (user)

| Step | Scope | Depends on |
|---|---|---|
| 7.1 Storage and safety | `library_storage`; workspace-path storage and the account-deletion fix (incl. existing AI shots); `broll.sweep` | backend.md 11.1 (jobs table), 12.4 (lifecycle) |
| 7.2 Upload | `POST /library/uploads` (quota reservation, rights, fingerprint duplicates) on top of backend.md's generic `/uploads`; global upload tray | 7.1; backend.md 11.6; Wave 2 tray component |
| 7.3 Processing | `on_ready` hand-off from the media pipeline; `broll.library_ready` (duplicates, compaction, shots); `broll.index` reuse; held state | 6.2; backend.md 11.6 (media at upload) |
| 7.4 Library UI | Your uploads grid, moments, drawer, edit, delete/trash/restore, download, storage meter in library and Settings | 7.2, 7.3 |
| 7.5 AI preference | `rendition_for` in cutaways and reels; user shots in `find()` behind the flag and per-user setting; `prefer_user_boost`; `your_library` reason | 6.5, 7.3 |
| 7.6 CDN | Library previews on CloudFront signed cookies, including the `library.media.clipnera.com` cookie for `broll/*`; remove the presigned fallback | backend.md 12.4 |
| 7.7 Moderation hardening | nsfw `hold` path, admin moderation for user items, rights-claim flow | 6.3; legal input (Q5) |

**Suggested order:** 6.1 → 6.2 → 7.1 → 6.3 ∥ 7.2 → 6.4 ∥ 7.3 → 7.4 → 6.5 → 7.5 → 6.6 → 6.7 → 7.6 → 7.7.

---

## 14. Existing behaviour that must not break

1. **Clip cutaways end to end:**
   - the upload toggle and its credit text ("5 credits per clip that gets B-roll")
   - `plan_project_broll` charging only clips that got B-roll (`cutaways.py:119-127`)
   - swap, remove and generate (`broll/route.py:70-89`)
   - exports overlaying shots before captions, and never failing on B-roll errors (`cutaways.py:164-179`)
2. **`GET /broll/search`** keeps its path, params and `BrollPreview[]` shape (≤4) for `ClipBrollPanel` (`ClipBrollPanel.tsx:40`, `lib/api.ts:2075-2076`).
3. **`BrollPreview`, `BrollPlacementResponse`, `ClipBrollResponse`, `BrollAssetResponse`, `BrollAssetListResponse`, `BrollIngestRequest`, `BrollStatusRequest`** stay backward compatible. Only optional fields are added, and the status `Literal` is only widened.
4. **Placement ids:** every `asset_id` stored in `generated_clips.broll_plan` and in reel scenes resolves to the same shot after migration.
5. **Takedown semantics:** `blocked` and `taken_down` remove a shot from search at once and from future renders (`cutaways.py:205`). `retired` is the only new state that keeps rendering.
6. **Licence policy:** users never receive Clipnera library files; only proxies and thumbs are signed (`service.py:65-67`). CC BY-SA and NC stay refused (`wikimedia.py:1-31`).
7. **AI shots:**
   - Pro only, 120 credits, daily quota, refund on failure (`generation.py:119-139`, `generation_job.py:25-33`)
   - private to the buyer
   - the previous shot becomes an alternate (`generation_job.py:47-61`)
8. **Image reels:** B-roll scene matching with fallback to image or text (`reels/jobs.py:135-150`) and the scene swap rule (`reels/service.py:141-147`).
9. **Footage reels' own footage** (`edit_engine`) is separate from the user library and keeps its own upload path and limits (`edit_engine/route.py:68-76`, `edit_engine/limits.py`).
10. **Admin library:**
    - remains usable while user flags are off (`broll/route.py:28`)
    - the existing admin page keeps working until the console replaces it
    - ingest by topic still works
11. **Editor Timeline v1:**
    - no schema change
    - fixtures stay valid
    - `apply_ops` stays pure (`editor/ops.py:158-174`)
    - stale-version 409 is unchanged (`editor/service.py:62-66`)
12. **Video uploads** (`/uploads/video/*`) keep working. Library uploads use backend.md's generic `/uploads` with `purpose: "library"` and never change project uploads.
13. **Account deletion** still deletes everything it deletes today, now plus library files.
14. **Flags:** `broll_studio.*` keys keep their meaning. New flags never gate existing cutaway, reel or AI-shot behaviour.
15. **Entitlements** stay the single plan gate for the UI (`useEntitlements`). Library limits are added to that payload, not served separately.

---

## 15. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| pgvector not available on the production Postgres (self-hosted or old version) | Medium | Semantic search delayed | Q1 first. FTS-only search still ships. Self-hosted install is one package plus `CREATE EXTENSION` |
| Vision captions miss what users search for | Medium | Weak semantic recall | Eval set gate (6.2). CLIP column added later behind `Embedder` |
| Library uploads crowd the shared `media` pool | Medium | Slower project uploads | Daily upload-minute caps; compaction only above 1080p or the bitrate cap; per-user in-flight caps (backend.md §9.1); the `broll` class is separate and low priority |
| Review queue backlog leaves ingests offline | Medium | Library grows slowly | Bulk approve, AI pre-fill, `review_required` is remote config |
| Users upload copyrighted or illegal content | Medium | Legal | Rights confirmation, takedown flow, hold on flags, legal review (Q5) |
| `broll:` key check missed on some op path (e.g. future import) | Low | Cross-tenant render | Check in `EditorService.apply`, the one choke point, plus a test that every op path routes through it |
| Hover previews drive S3 egress cost | Medium | Cost | Small proxies, hover intent, bucketed URLs, CloudFront (7.6) |
| Account deletion leaves AI-shot files (existing bug) | Present today | Privacy | Fixed in 7.1; can be shipped earlier on its own |
| backend.md's media pipeline (11.6) or CDN (12.4) slips | Medium | Area 7 waits | Area 6 doesn't depend on them; the presigned fallback covers Area 6 previews (Q9) |
| Remote config not ready when Area 7 starts | Medium | Quotas hard-coded | Defaults on `Entitlements` with the same API shape; move later |

---

## 16. Questions for the owner

| # | Question | Default if unanswered |
|---|---|---|
| Q1 | Is production Postgres on RDS (which version), or self-hosted on EC2? May we enable the `vector` extension? | Enable pgvector; FTS-only until it is available |
| Q2 | Tier the Clipnera library by plan at all? If yes, which content is Pro (newest? 4K? certain collections)? | Tiering off at launch; Pro tier for admin-uploaded premium footage later |
| Q3 | Backend.md scopes data by workspace. Should a **team** workspace share one B-roll library (members see each other's uploads), or should the library stay personal? | Personal workspaces only this wave; team sharing switched on later without schema change |
| Q4 | Storage quotas: 1 GiB Free / 25 GiB Pro (06-flags placeholders were 2 / 50)? What happens to footage above quota after a plan lapses? | 1 / 25; never auto-delete, block uploads only |
| Q5 | Legal: Terms text for user uploads, rights-claim contact, any reporting duties, and whether a dedicated child-safety classifier is required before uploads go public | Rights confirmation + hold-on-flag; uploads stay behind the flag for internal and Pro users until answered |
| Q6 | Should the user library take images and audio too (logos, stills, music beds)? | Video only this wave |
| Q7 | Transcribe speech in user uploads for search ("the clip where I say 'launch'")? Uses Groq Whisper minutes | Off; revisit after launch |
| Q8 | Approve a 1k-shot pilot of the vision captioning to measure real cost before the full backfill | Yes, pilot first |
| Q9 | If Area 7 must ship before backend.md's media pipeline (11.6) and CDN (12.4), may the library run on today's upload helpers and presigned URLs as a stop-gap? | No: Area 7 waits for 11.6; the platform library (Area 6) does not |
| Q10 | Replace the studio's four Unsplash "Add stock footage" stills with real library search? (A visible control, so it needs your OK) | Replace when 6.6 ships |
| Q11 | How long may we keep anonymised search queries for tuning? | 90 days |
| Q12 | Keep originals for Pro (more storage cost), or always delete after transcode as proposed? | Delete after transcode; offer mezzanine download |

---

## 17. What other teams depend on from this doc

| Consumer | Contract |
|---|---|
| **Wave 2 design** | Screens and states in §3 and §3.7: Library panel, `/dashboard/library`, upload tray, details drawer, storage meter, curation console, "why / swap" result card, Asset and Collection chips |
| **Wave 3 runtime** | Agent tools `search_broll` and `place_broll` (§8.3); the `broll:` asset key and `GET /library/media` for preview resolution (§8.1); one-version-per-placement; the run event "operation applied" carries `pick_id` |
| **Backend Architect** (`architecture/backend.md`) | Add `ASSET_NOT_AVAILABLE` and `STORAGE_QUOTA_EXCEEDED` to `ErrorCode`. The ranked-search cursor exception (§7.1). `purpose: "library"` and `on_ready: {library}` on generic uploads. `broll`-class kinds `broll.library_ready`, `broll.index`, `broll.sweep`. The second cookie hostname `library.media.clipnera.com` in `/media/session` |
| **Flags and remote config** (`06-flags.md`) | Flags `broll_platform_library` and `broll_user_library` as catalogued there, with the off-semantics in §9.1. The new remote-config keys in §9.2, and the storage quota priced at 1 / 25 GiB (replacing the 2 / 50 GiB placeholders). `STORAGE_QUOTA_EXCEEDED` and `UPLOAD_TOO_LARGE` as plan errors |
| **Billing** | `Entitlements.library` block shown in the plan comparison |
| **Editor** | Server-side `broll:` check in `EditorService.apply`; fixtures with a library asset |
| **Privacy and account** | Delete the personal workspace's `w/{workspace_id}/` prefix on account deletion; AI-shot file cleanup (§10.9) |
| **Infrastructure** | pgvector on RDS (`rds_superuser` for `CREATE EXTENSION`); the second CloudFront cookie hostname; `broll` worker class |
