# Wave 6 — shared brief for every agent

Date: 4 October 2026. The owner asked for a complete, no-compromise redesign of every screen as an AI-first video editor, taking cues from **Perplexity** (answer-engine calm, one prompt that does everything, threads, sources, follow-ups), **Lovable** (prompt-first home, chat left / live preview right, versions) and **Cardboard / compass.cardboard.ai** (agentic video editor: conversation drives the timeline).

Read before you start: `AGENTS.md`, `docs/revamp/01-experience-principles.md`, `docs/revamp/02-design-system.md`, `docs/revamp/04-architecture.md`, `docs/revamp/architecture/frontend.md` (§1 routing, §3 data, §8.4 file ownership), and your own screen spec under `docs/revamp/screens/`. Once it exists, `docs/revamp/wave6/07-visual-direction.md` overrides `02-design-system.md` wherever they disagree.

## Owner decisions (locked 4 Oct 2026)

1. **Base:** build on the existing revamp work (design system, `components/ui/*`, mockups under `app/design-system/screens/*`). Reuse it and improve it. Don't start over.
2. **Palette:** amber accent on neutral near-black, with emerald, rose and sky for status only. Don't add any other hue. Violet is retired. Everything else is open: layout, type, components, motion, flows.
3. **Rollout:** every new screen lives in the new tree (`app/v2/...`) and is reached through `middleware.ts` rewrites behind the `new_ui_*` flags. The legacy UI under `app/dashboard`, `app/admin` and `components/dashboard` stays and still works. **Don't edit or delete legacy UI files.** That is how this wave satisfies the AGENTS.md UI rule. Removals only happen at cutover, with the owner's sign-off.

## Hard rules

- **Write only inside the paths you own** (they're listed in your task). Every other file is read-only to you. If you need a change to a shared file, write it under "Requests" in your report.
- **Never run** `git stash`, `git checkout`, `git reset`, `git commit`, or any other git command that writes. Other agents and sessions are editing this tree right now.
- **Never run `next build`.** Type-check with `cd frontend && npx tsc --noEmit -p . 2>&1 | grep -E '<your paths>'` and fix only errors in your own files.
- **Only the Platform agent installs npm packages.** Everyone else works with what is in `frontend/package.json`.
- **Never read `.env*` files.** Never print secrets.
- **API contracts:** every backend call uses a typed wrapper whose types exactly match the Pydantic schema in `backend/**/schema.py`. Responses use `{ data, message, error }`. Don't invent endpoints. If an endpoint you need is missing, build the screen against a typed stub in `lib/api/<domain>/` marked `// NEEDS-BACKEND: <endpoint>` and list it in your report.
- **Design rules:** use `cn-*` tokens only (no raw hex, no arbitrary `[..px]` sizes, no new z-indexes). Use the `components/ui/*` primitives. Meet WCAG 2.2 AA. Every interactive element gets hover, focus, pressed, disabled, loading and error states. Respect reduced motion. Make every screen work at 360 px wide.
- **Real states:** every screen designs empty, loading, error, partial and full data. Don't show fake numbers where real data is missing.
- **Code quality (AGENTS.md):** no dead code, small focused components, and reuse the existing helpers in `lib/` and `lib/design/`.

## Report (your final message)

Keep it to 25 lines or fewer: the files you created, what works, typecheck status for your paths, `NEEDS-BACKEND` items, requests for changes to shared files, and open owner questions.
