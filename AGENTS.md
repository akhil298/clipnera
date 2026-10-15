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
  agent_runtime/  Provider-neutral tool loop and typed tool boxes
  clients/ai/     AI clients; roles.py picks a model per role (LLM_PROFILE), cassette.py for evals
  evals/          Golden set + injection cases (python -m evals.runner)
  tests/          pytest tests
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

## AI editor notes
- The studio (`/studio/[id]`, OpenCut) saves every edit to the backend as Timeline ops (`frontend/opencut/src/clipnera/backend-sync.ts`); mapping in `frontend/opencut/BRIDGE.md`.
- The AI chat is the studio's right-hand column (`clipnera/ai-panel.tsx`). Files dropped there or on the Editor home go to the media library; `clipnera/footage.ts` follows each one (upload → analysis step → ready), posts what the AI found (`understanding/findings.py`), and holds a prompt until the files are understood.
- AI steps (`brain/plan_ir.py` StepKind, compiled in `brain/compile.py`): structure, tighten, beat_sync, music, flash, reframe, look, zoom, transitions, title, callouts, captions, sfx. Zooms and transitions are clip keyframes; `clipnera/bridge.ts` maps them to the studio's animations both ways. Sounds come from `brain/library.py` (the same shelf as the Sounds tab). `brain/polish.py` adds a short's finishing touches by rule.
- "Edit the video" is a full edit (`brain/full_edit.py`): everything said stays, in order, minus what the analysis marks as false starts, earlier takes and off-camera talk (`mud.trims`, from `understanding/reading.py` and `analyzers.find_retakes`), tightened, in the footage's own shape, with zooms, on-screen numbers and captions. Only a request for a short, a reel, a clip or a length goes to the director as a cut-down.
- A new edit request replaces the main cut even where the user changed shots (the plan card says so; Undo restores it).
- Opening a project must not save anything: `BackendSync` remembers what the studio's defaults add (`shownExtra`), or every AI item would be logged as changed by the user and become off-limits to the AI.
- Rebuild the studio's stylesheet after changing classes under `frontend/opencut/src`: `cd frontend/opencut/tools && npm run build`.
- Prompts: `POST /api/v1/editor/projects/{id}/turns` → `brain/turns.py`; plans: `/api/v1/editor/plans/*` (`brain/api.py`).
- The AI never writes frame times: the director names moments by id (PlanIR); `brain/solvers/` place frames.
- Agent edits go through `EditorService.apply` with an `Actor`: human ownership, op budgets and the never-do list (`brain/invariants.py`) apply there.
- Feature flag `agent_editor` gates it all; it can be on for named test users only (`/admin/features`).
- Design docs: `AI Editor/BLUEPRINT.md`, build list `AI Editor/TODO.md`.

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
