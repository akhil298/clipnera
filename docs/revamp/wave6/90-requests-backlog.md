# Wave 6 — cross-owner requests and NEEDS-BACKEND backlog

Collected from builder reports by the lead. An integration agent works through this list after each batch.

## Design System (components/ui)
- Sidebar rail is 56 px and TopBar is 48 px (07 §5.2). Today they're `w-16` and `h-14`. (shell)
- MobileTabBar centre "+": use accent-subtle. Add a fade keyframe for the 120 ms page cross-fade. (shell)
- Add SaveBar, PlatformMark, DateTimeField, RadioGroup (spec 04). Also RadioGroup, the Select rebuild, CreditMeter, ActivityIndicator, the PromptBar modes/onDropFile/footer props, SelectionBar, PromptQueue, the version-history item, player chrome and Timeline (DS leftovers).
- 02-design-system.md §11 should point at wave6/02-ui-catalog.md.
- Fix or remove the mockup pages editor/export and editor/reels, which import the missing ./ExportShare and ./ReelBoard.

## Platform
- Add a pre-hydration `data-theme` script to app/layout.tsx (the light theme flashes on load). (shell)
- Rewrite /dashboard/connect/* under new_ui_export; rewrite the legal and functional pages under new_ui_auth. Add NEXT_PUBLIC_APP_ENV. Decide between hls.js and MP4-only for the share page. (spec 04)
- Wire lib/routing/auth-rules.ts into middleware once Area 2 lands it.

## Naming and ownership
- `lib/api/account.ts` (shell) clashes with the future `lib/api/account/**` (Area 9). Rename one of them.
- Move `listRecentProjects` into lib/api/projects once it exists, and invalidate `accountKeys.recentProjects()` on job events.
- Add the reels, legal, v2 connect and editor sub-folders to frontend.md §8.4 (specs 02, 04).

## Projects list follow-ups
- Upload should accept `?prompt=` alongside `?url=`. The empty-page composer on Projects sends both.
- Projects list wraps its own ToastProvider, but the shell already mounts one. Remove the duplicate.
- PromptBar needs a `modes` prop (DS-9). Projects hides the mode switch with CSS for now.

## Home follow-ups
- PromptBar: `modes={[]}`; allow sending an empty field when a context is attached; a `rounded-cn-3xl` hero variant; make + a popover anchor; add `onDropFile` and `footer` slots and a `source` ContextChip kind.
- Project page: handle a project that is downloaded but whose run never started (offer Start).
- Content formats: `backend/formats/` exists only on the `feature/v2` branch (taxonomy.py, visual_probe.py). On clipnera only `__pycache__` remains and nothing imports it. Home's 11 starter templates are hard-coded until the owner decides.

## Project page follow-ups
- `getProject` is duplicated in lib/api/clips.ts. Switch it to lib/api/projects.ts, which now exists.
- The shell DOES mount ToastProvider (components/shell/AppShell.tsx). Builders that added their own toast or alert fallbacks should switch to useToast.
- Move the export custom_config mapping out of lib/api.ts into a shared helper (lib/api/clips.ts repeats it).
- The scheduler should accept `?project=&clip=` so Publish arrives with the clip preselected.

## Backend registry
- New flags: share_links, post_analytics (spec 04).

## NEEDS-BACKEND
- PATCH /me {active_workspace_id} (shell)
- PATCH /clips/projects/{id} for rename (the legacy UI only renamed in the browser; v2 rolls back with an error until this exists)
- Real folders: GET/POST /folders, PATCH/DELETE /folders/{id}, POST /projects/move (legacy folders are browser-only)
- GET /clips/projects/{id}, plus server-side filters and paging on GET /clips/projects, plus a 30-day trash (delete is permanent today)
- `/pipeline/start` has no prompt field (API-8, PipelineOptions.prompt), so typed instructions and templates reach nothing yet
- Pipeline start is client-driven (the tab must stay open). Needs a server-side on_ready, e.g. POST /imports/youtube
- backend/pipeline has no schema.py (untyped dicts)
- DELETE /clips/item/{clip_id} (clip delete fails inline until this exists)
- GET /projects/{id} (API-9) with credits charged/returned and the chosen run options. Credits are summed from the ledger for now.
- Persist run options on PipelineState so Retry keeps the settings
- The status payload needs an explicit cancelled state (today a stopped run is detected by matching the error text)
- GET /projects?sort=recent&limit= with a schema; today /clips/projects returns every clip (shell)
- Spec 04 §22: about 40 items (share endpoints, reel publish, live post updates, reel chat reply, admin permissions endpoint, admin audit log, platform analytics)
- Spec 02 and spec 03 have their own lists in their API-needs sections
