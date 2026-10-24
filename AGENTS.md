# Clipnera Project Context

## Overview
Clipnera is a video clipping platform. It automates clipping, transcription, captioning, and social media content generation from long-form videos.

## Stack
- **Backend**: FastAPI (Python 3.12), PostgreSQL, SQLAlchemy 2.0, Alembic migrations
- **Frontend**: Next.js 15, React 19, TypeScript, Tailwind CSS 3.4, Recharts
- **AI/ML**: Groq, Anthropic APIs, WhisperX 3.7, faster-whisper, OpenCV, FFmpeg
- **Auth**: python-jose, passlib/bcrypt, Authlib

## Project Structure
```
backend/          FastAPI app — routes, services, schemas, DB models
  core/           Config, DB session, middleware, security, exceptions
  auth/           JWT-based auth (route.py, service.py)
  user/           User management
  subscription/   Plans, entitlements, billing
  clip/           Clipping engine
  pipeline/       Clipping pipeline
  audio/          Audio enhancement & extraction
  transcription/  WhisperX-based transcription
  analytics/      Analytics/reporting
  notifications/  Notifications system
  workspace/      Project/workspace management
  brand_kit/      Brand kit management
  clip_generation/ AI clip generation
  subtitle_styling/ Caption/subtitle styling
  depth_captions/ Depth-aware captions
  video_processor/ FFmpeg + OpenCV video processing
  content_intelligence/ AI scoring/analysis
  editor/         Timeline v1, ops (+ inverses), op log, undo/redo, human ownership (history.py)
  brain/          AI editor: router, refs, modifiers, director, PlanIR, solvers/, compile, rulebook/,
                  score, plans + execution, verify/repair, critic, credits, style memory, metrics
  understanding/  Per-asset Media Understanding Documents (MUD), LCV text view, media tools
  beats/          Pro clips' graphic beats: planner (word ids -> proven beats), kit (clean assets), compose
                  (grade, zoom rhythm, Chrome-rendered beats, mattes, SFX), renderer/ (no-npm Chrome driver)
  agent_runtime/  Provider-neutral tool loop and typed tool boxes
  clients/ai/     AI clients; roles.py picks a model per role (LLM_PROFILE), cassette.py for evals
  evals/          Golden set + injection cases (python -m evals.runner)
  tests/          pytest tests
desktop/          Clipnera Studio for Mac (Electron + React + TS); build phases in desktop/PHASES.md
frontend/         Next.js app (app router)
  opencut/        Vendored OpenCut studio (MIT); src/clipnera/ = bridge to Timeline v1, sync, AI chat
  app/            Pages (dashboard, auth, landing)
  components/     UI components
  lib/            Utilities, API client, auth helpers
  hooks/          React hooks
  types/          TypeScript types
.kilo/            Kilo config
.vscode/          VSCode settings (IGNORED)
generated_clips/  Output clips (IGNORED)
backend/.env      Environment secrets (IGNORED)
```

## Backend Architecture
- **Pattern**: Route → Service → Repository (when applicable)
- All routers are prefixed with `/api/v1` in `main.py`
- Custom exception handling via `CustomException` in `core/exceptions.py`
- Middleware registered via `register_middlewares()` in `main.py`
- Database: PostgreSQL via SQLAlchemy async (asyncpg)
- Migrations: Alembic in `backend/alembic/versions/`

## Key Files
- Entry point: `backend/main.py`
- Config: `backend/core/config.py` (uses pydantic-settings, env vars)
- DB: `backend/core/database.py`
- Auth service: `backend/auth/service.py`
- Auth routes: `backend/auth/route.py`

## Development
- Backend: `cd backend && uvicorn main:app --reload`
- Frontend: `cd frontend && npm run dev`
- Tests: `cd backend && pytest tests/`
- Migrations: `cd backend && alembic revision --autogenerate -m "message"`
- Apply migrations: `cd backend && alembic upgrade head`

## Conventions
- Python: snake_case files/functions, type hints everywhere
- Frontend: PascalCase components, camel_case hooks/utilities
- API responses: `{ "data": ..., "message": ..., "error": ... }` pattern
- Always create Alembic migration after model changes
- Environment files: `.env` is gitignored; use `.env.example` as template
- Generated files (clips, transcriptions) are gitignored

## Reel engine notes
- The premium footage reel (`engine = "premium"` on `edit_projects`, Pro) is edited end to end by `backend/reel_engine` in one job (`edits.premium`): listen (voice/music separation with Hybrid Demucs, audio kind from stem levels AND the transcript), watch (shots, face track, contact sheets), one director call (recipe from `reel_engine/data/recipes.json`, hooks, story, sections, beats, captions, music), verify (best hook, labels against frames), compile, assets, picture, layout, graphics, sound, review (up to 2 passes, keeps the best).
- Everything is written into one Edit Plan (`reel_engine/plan.py`); the reels board shows it through `PremiumResponse` (`reel_engine/jobs.summary`).
- Agents ask for assets; `reel_engine/assets.Scout` searches the user's assets, the kit, made assets and the packs, makes what is missing (sounds, scores) and stores it in `reel_assets` (scope global or user) so later reels reuse it.
- A voice is never cut inside a word or sped up; a song never becomes captions; one story graphic on screen at a time; graphics never cover a face (real face detection) and avoid busy detail (food, hands).
- Run it on local files: `cd backend && venv/bin/python -m reel_engine clip.mp4 --out out/reel.mp4` (writes the plan beside the reel).
- Credits are taken when it starts and refunded if it fails. Migration `20261022010000_add_reel_engine`.
- Synthesis (SFX pack, music beds, scores, on-demand foley) lives in `backend/motion/synth.py`; footage graphic templates in `backend/beats/renderer/footage.js`.
- The reel maker is one screen (`FootageReelForm.tsx`): videos, photos, one voiceover and/or a YouTube link (`source_url`), at least one of them; no model picker (GPT-Astra edits every plan); language `auto`. Pro gets `premium`, others `classic` with autopilot. A link is checked at create (`_check_source_link`: YouTube, plan length) and fetched at 1080p in the API process (`jobs.fetch_link` via `in_background`, like the clips flow: only the API machine has fresh YouTube cookies), then the edit starts as if uploaded. Migration `20261023010000_add_edit_source_url`.
- Signature effects (Orbit, Headline Wall, Framebreak, Vertigo, Green Screen...) are a catalog the director picks from: `reel_engine/data/effects.json` + `reel_engine/effects.py` + `beats/renderer/effects.js`. Preview them: `scripts/effects_gallery.py talking_head.mp4 out/`.
- Sound effects, Lottie motion graphics and animated emoji libraries: `scripts/build_asset_libraries.py` (files gitignored, manifests tracked; deploys build them on the worker).
- One reel per strong moment: `reel_engine/moments.py` ranks self-contained moments from the transcript (light model); `pipeline.run_many` analyses once and edits each moment with the director limited to that window (dense frames, open on its hook, end on its payoff). The premium job charges each extra reel before making it (`allow`) and stops when credits run out; reels land in `edit_projects.reels` (migration `20261023020000_add_edit_reels`), `REEL_MAX_REELS_FREE/PRO`.
- Framing (`reel_engine/track.py` + `render.framing`): every face 4×/s with lip motion; the camera follows the speaker, stacks two people trading lines, and frames detail/movement (focus track) when nobody is on screen — never a blind centre crop.
- Editing styles (`reel_engine/data/styles.json` + `styles.py`): the director picks one; it caps and favours effects, caption looks, caption styles, moods and pacing.
- Related pictures: Wikimedia Commons PD/CC0 photos (User-Agent must carry a contact URL), kit 3D-object cards when no photo fits, generated photos behind `REEL_IMAGE_PROVIDER` (`gemini` needs billing on the Google project; `openai` needs an `IMAGE_MODEL` deployment).
- Explainer scenes (`reel_engine/scenes.py`, catalog `reel_engine/data/scenes.json`, drawn by `beats/renderer/scene.js` with Three.js r159 in `vendor/`): where a speaker explains how or why, the director asks for a 3D scene (reveal, inside, compare, many, force, transform, flow, cycle, scale, wrong, location) in a world (sky, space, macro, body, ocean, room, studio, city); actors are built forms or the kit's 3D objects, labels are pinned and typed in, a figure on a label must be the one said. Cut to like an insert; photos and story graphics under it give way. Veo for scenes the kit cannot show only with `REEL_SCENE_VEO`. Chrome needs `--enable-unsafe-swiftshader` for WebGL without a GPU.
- The beats renderer must exit when done (Chrome in its own process group; `process.exit`); a hang there once shipped reels without captions. A reel is never shipped without its captions (`pipeline.draw`).

## AI editor notes
- The studio (`/studio/[id]`, OpenCut) saves every edit to the backend as Timeline ops (`frontend/opencut/src/clipnera/backend-sync.ts`); mapping in `frontend/opencut/BRIDGE.md`.
- The AI chat is the studio's right-hand column (`clipnera/ai-panel.tsx`). Files dropped there or on the Editor home go to the media library; `clipnera/footage.ts` follows each one (upload → analysis step → ready), posts what the AI found (`understanding/findings.py`), and holds a prompt until the files are understood.
- AI steps (`brain/plan_ir.py` StepKind, compiled in `brain/compile.py`): structure, tighten, beat_sync, music, flash, reframe, look, zoom, transitions, title, callouts, captions, sfx. Zooms and transitions are clip keyframes; `clipnera/bridge.ts` maps them to the studio's animations both ways. Sounds come from `brain/library.py` (the same shelf as the Sounds tab). `brain/polish.py` adds a short's finishing touches by rule.
- "Edit the video" is a full edit (`brain/full_edit.py`): everything said stays, in order, minus what the analysis marks as false starts, earlier takes and off-camera talk (`mud.trims`, from `understanding/reading.py` and `analyzers.find_retakes`), tightened, in the footage's own shape, with zooms, on-screen numbers and captions. Only a request for a short, a reel, a clip or a length goes to the director as a cut-down.
- A new edit request replaces the main cut even where the user changed shots (the plan card says so; Undo restores it).
- Opening a project must not save anything: `BackendSync` remembers what the studio's defaults add (`shownExtra`), or every AI item would be logged as changed by the user and become off-limits to the AI.
- Rebuild the studio's stylesheet after changing classes under `frontend/opencut/src`: `cd frontend/opencut/tools && npm run build`.
- Studio chat prompts: `POST /api/v1/editor/projects/{id}/agent` (SSE) → `brain/studio.py`, one model (role `studio`) with every tool: read, `apply_edits` (each call its own undo step), `look_at_frames`, studio actions (playhead, select, play, panel; run by `clipnera/agent-ui.ts`), `plan_edit` (hands whole edits to `brain/turns.plan_request` → director), `start_export`, to-dos, `ask_user`. Undo/redo/split/delete still skip the model. The old one-shot `POST .../turns` → `brain/turns.py` is still served; plans: `/api/v1/editor/plans/*` (`brain/api.py`).
- The AI never writes frame times: the director names moments by id (PlanIR); `brain/solvers/` place frames.
- Agent edits go through `EditorService.apply` with an `Actor`: human ownership, op budgets and the never-do list (`brain/invariants.py`) apply there.
- Feature flag `agent_editor` gates it all; it can be on for named test users only (`/admin/features`).
- Design docs: `AI Editor/BLUEPRINT.md`, build list `AI Editor/TODO.md`.

## Graphic beats (YouTube-link clips, Pro)
- After clip generation, `beats/service.plan_project_beats` asks one model (step `beat_planning`) which word gets which graphic; `beats/planner.prove` keeps only beats whose words were said (figures digit for digit). Stored in `analysis_json["beats"]`; a clip with beats does not draw its old `motion` cues.
- Exports run `beats.compose.with_finish` after `with_broll` and before captions: theme LUT (`beats/grade.py`), punch-in every other sentence on follow layouts, each beat rendered by `beats/renderer/render.mjs` (headless Chrome, `CHROME_PATH`) to a transparent MOV, text behind the speaker via a MODNet matte, SFX from `static/motion/sfx`. Captions step aside under cards (`MotionSource.quiet`).
- Assets only from `static/motion/kit/manifest.json` (built by `scripts/build_motion_kit.py`, made images by `scripts/generate_kit_images.py`, synced through S3); never from `static/motion/library/`. Brief: `docs/motion_kit/ASSET_KIT.md`; reel study: `before_after_reels/ANALYSIS.md`; benchmark: `scripts/beats_benchmark.py`.
- Pro judgement steps run on GPT-6 Astra through `LLM_PRO_STEP_MODELS`.

## Notes
- `.vscode/` is fully gitignored — do not commit VSCode files
- `generated_clips/` and `backend/generated_clips/` are gitignored
- The `.kilo/` directory is for Kilo tool config (plans, worktrees)

## Strict Rules

### 🔒 Never Read or Expose Secrets
- **NEVER** read `.env`, `.env.local`, `.env.production`, or any file containing secrets
- **NEVER** print, log, or output environment variable values, API keys, tokens, passwords, or credentials
- **NEVER** ask the user for secrets, keys, or credentials
- **NEVER** hardcode secrets in source code
- If you need a config value, reference `backend/core/config.py` — it uses pydantic-settings and reads from env vars safely
- If you need to reference a secret in code, only use the variable name (e.g., `settings.DATABASE_URL`) — never its value

### 🧹 Code Quality — No Messy Code
- Write clean, optimized code — no dead code, no unnecessary complexity
- Follow DRY principles — reuse existing utilities, services, and patterns
- Keep functions focused and small — single responsibility
- Use existing helpers and utilities from `backend/` and `frontend/lib/` — do not duplicate logic
- Optimize for readability and performance — no premature optimization, but no obvious inefficiencies either
- If a pattern exists in the codebase, follow it — do not reinvent

### 🎨 UI Rules — Cannot Remove Without Verification
- **NEVER** remove, hide, or break any UI component, page, or feature without explicit user confirmation
- Any UI change must preserve existing functionality — no destructive changes to the user interface
- Before modifying a UI component, verify its purpose and confirm the intended change with the user
- Preserves existing layout, styling, and user flows — do not break existing design patterns
- If asked to change UI, first explain what will change and get confirmation

### 🔗 API Contracts — Correct and Consistent
- Every API endpoint must have a matching type on both frontend and backend — no mismatched contracts
- **Backend**: Define request/response schemas in `schema.py` using Pydantic models — always
- **Frontend**: Define matching TypeScript types in `frontend/lib/types.ts` or near the consuming code — always
- Request types on frontend must exactly match the backend schema fields, names, and types
- Response types on frontend must exactly match the backend response schema
- Never create an API with inconsistent types between frontend and backend
- Before creating a new API endpoint, ensure the frontend types are written/updated in the same task
- Never create a frontend API call (`lib/api.ts`) without verifying the backend route exists and the types match
- API response format must always be `{ "data": ..., "message": ..., "error": ... }` — consistent across all endpoints
