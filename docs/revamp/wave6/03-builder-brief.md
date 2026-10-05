# Wave 6 — builder brief (read after 00-agent-brief.md)

You build one real screen of the new app inside `frontend/app/v2/...`. Read these first:
- `docs/revamp/wave6/00-agent-brief.md`: the hard rules (ownership, no writing git commands, no `next build`, palette).
- `docs/revamp/wave6/01-platform-api.md`: `apiFetch`, `ApiError`, `useFlag`, query keys, the v2 tree, and preview with `?ui=new`.
- `docs/revamp/wave6/02-ui-catalog.md`: every shared component. Import from `@/components/ui`. Never hand-roll something that is already there.
- `docs/revamp/wave6/07-visual-direction.md` (the Design Director is still writing it; if it exists, it overrides 02-design-system). Use `cn-*` tokens only, so token updates flow through automatically.
- Your screen spec section in `docs/revamp/screens/` and the matching "What Clipnera should take" items in `docs/revamp/research/{perplexity,lovable-visual,cardboard-compass}.md`.
- The mockup for your screen under `frontend/app/design-system/screens/**`, if one exists. It is your starting point: **copy** what's useful into your own folder and turn it into a real, data-backed screen. Never edit or import from the mockup folder.

How to build:
- The page file is a server component, and interactivity lives in client islands. Fetch real data through typed wrappers in `lib/api/<your domain>.ts` built on `apiFetch`. Check every field against the Pydantic schema in `backend/**/schema.py`. If something is missing, write a typed stub marked `// NEEDS-BACKEND: <METHOD path>` and say so in your report.
- Legacy code under `components/dashboard`, `components/landing`, `components/auth` etc. is **read-only reference**: study it so no feature is lost, but don't import its components into v2. You may import pure helpers from `lib/` when they have no UI.
- Design every state: empty, loading (skeleton), error (with an action), partial and full, plus a 360 px layout.
- Make it feel finished, with no "TODO" UI. This should be best-in-class: calm, fast and prompt-first.
- Type-check: `cd frontend && npx tsc --noEmit -p . 2>&1 | grep -E '<your paths>'` must print nothing.
