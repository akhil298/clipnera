# Wave 6: editor stores API (unit E1)

Written by the E1 builder, 8 October 2026. This is the contract that E2, E3, E4a/b, EH, P2/P3, T1/T2, X1, V1, C1, H1, B1 and CS1 build against. The files belong to E1. Send change requests to E1 and don't edit them yourself.

All three stores are Zustand vanilla stores. Each one is created by a factory, so one editor instance owns its own set (`EditorClient`, E2, creates them and passes them down or puts them in context). In React, read a store with `useDoc` / `useRun` / `useSelection(store, selector)`. **Selectors must return stable references.** The exported ones already do, so components re-render only when their own slice changes. Playback time is never in these stores. It lives in `lib/editor/playback/clock.ts` (P1).

## Doc store: `lib/editor/store.ts`

```ts
const doc = createDocStore({ transport: editorTransport, storage: idbPendingStorage, isLocked: runs.isLocked });
await doc.hydrate(projectId, { timeline, version });   // restores unsent batches from IndexedDB, rebases, sends
```

| Member | What it does |
|---|---|
| `hydrate(projectId, {timeline, version})` | Loads the project. Restores this project's unsent batches, rebases them on the server document and sends them. |
| `apply(ops, label?) → ApplyResult` | Applies one gesture as one batch. It is applied locally at once and then sent. It is refused, without throwing, with `{ok:false, code}` for these codes: `NOT_READY`, `READ_ONLY` (viewing a version), `LOCKED` (`itemIds` are held by a run step), or any `TimelineError` code (`OVERLAP`, `OUT_OF_RANGE`…). Pass `label` ("Title 2") so the rebase toast can name the edit. |
| `applyRemote({base_revision, revision, ops, item_ids?, changed_ranges?})` | Handles `run.operation.applied`. A duplicate revision is ignored. A gap triggers `resync()`. Sets `landed` for the 600 ms amber outline. |
| `flush()` / `retry()` | Sends pending batches one at a time, each with `base_version` set to the last acked version. Use `retry()` for "Not saved" → Retry and on the browser `online` event. |
| `resync()` | Refetches the server document (a full GET until EB-2) and rebases the pending batches on it. Call it on `sync.reset`. |
| `replaceServer({timeline, version})` | Sets the new head after a restore or undo (V1, T2). |
| `viewVersion(id, label, timeline)` / `backToLatest()` | Read-only preview document. `apply` refuses edits while it is shown. |
| `dismissDropped(batchId)` | Call this after showing the "Your edit to X was replaced by Clipnera's change." toast. |

State (`DocState`): `server {timeline, version}`, `pending: PendingBatch[]`, `view` (server + pending), `save: 'saved'|'saving'|'error'|'offline'`, `error`, `dropped: DroppedBatch[]`, `preview`, `landed {itemIds, ranges, revision, key}`.

How the queue handles failures: `409 STALE_VERSION` refetches the project, rebases and keeps sending. A network error sets `offline`, and the batch is kept on this device. A 5xx or 429 sets `error`, and the batch is kept. Any other refusal drops the batch and adds it to `dropped`.

Selectors: `selectShown` (the preview document, or else the live view), `selectReadOnly`, `selectTracks`, `selectTrack(id)`, `selectItem(id)` (an item's identity is kept unless that item changed, via `shareUnchanged`), `selectDurationFrames`, `selectFps`, `selectCaptions`, `selectVersion`, `selectSaveState`, `selectHasPending`, `selectLanded`, `selectDropped`.

Pure helpers in `lib/editor/rebase.ts`: `rebase(server, pending)`, `fitRemote(version, base, revision)`, `opItemIds(op)`, `batchItemIds(ops)`, `shareUnchanged(prev, next)`.

## Run store: `lib/editor/run-store.ts`

```ts
const runs = createRunStore();
runs.dispatch({ kind: 'event', event });              // from lib/realtime/handlers/runs.ts (E4a) or the simulator
```

The core is `reduceRun(state, action)`, which is pure. Actions:

| Action | When |
|---|---|
| `send {turnId, prompt, chips: PromptContext[], mode, at?, retryOf?}` | Send is pressed. The turn shows `status:'sending'` at once. |
| `send.failed {turnId, error}` | `POST /runs` never arrived. The turn shows `send_failed` and keeps its text. |
| `bind {turnId, run: Run}` | `POST /runs` or `/retry` answered. Merges with a turn the stream may have started first. |
| `hydrate {runs: Run[]}` | Older turns from EB-3 `listRuns` / EB-6 activity. Turns are ordered by start time. |
| `event {event: RunEvent}` | Every `run.*` event. It de-duplicates by `seq`, buffers events after a gap (then fetch `GET /runs/{id}/events?after_seq=backfill[runId]` and dispatch the result), and applies ephemeral events only at the current seq. |
| `answer {runId, choiceId\|'skip'}` · `decide {runId, decision}` · `stop {runId}` | Optimistic: shows the pick, the decision or "Stopping" before the server confirms. |
| `undone {turnId, undone}` · `markers.clear {itemIds?}` · `remove {turnId}` · `reset` | Undo or redo of a turn. A hand edit clears markers. Removes a queued prompt. |

`Turn`: `id, runId, prompt, chips, mode, status` (`RunStatus | 'sending' | 'send_failed'`), `queuePosition`, `startedAt/endedAt`, `planText` (streamed), `plan {sentences, steps, targets, needsApproval}`, `credits`, `steps: TurnStep[]` (same shape as `StepList`'s `RunStep`), `checking`, `checkFindings`, `sources` (EB-8 source strip), `question` (+ `chosenId/skipped/by`), `pause` (+ `decided`), `stopping`, `answerText`, `summaryText`, `citations` (EB-7, merged by id), `result`, `failure`, `cancelled {by, while, changed}`, `sendError`, `revisions`, `touched`, `undone`, `retryOf`.

State: `turns`, `lastSeq`, `buffered`, `backfill`, `locks` (item → run), `markers` (item → `{turnId, runId, revision}`). Markers clear when the next run is acknowledged.

Selectors: `selectTurns`, `selectTurn(id)`, `selectActiveTurn`, `selectIsRunning`, `selectQueue` (memoised, in queue order), `selectIsLocked(itemId)`, `selectLockedIds` (memoised), `selectMarker(itemId)`, `selectMarkers`, `selectBackfill`. `runs.isLocked(itemId)` is non-React and is wired into the doc store. `turnFromRun(run)` rebuilds a turn from a snapshot.

E4a wiring: for each `run.operation.applied` event, dispatch it **and** call `doc.applyRemote(event.data)`. On a hand edit, dispatch `markers.clear` with the touched item ids (`batchItemIds(ops)`).

## Selection store: `lib/editor/selection.ts`

`createSelectionStore()` returns `{store, select(sel, {additive?}), remove(key), clear(), prune(itemExists)}`. The `Selection` kinds are `item {itemId, label, meta?, thumbnailUrl?}`, `range {start, end}` (frames), `caption {start, end, text}`, `asset {assetId, library:'media'|'broll', label}`, `moment {frame}` and `region {frame, bbox}` (EB-9).

- `chipsFor(selected, fps, runs.isLocked) → Chip[]`: `PromptContext` plus `locked`, for the composer. Wrap it in `useMemo`.
- `toWireChip(sel, fps)`: the openapi `ContextChip` for `POST /runs`.
- `toContext(sel, fps)`: builds the UI chip.
- `contextFromWire(chip)`: reads a chip the server echoed back.
- `selectionKey(sel)`: the de-duplication key.
- Selectors: `selectSelected`, `selectIsSelected(key)`.

## Clip mode: `lib/editor/clip-doc.ts`

- `clipDocFromSettings({settings, segments, normaliseCaption: normalizeCaptionConfig}) → {doc: ClipDoc, saved}`
- `settingsFromClipDoc(doc) → ClipEditorSettings` (the body for `PUT /clips/item/{id}/editor-settings`). Every saved field round-trips, including highlights saved for words this transcript doesn't have (kept in `orphanHighlights`).
- `withBrandKitCaption(doc, presetConfig, kit)`: use it when `saved` is false.
- `setWordsCut(doc, sourceStarts, cut)` and `setWordsHighlighted(doc, wordIds, on)`.

`ClipDoc` has the legacy `StudioDoc` fields. B-roll overlays, sound effects, auto-zoom and audio enhancement are kept for preview only and are not saved (EB-23).

## API wrappers: `lib/api/editor/`

- **`projects.ts`** (real): `listEditorProjects`, `createEditorProject`, `openReelInEditor`, `getEditorProject`, `applyEditorOps`. Each returns a normalised Timeline.
- **`projects.ts`** (stubs): `getEditorOpsSince` (EB-2), `renameEditorProject` (EB-17), `getEditorTranscript` (EB-18).
- **`runs.ts`** (stubs): `createRun`, `listRuns`, `getRun`, `listRunEvents`, `stopRun`, `answerRun`, `continueRun`, `retryRun`, `updateQueuedRun`, `removeQueuedRun` (all EB-3), `estimateRun` (EB-4), `getProjectActivity` (EB-6).
- **`versions.ts`** (stubs): `listVersions`, `getVersion`, `updateVersion`, `restoreVersion`, `checkpointVersion`, `undoVersion` (all EB-10), `compareVersions` (EB-11).
- **`transport.ts`**: `editorTransport` for the doc store.
- **`types.ts`**: the wire types, including the `RunEvent` union with envelope fields. Citations are EB-7, findings EB-8, outputs EB-21 and region chips EB-9.

Other files:

- **Query keys:** `editorKeys` in `lib/query/keys/editor.ts`.
- **Copy:** `editorMessage(code, serverMessage?) → {text, action}`, `droppedEditMessage(label)` and `SAVE_STATE_TEXT`, all in `lib/api/messages/editor.ts`.

## Dev simulator: `lib/editor/dev/`

```ts
const sim = createRunSimulator({ runs, onSideEvent, onOperation: (e) => doc.applyRemote(e.data) });
sim.start('happy' | 'question' | 'approval' | 'credits' | 'step-failed' | 'second-failure' | 'partial'
          | 'not-enough' | 'not-understood' | 'unreadable' | 'connection' | 'ask' | 'plan');
sim.answer(id | 'skip'); sim.decide('continue' | 'finish' | 'add_credits'); sim.stop(); sim.enqueue(prompt); sim.setSpeed(0.5 | 1 | 2); sim.reset();
```

The simulator emits real envelopes (`run_id`, `seq`, `durable`) into the run store. Side events (`version.created`, `credits.updated`, `sync.reset`, `job.succeeded`, `client.connection`) go to `onSideEvent`. The scripted ops are empty, so only connect `onOperation` to a throwaway doc. `SCENARIOS` are in `scenarios.ts`.

Tests: `resolve-hooks.mts` lets `node --test` load modules that import `@/…` and extensionless paths. `fixture.mts` is the shared backend Timeline fixture.

## Editor frame API (unit E2)

Added by the E2 builder, 8 October 2026. Files: `components/editor/EditorClient.tsx` and `components/editor/workspace/**`. Zone units replace only their slot file in `workspace/zones/`. They never edit the frame.

`EditorClient` loads `GET /editor/projects/{id}` once, with `staleTime: Infinity`. `EditorRoot` then creates the doc, run and selection stores and the `PreviewEngine`, plus the run simulator when the URL has `?sim=1` outside production. It provides all of them through `useEditor()` from `workspace/context.tsx`:

| Field | What it is |
|---|---|
| `project` | `EditorProjectSummary` as loaded. The live version comes from `doc` (`selectVersion`). |
| `doc`, `runs`, `selection` | The E1 stores. The frame hydrates `doc`, toasts dropped edits and calls `retry()` on `online`. |
| `engine` | The P1 engine. The frame creates and destroys it and calls `setTimeline(selectShown)` on every change. Zones call `engine.mount(el)`. Media URLs are a `NEEDS-BACKEND` resolver (`workspace/mediaUrls.ts`). |
| `sim` | `RunSimulator \| null`. In dev, the composer calls `sim.start(id)` on send. |
| `features` | `{conversation, timeline}`. `conversation` = `prompt_streaming_v2` or `?sim=1`. `timeline` = `new_ui_editor_timeline`. |
| `connection` | `'online' \| 'offline' \| 'reconnecting'`. Drives the strips under the top bar. |
| `layout` | `arrangement` (`wide`/`xl`/`lg`/`md`/`phone`), `tool`, `panelOpen`, `toggleTool`, `openTool`, `setPanelOpen`, `togglePanel`, `conversationOpen`, `setConversationOpen`, `toggleConversation`, `phoneTab`, `setPhoneTab`. |
| `promptRef`, `focusPrompt()` | E3 attaches `promptRef` to the composer textarea. ⌘K and / call `focusPrompt`, which also switches to the Chat tab on phones. |
| `openExport()` | Flushes pending ops, then opens Area 8's dialog (`useExport`) on the acked server version. |
| `history`, `shortcuts` | `{open, setOpen}` for the History drawer (V1 fills `zones/HistoryZone.tsx`) and the shortcuts dialog. |

Zone slots and their props (the full contract is in each file's header):

- `LeftPanelZone {tool, placement: 'docked'|'overlay'|'tab', onClose}`: X1, C1, H1, B1
- `PreviewZone {placement: 'stage'|'phone'}`: P2, P3
- `TimelineZone {placement: 'full'|'compact'|'strip'}`: T1, T2
- `ConversationZone {placement: 'side'|'drawer'|'dock'|'phone'}`: E3, E4a, E4b
- `HistoryZone`, `VersionSwitcherZone` (no props): V1

The frame owns these keys: ⌘B, ⌘\, ⌥1–⌥7, ⌘E, ⌘K, /, ⌘⇧H, ? and Esc (clears the selection). Zones bind everything else listed in 02-editor §2.4.

`WorkspaceLayout` is the presentational four-zone layout. It takes render functions, so clip mode (`ClipModeFrame`, which CS1 fills) shares the same sizes and breakpoints. Sizes come from `layout` in `tokens.ts`. They are converted to percentages for `ResizablePanels`, and saved per width under `cn-panels:<editor|clip>:<arrangement>:<outer|timeline|panel>`.
