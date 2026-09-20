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
  tests/          pytest tests
frontend/         Next.js app (app router)
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
