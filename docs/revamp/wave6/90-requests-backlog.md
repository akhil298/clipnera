# Wave 6 — cross-owner requests and NEEDS-BACKEND backlog

Collected from builder reports by the lead. An integration agent works through this list after each batch.

## Design System (components/ui)
- ✅ (DS-E) Sidebar rail is 56 px and TopBar is 48 px (07 §5.2). Today they're `w-16` and `h-14`. (shell)
- ✅ (DS-E; the shell still needs `emphasis: true` on the `new` tab in PhoneNav.tsx) MobileTabBar centre "+": use accent-subtle. Add a fade keyframe for the 120 ms page cross-fade. (shell)
- Add SaveBar, PlatformMark, DateTimeField, RadioGroup (spec 04). Also RadioGroup, the Select rebuild, CreditMeter, ActivityIndicator, the PromptBar modes/onDropFile/footer props, SelectionBar, PromptQueue, the version-history item, player chrome and Timeline (DS leftovers).
- 02-design-system.md §11 should point at wave6/02-ui-catalog.md.
- ✅ (DS-E) Fix or remove the mockup pages editor/export and editor/reels, which import the missing ./ExportShare and ./ReelBoard.

## Platform
- ✅ Add a pre-hydration `data-theme` script (placed in app/v2/(app)/dashboard/layout.tsx, since only the v2 shell reads data-theme) to app/layout.tsx (the light theme flashes on load). (shell)
- Rewrite /dashboard/connect/* under new_ui_export; rewrite the legal and functional pages under new_ui_auth. Add NEXT_PUBLIC_APP_ENV. Decide between hls.js and MP4-only for the share page. (spec 04)
- ✅ Wire lib/routing/auth-rules.ts into middleware once Area 2 lands it.

## Naming and ownership
- ✅ (now lib/api/me.ts; note Area 9 still plans `lib/query/keys/account.ts`, which the shell owns: extend it, don't recreate) `lib/api/account.ts` (shell) clashes with the future `lib/api/account/**` (Area 9). Rename one of them.
- ✅ Move `listRecentProjects` into lib/api/projects once it exists, and invalidate `accountKeys.recentProjects()` on job events.
- Add the reels, legal, v2 connect and editor sub-folders to frontend.md §8.4 (specs 02, 04).

## Projects list follow-ups
- Upload should accept `?prompt=` alongside `?url=`. The empty-page composer on Projects sends both.
- ✅ Projects list wraps its own ToastProvider, but the shell already mounts one. Remove the duplicate.
- PromptBar needs a `modes` prop (DS-9). Projects hides the mode switch with CSS for now.

## DS-E follow-ups
- HomeComposer: drop HIDE_MODES/mode/onModeChange; use `onDropFile` (its overlay is still rounded-cn-2xl), the `source` chip kind, `footer={<ComposerFeedback/>}` and `attachMenu`. FirstProject: drop the radiogroup CSS hack.
- Still to build in components/ui: MomentCard, TimelineChangeMarker, CreditMeter, SaveBar, PlatformMark, DateTimeField, RadioGroup, the Select rebuild.

## Home follow-ups
- PromptBar: `modes={[]}`; allow sending an empty field when a context is attached; a `rounded-cn-3xl` hero variant; make + a popover anchor; add `onDropFile` and `footer` slots and a `source` ContextChip kind.
- Project page: handle a project that is downloaded but whose run never started (offer Start).
- Content formats: `backend/formats/` exists only on the `feature/v2` branch (taxonomy.py, visual_probe.py). On clipnera only `__pycache__` remains and nothing imports it. Home's 11 starter templates are hard-coded until the owner decides.

## Project page follow-ups
- ✅ `getProject` is duplicated in lib/api/clips.ts. Switch it to lib/api/projects.ts, which now exists.
- ✅ The shell DOES mount ToastProvider (components/shell/AppShell.tsx). Builders that added their own toast or alert fallbacks should switch to useToast.
- Move the export custom_config mapping out of lib/api.ts into a shared helper (lib/api/clips.ts repeats it).
- The scheduler should accept `?project=&clip=` so Publish arrives with the clip preselected.

## Header actions follow-ups
- ✅ Desktop has two credit entry points (the sidebar CreditSummary and the header CreditsPopover). Reuse CreditsPopover in the sidebar, or hide the header one at lg+ (owner question).
- Toasts sit at bottom-4 and overlap the 56 px phone tab bar (DS).
- Credits buttons should link to /dashboard/plans and /dashboard/payment?pack= once Area 9 builds them.
- ✅ Move `stepWords` and `runPercent` from components/projects/detail/run.ts into lib/ (they're shared with header actions).

## Sign-in follow-ups
- ✅ Home (Area 3): mount `<FirstRunGate carriedIntent={restored} />` in HomeScreen, or onboarding never shows. Also export a non-consuming `peekPendingPrompt` from components/home/handoff.ts (the key is duplicated in auth-v2/session.ts).
- ✅ Platform: wire `authRedirect` from lib/routing/auth-rules.ts into middleware. Add /dashboard/welcome to the new_ui_dashboard rewrites with a full-page fallback.
- ✅ Move onboarding/connections.ts into a shared lib/api/social.ts plus lib/query/keys/social.ts.
- **Owner decision (legacy file):** app/login/google/page.tsx should go to `takeSignInNext() ?? '/dashboard'` and call `markSignedIn()`. Without this, `?next=` only works once the dashboard is on the new UI. This edits a legacy file, so it needs the owner's OK.

## Parity with clipnera commits merged on 2026-10-07 (aa8b4e9, 5ead812)
- ✅ **Onboarding is now real on the backend:** (v2 welcome uses GET/POST /onboarding and /me onboarding_completed; it opens on Home only, while legacy blocks the whole dashboard) GET/POST /onboarding (backend/onboarding/) and `onboarding_completed` on /me. The v2 onboarding (components/onboarding) must use these instead of localStorage, and match the legacy WelcomeForm fields (components/referral/WelcomeForm.tsx).
- **Referrals:** ✅ v2 /dashboard/referrals (account menu → Refer and earn) and the Home InvitedByCard done; admin referrals page still open. Legacy has /dashboard/referrals (ReferralsView, InvitedByCard), ReferralCapture in the root layout (kept), and /admin/referrals. v2 needs a Referrals screen (Settings area or sidebar account menu) and an admin referrals page.
- ✅ **Expiring bonus credits:** legacy CreditsPopover and useEntitlements changed. The v2 CreditsPopover and the credit meter must show bonus credits and their expiry.
- **Upload charges at submit:** legacy UploadModal changed. The v2 upload flow must match the new charging behaviour.

## Upload follow-ups
- Shell: mount `<UploadTray/>` from components/upload/UploadStatus (pause and resume after the dialog closes).
- Project page: render `<ProjectUploadStatus projectId/>` while the file is still uploading.
- Platform: add `@modal/[...catchAll]/page.tsx` returning null.
- Home: use `PENDING_UPLOAD_KEY` from components/upload/handoff.ts. Send snake_case `audio_config` and pass `pipeline` to /clips/download (Home still has the legacy camelCase bug).
- Credits: add the bonus credit fields to the v2 `Entitlements` type.
- **Legacy bugs found (owner decision, clipnera):** (1) UploadModal sends audio_config in camelCase (aiDenoise, noiseSuppressionStrength…), but the backend reads snake_case, so Studio voice settings never apply. (2) UploadModal and lib/api DEFAULT_PIPELINE_STEPS omit `burn_in_export`, so legacy runs skip the pipeline's caption burn-in.
- Owner questions: strength 80 vs 90 sound identical (the backend maxes out above 70); add a language choice? offer max_clips?

## Playback follow-ups
- Platform: install hls.js for long sources (also needed by the share page); add "type": "module" to silence Node's MODULE_TYPELESS warning in lib tests.
- Owner: should clip audio on the picture track play in the editor preview? (Only audio tracks play today.) There's no backend Timeline renderer yet, so the preview approximates slide and zoom transitions.

## E1 follow-ups
- Platform: a paged apiFetch that also returns meta.next_cursor (for listRuns, listVersions, activity). Also build lib/realtime (R-1) so E4a can wire live run events.
- DS: point the mockup run/* files at lib/editor/dev/scenarios.ts (R-5). Add a `region` kind to ContextChip.
- Editor backend stubs to build: EB-2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 17, 18, 21 (see 02-editor.md).

## Export follow-ups
- Switch lib/api.ts exportProject (legacy, owner OK needed), lib/api/clips.ts exportClip and lib/api/projects.ts exportProjectBundle to `socialExportRequest` + `exportVideoProject` from lib/api/export/request.ts. exportProjectBundle sends no style_type today.
- Scheduler should read ?project=&clip=. R-2: add RenderCardSlot for the editor Outputs tab.
- Owner: is an estimated file size OK until EB-24 returns real sizes?

## Library + Brand kit follow-ups
- U12 export getLibraryUsage (storage meter); U13 handle /dashboard/library/mine?upload=1; Area 1 export dashboardSegments; Area 4 accept ?insert=broll:<id> (A4-1).
- DS promote: SectionNav, KeyValues, RadioGroup (cards), LibraryTile, justified grid, SaveBar, SettingsCard.
- U8 replaces components/settings/brand/intro/index.ts (keep the ChannelIntroSection({brandName}) export and the #channel-intro id).
- Owner: should the library hide non-public-domain sources (Pexels and Pixabay still appear)? Tab counts and storage stay hidden until real numbers exist. Should the brand font apply to burned captions?

## Settings follow-ups
- Area 1: add workspace, notifications and connections labels to ShellBreadcrumbs LABELS.
- Landing: show ACCOUNT_DELETED_NOTICE once when sessionStorage has cn_account_deleted (lib/api/messages/account.ts), then clear it.
- Lead: frontend.md lines 81 and 794 still say settings/[[...tab]].
- Owner: with new_ui_settings on, the only way back to the classic UI is /api/ui/override?mode=classic. OK? Importing BUSINESS from legacy LegalPage.tsx: OK?

## E3 composer follow-ups
- DS: `PromptContext.locked` on ContextChip (lock icon, no ×), and a hint tone on PromptBar (danger-text).
- E1: a `queue.update {turnId, prompt}` run-store action.
- Platform: one shared useOnline (copies exist in components/home and components/projects; the composer imports Home's).
- npm test only runs lib/. Component tests (components/editor/prompt) need adding to the test script.

## Backend registry
- **Broken on ui-revamp-wave6 after the merge:** `backend/feature_flags/registry.py` `REFERRAL_PROGRAM` FlagDefinition lacks the `owner`, `kind`, `created` arguments the wave6 FlagDefinition requires, so the module fails to import (and `scripts.gen_flag_types` can't run, so `referral_program` is missing from lib/flags/registry.gen.ts). The v2 Refer and earn entry is therefore always shown; gate it on `useFlag('referral_program')` once regenerated.
- Landing: BUSINESS and LEGAL_LINKS still come from components/legal/LegalPage.tsx; moving them to lib/legal.ts needs that legacy file to import from it (owner OK).
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
- POST /notifications/{id}/read (opening a row can't mark it read yet)
- DELETE /notifications should return the deleted ids, plus POST /notifications/restore (API-10), for a safe Undo
- GET /jobs?status=active (activity only covers clip runs; no reels, exports or renders)
- /pipeline/status/batch has no schema
- PATCH /me/preferences and onboarding_completed_at on /me (API-3); onboarding state is in localStorage per account for now
- Optional CONSENT_REQUIRED error code (API-2); the backend returns 400 TERMS_NOT_ACCEPTED for new accounts without consent
- Pipeline prompt is sent as clip_settings.prompt but nothing reads it (API-8)
- Editor media: EB-12 540p proxies, storyboard and waveform; a signed-URL endpoint for editor assets (url, proxy_url, expires_at, refresh); URLs for music and SFX; EB-18 transcript words in timeline time
- EB-24 async exports: POST /exports, GET /jobs/{id}, POST /jobs/{id}/cancel. Until then exports block, show no %, and editor-project exports are unavailable. The server ignores resolution, fps and quality options. EB-16: the export route has no envelope.
- B-roll library API (L-API-1: search, browse, details, favourites, report, media, collections) plus U9-B1 sort and U9-B2 source/source_url; no /library routes exist yet
- Brand kit: GET /subtitle-styles/presets returns a 500 (the service returns style_type/description/uses_ass and a dict config, but the schema wants id/is_preset and a str config; this is also broken on clipnera, though no legacy UI calls it). L-API-11 logo upload. logo_size and logo_opacity are read by no renderer.
- Account: L-API-5 created_at/terms_accepted_at, L-API-6 sessions and sign out everywhere (/auth/logout does nothing on the server), L-API-7 the uploads-in-AI switch, a language/region field
- GET /projects?sort=recent&limit= with a schema; today /clips/projects returns every clip (shell)
- Spec 04 §22: about 40 items (share endpoints, reel publish, live post updates, reel chat reply, admin permissions endpoint, admin audit log, platform analytics)
- Spec 02 and spec 03 have their own lists in their API-needs sections
