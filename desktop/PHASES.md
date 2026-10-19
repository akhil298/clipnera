# Clipnera Studio (Mac) — build phases

Design: https://claude.ai/artifact/BzuJz4bdGt6G4p4MEGuNas

The rule: build one phase, test it, mark it done, then start the next one.
Local builds are unsigned and run only on this Mac, so no Apple Developer account is needed until we share the app.

Stack: Electron + React + TypeScript (electron-vite) for the app, a Swift package for the video engine (from phase 3), and the existing FastAPI backend for login, credits and AI.

---

## Phase 1 — App shell ✅ done 2026-10-18
Goal: the app opens a window with the empty workbench, and every layout action is a command.
- [x] `desktop/` project: Electron + React + TypeScript, `npm run dev` / `build` / `test`
- [x] Secure window: context isolation, sandbox, minimal preload, macOS hidden title bar
- [x] Workbench layout: activity bar, side panel, viewer, timeline, AI panel, bottom panel (Activity / Problems), status bar
- [x] Amber-on-neutral theme tokens (dark first)
- [x] Command registry core (`id`, title, category, shortcut, `aiCanRun`, run), and every action recorded in the Activity log
- [x] First commands: show side panel view, toggle side panel / bottom panel / AI panel, with keyboard shortcuts
- [x] Tests: registry + layout unit tests, and a smoke test that launches the real app and runs a command

Tested: `npm run typecheck`, `npm test` (16 unit tests), `npm run test:e2e` (5 tests on the real app: regions, locked-down window, shortcut → command → Activity log, activity bar, View menu).

## Phase 2 — Sign in ✅ done 2026-10-18
Goal: sign in with Google from the app and stay signed in.
- [x] Backend: `POST /auth/desktop/start`, `GET /auth/desktop/callback`, `POST /auth/desktop/exchange` (PKCE, same Google account logic as the web login, no new table), schemas + TS types (`src/shared/api.ts`)
- [x] App: Google opens in the system browser and comes back to a one-time `127.0.0.1` port (works unpackaged, unlike a `clipnera://` link); session encrypted with a Keychain key (`safeStorage`)
- [x] Sign-in screen with the same 18+ / Terms consent as the web; signed-in name, plan and credits in the status bar; `account.signOut` command
- [x] Tests: 18 backend tests (`tests/test_desktop_auth.py`), 16 new app unit tests (PKCE, token store, loopback, session), 4 new end-to-end tests (consent, browser round trip, restart, sign out); smoke-tested the endpoints on a real local backend

**Owner setup before a real Google sign-in works:** in Google Cloud console → the existing OAuth client → Authorized redirect URIs, add `http://localhost:8000/api/v1/auth/desktop/callback` (local) and `<PUBLIC_API_URL>/api/v1/auth/desktop/callback` (prod).

Later (not this phase): longer sessions with refresh tokens, and a list of signed-in Macs.

## Phase 3 — Swift engine + importing footage ✅ done 2026-10-18
Goal: bring footage in; the app reads it, shows a thumbnail and makes a smooth editing copy.
- [x] `desktop/engine`: Swift video engine (AVFoundation), started by the app, JSON lines over stdio; `npm run engine:build` (swiftc, picks the SDK that matches the compiler, skips when up to date)
- [x] Probe (duration, size, fps, codecs, audio), JPEG thumbnails, 720p H.264 editing copy with progress, cancel
- [x] Media panel: import with ⌘I, File → Import Media…, or drop files anywhere on the window; progress; remove (original never touched)
- [x] Commands: `media.import`, `media.remove` (AI can't run them yet — removal gets AI access with undo in phase 5)
- [x] Tests: 9 engine integration tests on the real binary (ffmpeg makes sample files), 8 library tests, 3 end-to-end import tests

Open: macOS can't open WebM/MKV (YouTube downloads). Decide later: bundle an ffmpeg build to convert them on import, or ask users for MP4/MOV.
Not yet: the media list isn't saved between launches — that comes with the project file in phase 5.

## Phase 4 — Viewer & playback ✅ done 2026-10-18
Goal: click a file and watch it, with editor-style controls.
- [x] Click a file in Media to open it in the viewer (video plays its 720p editing copy, audio its original)
- [x] Play/pause (Space), J/K/L shuttle with 2× and 4× (reverse too), ←/→ frame steps, scrub bar, HH:MM:SS:FF timecode at the clip's frame rate
- [x] `clipnera-media://` serves byte ranges so seeking doesn't read the whole file
- [x] Commands, all AI-runnable: `player.open`, `player.togglePlay`, `player.play`, `player.pause`, `player.shuttleForward/Back`, `player.stepForward/Back`, `player.seek`, `player.playRange`
- [x] Tests: timecode/shuttle maths, seek queue, range serving, 7 end-to-end playback tests

Found and fixed: Chromium's decoder hangs if a seek starts before the last one finishes (fast frame steps froze playback) — seeks are now queued.

## Phase 5 — Project & timeline ✅ done 2026-10-18
Goal: a real edit — footage on a timeline, cut, trimmed, retimed, undone — saved to the project.
- [x] Opens the account's latest backend project (or a new 16:9 one); preview mode keeps a local project with the same op rules
- [x] Each file's small copy (720p H.264, AAC for audio) is uploaded (`assets/init` + S3 PUT) and added with `add_asset`, so the AI can use it; media list saved per project
- [x] Timeline v1 shared with the backend (`frontend/lib/editor/timeline.ts`, aliased as `@timeline`): edits show at once and the backend confirms them, one batch at a time
- [x] Timeline UI: tracks, clips, ruler, playhead, zoom, select, drag to move (snaps), drag edges to trim
- [x] Viewer plays the edit cut to cut (main video track), or one file in source mode (Esc goes back)
- [x] Commands: `timeline.append/split/delete/lift/move/trim/setSpeed/setVolume/select/zoomIn/zoomOut`, `edit.undo/redo`, `player.showTimeline`; Edit menu runs them
- [x] Tests: op builders checked by the shared applyOps, program playback maths, library upload flow, 6 end-to-end timeline tests against a fake backend that applies ops the same way

Later: overlay/text/audio tracks play in the viewer (phases 10–12); waveforms and thumbnails on clips.

## Phase 6 — ⌘K command palette ✅ done 2026-10-18
- [x] ⌘K (and View → Show All Commands…) lists every command that runs without arguments, with its shortcut and whether the AI can run it
- [x] Fuzzy search over title, category and id; ↑/↓, Enter runs, Esc closes
- [x] Tests: search ranking, end-to-end open → search → run

## Phase 7 — Connect the backend brain ✅ done 2026-10-18
- [x] Footage reaches the backend as project assets (phase 5), which queues the AI's understanding (shots, transcript, music, moments)
- [x] The app follows it (`GET /editor/projects/{id}/analysis` every 2.5 s while anything is being understood, then stops) and shows each stage under the file
- [x] What the AI found: summary, words / fillers / shots, its top moments (click to play), problems; "Try again" on failures (`…/analysis/{asset}/retry`)
- [x] Preview mode never polls (no backend to understand footage)
- [x] Tests: polling and stop rules, end-to-end understanding with a fake backend that advances like the real one

## Phase 8 — AI panel ✅ done 2026-10-18
- [x] Chat to the backend's studio agent (`POST /editor/projects/{id}/agent`, SSE): prompt, selection, playhead, history, Auto mode, model (`gpt-6-astra-1` by default when offered)
- [x] Live reply: tool lines, text, to-dos, questions with one-click answers, edit chips with Undo (`…/steps/{id}/undo`)
- [x] Whole edits arrive as plan cards: Approve / Reject, then followed step by step (`/editor/plans/{id}/stream`)
- [x] The AI moves the studio (`ui` events → playhead, play range, select, panels), logged as "AI" in Activity; what it changes glows on the timeline
- [x] Esc stops the AI (commands now have `when` rules); ⌘K offers "Ask the AI: …"
- [x] Tests: SSE parser, chat reducer, 4 end-to-end chat tests against a scripted agent (edit, studio moves, undo, plan approve → run)

Found and fixed: newer Chromium's scrollIntoView returns a promise, which React took for an effect cleanup and unmounted the app.

## Real end-to-end run ✅ 2026-10-18 — raw video → finished video with gpt-6-astra-1
`e2e-real/run.sh <video>` (own Postgres, local S3, the real backend and AI; your DB/bucket untouched).
2:30 conversation → "Edit the video." → plan (cut 30 s dead air, 5 fillers, 1 false start; punch-ins; captions) → approved → 17 cuts, 1:53 → exported 1080p30 MP4, −14 LUFS. 4.4 min end to end, 3 credits.
Found: captions laid over a source's burned-in subtitles; Groq key invalid (falls back to local Whisper); astra priced at $0 in usage; astra needs the Responses API for tools (backend learns it per process).

## Phase 9 — Select & ask ✅ done 2026-10-18
- [x] Drag across the ruler (or an empty part of a track) to select a range; a click still moves the playhead; Esc clears it (Esc stops the AI first when it's working)
- [x] An amber band with the range's times, and an "Ask about 0:42–1:10…" bar floating over it (▶ plays just that part)
- [x] The chat box shows the range as a chip; each turn shows the range it was about
- [x] Backend: `AgentRequest.range` (`FrameRange`, frames); the studio agent's digest names it, and the router and director get the prompt with "this is about 0:42–1:10 only"
- [x] Commands: `timeline.setRange`, `timeline.clearRange`
- [x] Tests: 5 backend tests (`tests/test_select_and_ask.py`), studio-agent DB tests still pass, 3 end-to-end tests (drag → ask → range in frames sent → Esc)
- Also: errors from the main process show only their reason (no "Error invoking remote method…")

## Phase 10 — Captions & text ✅ done 2026-10-18
- [x] Backend `GET /editor/projects/{id}/preview` (brain/preview.py): what the server render draws over the picture — caption words in timeline seconds, the caption look, titles in the renderer's three kinds, sound cues, the look — from the renderer's own `to_reel`, so preview and export can't disagree
- [x] Backend `GET /editor/caption-styles`: the 21 styles with their looks (the old `/subtitle-styles/presets` doesn't match its own schema)
- [x] Viewer overlay: captions in the style's font, size (×width/1080), colours and position, the spoken word lit; titles as hook / pop / lower third; the frame takes the project's shape
- [x] Text & Captions panel: captions on/off, 21 style tiles drawn in their own fonts, titles (add at playhead, edit words, top / middle / lower third)
- [x] Burned-in subtitles: the engine scans sampled frames with Apple Vision; the panel warns when captions would sit on them and offers to turn them off
- [x] Fonts bundled with their licences (assets/fonts)
- [x] Commands: `captions.toggle`, `captions.setStyle`, `text.add`, `text.edit`, `text.place`
- [x] Tests: 5 backend preview tests, caption line grouping, title ops, 3 end-to-end tests (captions on → shown lit, style change, title add/edit/move)

## Phase 11 — Sounds & music ✅ done 2026-10-18
- [x] Sounds panel: search the backend's library (`GET /editor/sounds`), ▶ preview, + adds at the playhead on an `sfx` track (stores the file's path like the AI's sounds); marks sounds the export can't play yet ("viewer only" — the render plays whoosh / pop / ding / hit kinds)
- [x] Music panel: any imported audio file as the music — from the start, cut to the edit's length, at −14 dB — with a level slider
- [x] The viewer mixes them in: the first audio clip plays as music, ducked under the main track's speech like the export; sound effects fire as the playhead passes them (not on seeks)
- [x] Commands: `sounds.add`, `music.add` (level via `timeline.setVolume`)
- [x] Tests: mix plan (music pick, sound order, export marks, ducking), sound/music ops, 3 end-to-end tests (library, a sound firing on playback, ducked music)

## Phase 12 — Effects ✅ done 2026-10-18 (zoom and framing, as the export draws them)
- [x] The viewer frames each clip exactly like the render's crop: fill the frame, zoom (a moving zoom held at its average, ≥1×), crop centre kept inside the picture, top at 45% of the spare height — so a vertical edit of landscape footage looks the same in the viewer and the export
- [x] Effects panel: zoom (None / Punch-in 1.14× / Tight 1.3× / fine slider) and framing (left ↔ right) for the selected clip or the one under the playhead; zoom badge on clips
- [x] Commands: `effects.zoom`, `effects.frame`
- [x] Not offered, and said so in the panel: fades, slides, shakes and flashes — the render doesn't draw them yet (backend renderer work)
- [x] Tests: framing maths (incl. landscape → vertical), effect ops, end-to-end zoom and framing measured on the real picture

## Phase 13 — Colour & look ✅ done 2026-10-18
- [x] Backend `GET /editor/looks`: the render's 7 looks
- [x] The viewer applies the look like the export: each FFmpeg filter (colorbalance, eq saturation / contrast / brightness) as the same arithmetic in one colour matrix; moody's vignette
- [x] Look swatches in the Effects panel; command `look.set`
- [x] Tests: look matrices (B&W, grey pivot, warm tint, vivid), route test, end-to-end look change

## Phase 14 — Export ✅ done 2026-10-18 (server render)
- [x] Export (⌘E, File → Export Video…, title-bar button): the backend renders the saved edit at full size (`POST /editor/projects/{id}/renders`, `brain/server_render.py`), the app follows it and saves the MP4 to ~/Movies/Clipnera, "Show in Finder"
- [x] Exports the AI starts (its `start_export` tool) are followed the same way
- [x] Editing copies are now 1080p, so the render is sharp
- [x] Tests: file names, end-to-end export against a fake renderer
- Later: render on the Mac with VideoToolbox from the original files

## Phase 15 — Edit Rules + Problems panel ✅ done 2026-10-18
- [x] Edit Rules view: plain rules per project (kept on this Mac), sent with every AI request — backend `AgentRequest.rules` reaches the studio agent and the planner
- [x] "Learned from your edits": the backend's style memory (`GET /editor/style`), each one forgettable (`DELETE /editor/style/{key}`)
- [x] Problems tab with a live count: no main track, missing footage, gaps (fix: close the gap), flash frames (fix: delete), moving zooms the export holds (fix: hold), fades / graphics / overlays / extra music / sounds the export leaves out, captions over burned-in words (fix: captions off), titles where captions sit (fix: move to the middle); each with Go to and Ask AI
- [x] Commands: `rules.add/remove/forget`, `timeline.closeGap`
- [x] Tests: 3 backend tests, rules store, every problem check, 3 end-to-end tests (rules sent, forget learned, gap → fix)

## v1.1 — Takes, agent team, Point & ask, Claude Code / Codex, voice ✅ done

- [x] Takes: save versions of the edit, compare them, go back to one, mix batches from one into another (`state/takes`, `timeline/takes`, `TakesPanel`) — `e2e/takes.spec.ts`
- [x] Agent team: a view of the agents working in parallel (`state/team`, `AgentsSheet`)
- [x] Point & ask: click a spot in the viewer to ask the AI about it or zoom in there (`PointAsk`, backend `point` field) — `e2e/point-ask.spec.ts`, `test_select_and_ask.py`
- [x] Claude Code / Codex over MCP: 127.0.0.1:47821 with a token, plus the stdio bridge `bin/clipnera-mcp.mjs` — `e2e/mcp.spec.ts`
- [x] Voice: hold to speak a prompt, transcribed through `/editor/voice` (Groq) — `e2e/voice.spec.ts`, `test_voice_note.py`

## Phase 16 — The export draws everything the timeline holds ✅ done

- [x] Speed changes and slow motion: picture (frames blended up to 30 fps) and voice (pitch kept) — `edit_engine/framing.py`, `render.tempo`
- [x] Zooms and pans animate between keyframes with their easing (`edit_engine/keyframes.py`); the editor preview follows them frame by frame (`player/framing.ts framingAt`)
- [x] Overlay tracks: B-roll and images, full frame or picture-in-picture, fades — `edit_engine/compose.py`
- [x] Graphic tracks: flashes and the shelf's animated graphics (`library.graphics()`)
- [x] Every library sound plays at its own level; the preview plays them at the export's level
- [x] The check render keeps the edit's own shape (`render_adapter.preview_size`)
- [x] Problems no longer warn about what the export now draws; Sounds lost its "viewer only" tag
- Tests: `tests/test_export_motion.py` (with a real FFmpeg render), `test_project_preview.py`, `framing/audio/problems` unit tests, `e2e/sounds|effects|rules-problems`
- Not yet: the editor preview doesn't draw overlay/graphic layers (phase 18); rotation and main-track fades aren't exported

## Phase 16b — Fast, real editing plans ✅ done

Measured on the owner's hands-on run (2026-10-18): "edit this video" took ~3.3 min — router 4 s, the full
edit rejected, the director 98 s (5 calls), then 90 s of review (two check renders and a 54 s critic) —
and the director's plan was 2 steps ("keep everything", "natural look").

- [x] The full edit no longer fails on cut filler words: tighten's pads stop at the next word, and edges that
      would cross stay where the cut put them (`speech_tighten.keep_ranges`, `compile._repair_word_edges`)
- [x] Footage brought in twice is edited once (`full_edit._distinct`)
- [x] Planning the owner's project: 0.06 s (was ~100 s through the director)
- [x] One check render shared by the verifier and the critic; director and critic at medium effort
- [x] The router reads the prompt while the chat model writes its first reply (which acts only after routing)
- [x] The plan card shows the edit part by part: timecodes, the first sentence, cuts, closer shots, slow
      motion, titles, sounds, graphics, B-roll, music (`brain/outline.py`, `PlanCard.outline`)
- Tests: `test_full_edit_fast.py`, `test_studio_agent_db.py` (TEST_DATABASE_URL), `test_llm_roles.py`, `e2e/agent.spec.ts`
- [x] Mastering ends with a true-peak limiter, so the peak check passes and the critic runs (it was skipped)
- [x] The chat AI searches every effect with `find_effects` (`brain/effects.py`): motion, speed, transitions,
      246 sounds, 16 graphics, 7 looks, 21 caption styles, titles, B-roll, each with the operation to apply it
- [x] Real astra run, raw 2:30 → final (`run.sh <video> full-edit`): plan in ~5 s (was ~100 s), approve → done
      in 37 s with the critic (was ~90 s), whole run 1.7 min; 1080p, -14 LUFS, -1.5 dBFS peak
- [x] `stack.sh`: other ports for a second stack (PG_PORT/S3_PORT/API_PORT), uvicorn really stops, busy ports refused
- Next: the backend doesn't know a video has burned-in subtitles (only the Mac app's text scan does), so the
  full edit captions over them; pass the scan's finding through and skip or lift captions there

## Phase 16c — It does what's asked, and you can see it ✅ done

From the owner's hands-on session (2026-10-18): effects were placed but the viewer never drew them, sounds
had no names on the timeline, titles were refused, and there was no step-by-step plan.

- [x] The viewer draws graphic and overlay layers like the export: flashes, the shelf's animated graphics
      (WebGL, packed alpha; played from a local cache the viewer can seek in), B-roll and picture-in-picture
      (`player/layers.ts`, `workbench/Layers.tsx`, `media/shelfCache.ts`, `GET /editor/graphics`)
- [x] Short timeline items keep their names (narrow style, tooltip); graphics show their name; sounds,
      music and graphics have their own colours
- [x] Sounds the AI adds carry their file, so the viewer plays them (`studio._playable`)
- [x] Titles: the AI may put on screen the user's own words or what is said (`invariants.given`)
- [x] The AI's frame checks show the flashes and graphics on screen (`frames.draw_layers`)
- [x] Two or more changes: a to-do list first, then one step at a time; a failed step doesn't stop the rest
- [x] Hooks copy the moment to the front and keep the cut (`open_with_moment`, `studio.hook_ops`)
- [x] A stalled AI request is retried after 30–60 s (was 120 s, silently); retries are logged
- [x] `e2e-real/prompts.spec.ts`: ten beginner → advanced requests on a raw video with real astra, recorded
- Not yet: background removal / green screen (needs a matting model: proposed as its own phase)

## Phase 17 — Clipnera's own assets

- [ ] Graphics made in code: lower thirds, arrows, highlight boxes, progress bar, subscribe card, emoji pops, counters
- [ ] Music made in code: beds by mood (lo-fi, upbeat, cinematic, tension, corporate), with loop points
- [ ] More fonts (licences beside them) for captions and titles
- [ ] Public-domain B-roll search through the backend's broll module

## Phase 18 — The editor shows and offers them

- [ ] Graphics panel; B-roll in Media; fonts in Text; music shelf in Music
- [ ] Keyframe and speed controls on the selected clip
- [ ] The preview draws overlays, graphics and animated framing

## Phase 19 — The AI knows the shelf and uses it

- [ ] One asset list the AI reads (id, what it's for, mood, length)
- [ ] Commands and agent tools to place each kind
- [ ] Prompt rules for slow motion, B-roll, graphics and music
- [ ] A real astra edit that uses them
