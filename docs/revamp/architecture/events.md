# Clipnera revamp, Wave 3: run and job events

Date: 3 October 2026. This file is the companion to [backend.md](backend.md) §4–§5 and [openapi.yaml](openapi.yaml).

It defines every event the server sends to clients about agent runs, jobs, versions and notifications:

- names and fields,
- ordering and idempotency,
- delivery over SSE and polling,
- versioning.

The event list maps one to one onto the moments in [01-experience-principles.md](../01-experience-principles.md) §5 and §13.

---

## 1. Envelope (every event)

Each event is one JSON object. On SSE it is sent as:

```
id: 1727950000123-0
event: run.operation.applied
data: {"type":"run.operation.applied","v":1,"stream":"run:01J9Z...","seq":17,...}

```

### 1.1 Envelope fields

```jsonc
{
  "type": "run.operation.applied",   // event name, see §3–§6
  "v": 1,                            // schema version of THIS type (§8)
  "stream": "run:01J9ZK6V...",       // "run:<id>" | "job:<id>" | "project:<id>" | "user:<id>"
  "seq": 17,                         // durable: gapless per stream, starts at 1
                                     // ephemeral: seq of the last durable event on the stream
  "sub": 3,                          // ephemeral only: counter since that durable seq (else omitted)
  "durable": true,                   // false for ephemeral types (§2)
  "ts": "2026-10-03T14:05:07.123Z",  // server time the event was produced (UTC, ms)
  "workspace_id": "…",
  "project_id": "…",                 // editor project, when the stream belongs to one
  "run_id": "…",                     // present on run.* and on job.* spawned by a run
  "job_id": "…",                     // present on job.*
  "data": { }                        // type-specific payload (§3–§6)
}
```

### 1.2 JSON Schema for the envelope

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://clipnera.com/schemas/events/envelope.json",
  "type": "object",
  "required": ["type", "v", "stream", "seq", "durable", "ts", "workspace_id", "data"],
  "properties": {
    "type": { "type": "string", "pattern": "^[a-z]+(\\.[a-z_]+)+$" },
    "v": { "type": "integer", "minimum": 1 },
    "stream": { "type": "string", "pattern": "^(run|job|project|user):[0-9A-Za-z-]{1,64}$" },
    "seq": { "type": "integer", "minimum": 0 },
    "sub": { "type": "integer", "minimum": 1 },
    "durable": { "type": "boolean" },
    "ts": { "type": "string", "format": "date-time" },
    "workspace_id": { "type": "string" },
    "project_id": { "type": "string" },
    "run_id": { "type": "string" },
    "job_id": { "type": "string" },
    "data": { "type": "object" }
  },
  "additionalProperties": true
}
```

`additionalProperties: true` is deliberate. Clients must ignore unknown fields (§8).

### 1.3 SSE line rules

- **`id:`** is the Redis stream entry id of the user's event stream (`<ms>-<n>`). It is used **only** for `Last-Event-ID` resume and is opaque to the client.
- **`event:`** equals `type`, so the client can use `addEventListener(type, …)`, or a single `onmessage` with a switch on `data.type`.
- **Heartbeat:** the server sends `: hb` every 15 s. It is a comment, so it has no id and does not move the resume cursor.
- **First lines:** the server sends `retry: 3000` once at open. The client adds jitter and exponential backoff to a 30 s cap.
- **CRLF:** the server always sends LF line endings. Clients must accept `\r\n` too, because a proxy may rewrite them. The current parser at `frontend/lib/api.ts:789-836` does not, and must be fixed.

---

## 2. Durable and ephemeral events

| | Durable | Ephemeral |
|---|---|---|
| Stored | Postgres (`agent_run_events` / `job_events`) **and** Redis user stream | Redis user stream and pub/sub only |
| `seq` | Gapless per stream, allocated in the same transaction as the state change | Copies the latest durable `seq`; `sub` orders within it |
| On reconnect | Replayed from Redis (`Last-Event-ID`) or Postgres (`after_seq`) | Replayed only if still in the Redis buffer; otherwise lost, and the next durable event or snapshot carries the state |
| Examples | state changes, plan, question, steps, operations, result | streamed plan text, step percentages, job percentages |

**Rule:** a client must be able to rebuild the correct UI from durable events plus snapshots alone. Ephemeral events only make that UI feel live.

---

## 3. Run events (`stream = run:<run_id>`)

**Ordering.**

- `run.acknowledged` is always `seq = 1`. A queued run gets `run.queued` at `seq = 1` and `run.acknowledged` later.
- Exactly one terminal event ends the stream: `run.result`, `run.failed` or `run.cancelled`.

### 3.1 Summary table

| Type | Durable | When | 01 §5 moment |
|---|---|---|---|
| `run.queued` | yes | Created while another run on the project is active | queue |
| `run.queue.updated` | yes | Its position changed (reorder, earlier run removed or finished) | queue |
| `run.acknowledged` | yes | Run row committed and active (written by the API) | 2 |
| `run.plan.delta` | **no** | Streamed plan text, coalesced about every 80 ms | 3 |
| `run.plan` | yes | Final plan: sentences, step outline, credit estimate | 3 |
| `run.message.delta` | **no** | Streamed answer text (Ask mode), or the result summary while it is written | 9 |
| `run.question` | yes | Assistant needs a choice | 4 |
| `run.answered` | yes | Answer recorded (written by the API) | 4 |
| `run.step.started` | yes | A step begins | 5 |
| `run.step.progress` | **no** | Count or percentage inside a long step (at least every 5 s) | 5 |
| `run.step.completed` | yes | Step finished, with what it changed | 5 |
| `run.step.failed` | yes | Step failed; run may continue, retry once, or fail | 8 |
| `run.lock.acquired` | yes | Items locked for the current step | 5 |
| `run.lock.released` | yes | Items unlocked | 5 |
| `run.operation.applied` | yes | A revision was committed by the run | 6 |
| `run.check.started` | yes | Result check begins | 8 |
| `run.check.completed` | yes | Check findings | 8 |
| `run.paused` | yes | Waiting for credits or approval | 8, 9 |
| `run.resumed` | yes | Continued after pause, or after a worker restart | 8, 9 |
| `run.stop_requested` | yes | User pressed Stop (written by the API) | 5 |
| `run.result` | yes | Terminal: `succeeded` or `partial`, with version and summary | 9 |
| `run.failed` | yes | Terminal: failed | 8 |
| `run.cancelled` | yes | Terminal: stopped before any change, or removed while queued | 5 |

### 3.2 Payloads (`data`)

All times are ISO 8601 UTC. All Timeline positions are **frames** (Timeline v1, `editor/timeline.py`). `label` strings are user-facing, plain words (01 §11).

```ts
// shared
type StepId = string;                         // "s1", "s2", ... stable within a run
type Credits = { estimate: number; held: number; spent: number };

type ErrorObject = {                          // same as the API error object (openapi Error)
  code: string; message: string; details?: Record<string, unknown> | unknown[];
  request_id?: string; retryable: boolean;
};

// run.queued
{ queue_position: number; prompt_preview: string }          // first 120 chars

// run.queue.updated
{ queue_position: number }

// run.acknowledged
{ status: "acknowledged"; mode: "edit" | "ask" | "plan";
  chips: ContextChip[];                                    // echo, so the "Reading your request" line can show them
  base_revision: number; credits: Credits }

// run.plan.delta (ephemeral)
{ text: string }                                           // append-only fragment

// run.plan
{ sentences: string[];                                     // the plain-language plan as shown
  steps: { id: StepId; label: string }[];                  // outline; labels are "verb + object"
  targets?: { clip_ids?: string[]; ranges?: [number, number][] };
  credits: Credits;
  needs_approval: boolean }                                // true → a run.paused{reason:"approval"} follows

// run.message.delta (ephemeral)
{ text: string; role: "answer" | "summary" }

// run.question
{ question_id: string; text: string;
  choices: { id: string; label: string; hint?: string }[]; // up to 4
  allow_skip: true;                                        // "Skip, use your best guess"
  expires_at?: string }                                    // after this the run picks its best guess

// run.answered
{ question_id: string; choice_id?: string; text?: string; skipped: boolean; by: "user" | "timeout" }

// run.step.started
{ step_id: StepId; index: number; total: number; label: string }   // "Trimming 14 silences"

// run.step.progress (ephemeral)
{ step_id: StepId; done?: number; total?: number; percent?: number; label?: string }

// run.step.completed
{ step_id: StepId; label: string; summary: string;          // "Removed 42 seconds"
  revisions: number[] }                                     // revisions this step produced

// run.step.failed
{ step_id: StepId; error: ErrorObject; will_retry: boolean; attempt: number }

// run.lock.acquired / run.lock.released
{ step_id: StepId; item_ids: string[] }

// run.operation.applied
{ revision: number;                                         // editor_ops version produced
  base_revision: number;                                    // revision the ops were applied on
  ops: TimelineOp[];                                        // exact ops, as in frontend/lib/editor/timeline.ts
  changed_ranges: [number, number][];                       // frames, for the 600 ms highlight / "Jump to change"
  item_ids: string[];                                       // items touched
  step_id: StepId;
  client_batch_id: string }                                 // "{run_id}:{step}:{call}" -- idempotency

// run.check.started
{ }

// run.check.completed
{ passed: boolean; findings: { severity: "info" | "warn"; text: string }[] }

// run.paused
{ reason: "credits" | "approval";
  credits: Credits; needed?: number;                        // credits needed to continue
  approval?: { kind: "credits" | "removal"; text: string; share_removed?: number };
  options: ("continue" | "finish" | "add_credits")[] }

// run.resumed
{ reason: "user_continue" | "credits_added" | "worker_restart"; attempt?: number }

// run.stop_requested
{ by: string }                                              // user id

// run.result (terminal)
{ status: "succeeded" | "partial";
  version: { id: string; name: string; result_revision: number } | null;   // null for Ask/Plan modes
  summary: { done: string[]; not_done: { text: string; reason: string }[] };
  answer?: string;                                          // Ask mode
  plan_document?: { sentences: string[]; steps: { id: StepId; label: string }[] };  // Plan mode
  suggestions: { label: string; prompt: string }[];         // up to 3 next-step chips
  credits: Credits; duration_ms: number }

// run.failed (terminal)
{ error: ErrorObject;
  version: { id: string; name: string } | null;             // ops applied before the failure are kept as a version
  suggestion?: { label: string; prompt: string };           // "different prompt" after the 2nd failure
  credits: Credits }

// run.cancelled (terminal)
{ by: "user" | "system"; while: "queued" | "running" }
```

`ContextChip` is defined in [openapi.yaml](openapi.yaml) (`components/schemas/ContextChip`):

- `{type: "clip" | "range" | "caption_line" | "asset" | "moment", ref, label}`

### 3.3 Run event invariants

1. Every `run.step.started` is followed by exactly one `run.step.completed` or `run.step.failed` with the same `step_id`. The only exception is a terminal event that arrives first, after a stop or failure.
2. `run.operation.applied.revision` values within a run increase strictly. A client that has already applied revision R ignores any event with `revision <= R`. Redelivered runs replay with the same `client_batch_id` and the same revision.
3. At most one open `run.question` at a time. The run is in `awaiting_input` until `run.answered`.
4. A terminal event is the last durable event of the stream, and carries the final `credits`.
5. If any `run.operation.applied` was emitted, the terminal event carries a non-null `version`. This is the "one prompt, one version" rule (01 §3.3).

---

## 4. Job events (`stream = job:<job_id>`)

Jobs cover uploads and media processing, the clip pipeline, exports and renders, B-roll indexing, and the optional full-quality render after a run.

| Type | Durable | `data` |
|---|---|---|
| `job.queued` | yes | `{kind, job_class, subject: {type, id}, label}` (label example: "Preparing video") |
| `job.started` | yes | `{attempt}` |
| `job.step` | yes | `{step: string, label: string, status: "running" \| "completed" \| "failed" \| "skipped", index?: number, total?: number}`. For pipelines this mirrors `pipeline_step_logs` |
| `job.progress` | **no** | `{percent?: number, done?: number, total?: number, message?: string, eta_s?: number}` |
| `job.retrying` | yes | `{attempt, next_attempt_at, error: ErrorObject}` |
| `job.succeeded` | yes | `{result: object}`. Per kind: `media.proxy` → `{media_asset_id, proxy_url_path}`; `export.clips` → `{exports: [{clip_id, download_path}]}`; `pipeline.run` → `{clip_count}` |
| `job.failed` | yes | `{error: ErrorObject, dead_letter: boolean, refunded_credits?: number}` |
| `job.cancelled` | yes | `{by}` |

**Invariants.**

- Exactly one terminal event: `job.succeeded`, `job.failed` or `job.cancelled`.
- `job.started` may repeat with a higher `attempt` after a crash. Clients show the latest one.
- `job.step` with the same `step` may repeat after a resume. Clients key by `step`.

**Media-specific shortcut.** When a `media_assets` row changes status, the server also emits `media.updated` on `stream = project:<project_id>` (or `user:<user_id>` for library assets) with:

- `{media_asset_id, status, proxy_ready, hls_ready, poster_ready, rejection?}`

That way the editor can switch an asset from "processing" to playable without tracking job ids.

---

## 5. Project and version events (`stream = project:<editor_project_id>`)

These events keep a second tab or a collaborator in sync, and record version actions not caused by runs.

| Type | Durable | `data` |
|---|---|---|
| `project.revised` | yes | `{revision, author: "user" \| "agent:editor", run_id?, item_ids, client_batch_id?}`. Emitted for hand edits; run edits already arrive as `run.operation.applied`. Other tabs fetch ops with `GET /editor/projects/{id}?since_revision=` or reload |
| `version.created` | yes | `{version: VersionSummary}` (openapi `VersionSummary`) |
| `version.updated` | yes | `{version_id, name?, bookmarked?}` |
| `version.restored` | yes | `{restored_version_id, new_version: VersionSummary, revision}` |
| `media.updated` | yes | see §4 |

The `seq` on `project:` streams is gapless per project and is allocated from `editor_projects.last_event_seq`, a new column. Both `project.revised` and `version.*` events are written in the same transaction as the revision or version they describe.

---

## 6. User-level events (`stream = user:<user_id>`)

| Type | Durable | `data` |
|---|---|---|
| `notification.created` | yes (the notification row) | `InAppNotification` (same shape as `GET /notifications` items, see openapi) |
| `activity.updated` | **no** | `{active_jobs: number, active_runs: number}`, sent whenever either count changes. Drives the header activity indicator |
| `credits.updated` | yes | `{balance, purchased_balance, held}`, sent after any charge, hold, release or top-up. Fixes "balance not refetched after a charge" (audit 00 §7 #12) |
| `entitlements.changed` | yes | `{plan}`. The client refetches `GET /subscription/entitlements` |
| `config.changed` | **no** | `{snapshot_version}`. The client refetches flags and config (see [06-flags.md](../06-flags.md)), which gives kill switches that reach an open tab |
| `auth.expired` | **no** | `{reason: "revoked" \| "session_expired"}`. The server closes the stream after sending it |
| `sync.reset` | **no** | `{reason: "buffer_miss" \| "server_restart", streams?: string[]}`. The client refetches snapshots (§7.3) |

User-level `seq` is the per-user Redis stream position. These events do not carry a gapless `seq`. The snapshot endpoints (`GET /notifications`, `GET /jobs?status=active`, `GET /subscription/entitlements`) are the truth.

---

## 7. Delivery, ordering and idempotency

### 7.1 Producing an event (server)

```
BEGIN
  UPDATE agent_runs SET status = …, last_event_seq = last_event_seq + 1 WHERE id = :run RETURNING last_event_seq  -- seq
  INSERT INTO agent_run_events (run_id, seq, type, v, data) VALUES (…)
       ON CONFLICT (run_id, seq) DO NOTHING
  …the state change itself (revision, version, status)…
COMMIT
→ after commit: XADD ev:u:{user} MAXLEN ~ 2000 * json ; PUBLISH ch:u:{user} <entry id>
```

- The `seq` allocation and the state change are atomic, so a durable event exists if and only if its state change committed.
- If publishing fails, nothing is lost. The client detects a gap and backfills (§7.3).
- Ephemeral events skip the database and are published directly. They copy the current `last_event_seq` into `seq` and use an in-memory `sub` counter.

### 7.2 Idempotency keys

| Consumer concern | Key |
|---|---|
| Duplicate delivery (reconnect overlap, two sources) | `(stream, seq)` for durable events; `(stream, seq, sub)` for ephemeral events |
| Applying Timeline operations twice | `run.operation.applied.revision`, or `client_batch_id` |
| Re-run of a step after a worker restart | `step_id`. A second `run.step.started` for a known `step_id` updates the existing row rather than adding one |
| Notifications | `notification.id` (same de-duplication as `useNotificationInbox` today) |

### 7.3 Resume and gap handling (client algorithm)

1. **Opening a project.** Fetch snapshots: `GET /editor/projects/{id}` (Timeline plus revision), `GET /editor/projects/{id}/runs?limit=…` (each run with its `last_event_seq`), and `GET /jobs?status=active`. Remember `lastSeq[stream]`.
2. **Open the stream.** `EventSource('/api/v1/events/stream?project_id=…', {withCredentials: true})`. The browser sends `Last-Event-ID` automatically on reconnect.
3. **For each durable event:**
   - if `seq <= lastSeq[stream]`, drop it as a duplicate;
   - if `seq == lastSeq + 1`, apply it;
   - if `seq > lastSeq + 1`, buffer it and call `GET /runs/{id}/events?after_seq=lastSeq` (or `/jobs/{id}/events`), apply in order, then drain the buffer.
4. **Ephemeral events** are applied only if their `seq` equals `lastSeq[stream]` (they belong to the current durable state). Otherwise they are dropped.
5. **On `sync.reset`,** repeat step 1 for the open project and refetch user-level snapshots.
6. **Fallback transport.** After 3 failed stream attempts within 60 s, or if the stream delivers nothing (not even a heartbeat) for 45 s, switch to `GET /events/poll?cursor=…` (long poll, 25 s). Keep retrying SSE every 2 minutes.

### 7.4 Ordering guarantees

- **Total order within a stream** (`run:`, `job:`, `project:`) by `seq`.
- **No ordering guarantee across streams**, except that a run's `run.operation.applied` for revision R is produced in the same transaction as revision R. Any later `project.revised` with a higher revision is therefore committed after it.
- The per-user Redis stream preserves publish order, which matches commit order for events from one producer. The client must not depend on cross-stream order for correctness.

### 7.5 Retention

| Store | Retention |
|---|---|
| Redis user stream | about 2,000 entries or 30 minutes, whichever is smaller |
| Postgres `agent_run_events`, `job_events` | 90 days (monthly partitions dropped). Run and job rows keep `summary`, `result` and `error` indefinitely |
| Run LLM transcripts (S3) | 90 days |

---

## 8. Versioning

1. **Additive changes do not bump `v`.** New optional fields, new enum values in fields documented as open (`reason`, `kind`, `status` values in `findings`), and new event types all fall into this category.
2. **Clients must:**
   - ignore unknown event types;
   - ignore unknown fields;
   - treat unknown enum values as a generic case (for example, an unknown `run.paused.reason` shows the generic paused card).
3. **A breaking change** (removing or renaming a field, or changing a type or meaning) increments `v` for that type. The server then emits **both** versions for one release window. The client opts in with `?accept=run.plan@2` on the stream URL, and the server sends only the newest version the client accepts. After the window, the old version is removed.
4. **Event names never change meaning.** A wholly new semantic gets a new name.
5. **Schemas live in code.** Pydantic models in `backend/realtime/events.py` (new) generate `docs/revamp/architecture/events.schema.json`, and the TypeScript types in `frontend/lib/realtime/events.ts` are generated from that JSON Schema. A CI test fails if the generated files are stale. This satisfies the AGENTS.md rule that frontend and backend types match.

---

## 9. Example: one prompt, end to end

Prompt: "Trim the silences and add captions", sent on an editor project at revision 40.

| # | Event | Notes |
|---|---|---|
| 1 | `run.acknowledged` seq 1 | `base_revision: 40`, chips echoed |
| 2 | `run.plan.delta` ×n (seq 1, sub 1…n) | "I'll remove the pauses longer than…" |
| 3 | `run.plan` seq 2 | steps s1 "Finding silences", s2 "Trimming silences", s3 "Adding captions"; `credits.estimate: 4` |
| 4 | `run.step.started` seq 3 | s1 |
| 5 | `run.step.completed` seq 4 | s1 "Found 14 silences" |
| 6 | `run.step.started` seq 5 | s2 |
| 7 | `run.lock.acquired` seq 6 | `item_ids: [c3, c4]` |
| 8 | `run.step.progress` (seq 6, sub 1) | `done: 6, total: 14` |
| 9 | `run.operation.applied` seq 7 | revision 41, 14 `trim_item`/`split_item`/`remove_item` ops |
| 10 | `run.lock.released` seq 8 | |
| 11 | `run.step.completed` seq 9 | s2 "Removed 42 seconds", `revisions: [41]` |
| 12 | `run.step.started` seq 10 | s3 |
| 13 | `run.operation.applied` seq 11 | revision 42, `set_captions` |
| 14 | `run.step.completed` seq 12 | |
| 15 | `run.check.started` seq 13 | |
| 16 | `run.check.completed` seq 14 | `passed: true` |
| 17 | `run.result` seq 15 | `status: succeeded`, `version: {name: "Trimmed silences, added captions", result_revision: 42}`, suggestions |
| 18 | `version.created` on `project:` | for other tabs |
| 19 | `credits.updated` on `user:` | balance after settlement |

If the user presses **Stop** after #9, the API emits `run.stop_requested`. The worker stops at its next safe point (before #10's next tool call), emits `run.lock.released` and `run.step.completed` (s2, partial), and then `run.result` with `status: partial`. Its `summary.not_done` reads "Add captions — stopped before this step", and its version covers revision 41 only.
