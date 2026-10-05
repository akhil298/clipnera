# Clipnera UI revamp — Wave 5: feature flags, kill switches and remote config

Date: 3 October 2026. Branch `clipnera` at `38f9bd5`. Builds on [00-audit.md §6.3](00-audit.md), [01-experience-principles.md §5, §8, §9, §13](01-experience-principles.md), [audit/07 §3, §7](audit/07-settings-billing-admin.md) and [audit/02 §7](audit/02-data-layer.md).

This is a design only. No repo file other than this one was changed. Implementation starts once the Lead signs off.

**Summary of the decisions**

1. **Self-hosted on the existing Postgres.** No paid flag service and no new Redis. Redis is configured (`core/config.py:31`) but nothing uses it and it is not in `requirements.txt`. The engine holds an in-process snapshot, so a flag check costs zero queries.
2. **Definitions stay in code and are the single source.** Python is the master copy. TypeScript is generated from it and a test fails if the generated file is out of date. This replaces the three hand-copied lists.
3. **Evaluation happens on the server only.** The frontend never hashes or evaluates rules. It reads evaluated values from one bootstrap payload, through server components where possible.
4. **Plan entitlements stay a separate system.** Flags decide whether something is *released* to a person. Entitlements decide whether their *plan pays for it*. Targeting a flag by plan is for rollout order only, never for a paywall.
5. **Backward compatible.** All 13 keys keep their names. `GET /features` and the two admin routes keep their shapes. The one intended behaviour change is the grandparent fix (§1.3), and a pre-deploy check guards it (§12, step 1.0).

---

## 1. Current state

### 1.1 Backend

| Piece | Where | What it does |
|---|---|---|
| Definitions | `backend/feature_flags/registry.py:14-19` | `FlagDefinition(key, label, description, parent)` — no owner, default, expiry, kind |
| Keys | `registry.py:22-30`, list `:37-104`, map `FLAGS` `:106` | 13 keys; an undeclared key raises (`service.py:41-42`) — keep this |
| Table | `feature_flags/model.py:11-23`; created in `alembic/versions/20260926000000_add_social_publishing.py:51-57` | `key` PK, `enabled`, `updated_by` (FK users, SET NULL), `updated_at`. No row means off |
| Evaluation | `feature_flags/service.py:18-26` `resolve()` | `stored[key] and stored[parent]` — **one level only** |
| Storage read | `service.py:33-35` | `SELECT key, enabled` on **every** check; no cache; no context argument anywhere |
| Enforcement | `service.py:45-55` `require()`; dependency `feature_flags/dependencies.py:19-25` | 403 `FEATURE_DISABLED`, `extra={"feature": key}` |
| Public read | `feature_flags/route.py:20-22` | `GET /features`, signed-in only, the user is ignored (`_: CurrentUserDep`) |
| Admin | `route.py:15-17, 25-35` | `GET /admin/features`, `PATCH /admin/features/{key}` `{enabled}`; router-level `get_current_admin` |
| Write | `service.py:57-68` | Upsert overwrites `updated_by`/`updated_at`; one log line. **No history** |
| Admin role | `auth/model.py:19-21`, `auth/dependencies.py:53-65` | Single `admin` role read from the DB on every request (good); no finer permissions |

**Where flags are checked (backend, 13 sites):**

| Key | Site | Kind of check |
|---|---|---|
| `video_upload` | `uploads/route.py:25` | router dependency |
| `broll_studio.reels` | `reels/route.py:26` | router dependency |
| `broll_studio.cutaways` | `broll/route.py:29`; `pipeline/service.py:815` | router dependency; background pipeline step (no user context) |
| `broll_studio.ai_shots` | `broll/generation.py:122` | `require` inside service |
| `broll_studio.reels.footage` | `edit_engine/route.py:30` | router dependency |
| `broll_studio.reels.footage.opus_director` | `edit_engine/service.py:90`; `edit_engine/jobs.py:242` | value switch (model choice + 1.5x price), background job |
| `agent_editor` | `editor/route.py:16` | router dependency |
| `social_publishing` (+ platform) | `social/service.py:170`; `social/posts.py:79`; `social/publisher.py:100-102`; `social/worker.py:99-104` | `require`; worker loops read `effective()` once per batch |
| (tests) | `tests/test_broll_flags.py:18-40, 98, 124-128`; `tests/test_generation.py:90`; `tests/test_social_db.py:209`; `tests/test_social_security.py:22` | hand-written `Flags` fake + `dependency_overrides` / `monkeypatch` |

`broll_studio` and `social_publishing.tiktok`/`.x` are checked only as parents or through `social_platform_flag()`.

### 1.2 Frontend

| Piece | Where | Behaviour |
|---|---|---|
| Key union | `frontend/lib/api.ts:1705-1718` | hand copy of the 13 keys |
| Types | `lib/api.ts:1720-1737` | `FeatureFlagsResponse`, `AdminFeatureFlagResponse`, `AdminFeatureFlagListResponse` — these match the backend schema `feature_flags/schema.py:9-31` |
| Client | `lib/api.ts:1767-1778` | `featuresApi.get`, `adminFeaturesApi.list/set` |
| Hook | `hooks/useFeatureFlags.ts:8-22` `ALL_OFF` (third copy of keys); `:25-38` module-level promise; `:42-56` hook | One request per page load. **All off until loaded and on failure.** `refresh()` updates only the calling instance (`:53`). No polling, no push, no refetch on focus. The cache survives sign-out in the same tab |
| Error handling | `lib/api.ts:496-503, 551-555` | Plan errors fire `clipnera:upgrade-required`; `FEATURE_DISABLED` has no handler and surfaces as a generic error |
| Admin UI | `components/admin/AdminFeaturesView.tsx:8-21`, `AdminSocialView.tsx:63`, `FeatureSwitches.tsx:7-57` | Flat switches split by key prefix (`AdminFeaturesView.tsx:17`). No confirmation. All switches disabled while one saves (`FeatureSwitches.tsx:42`). Failed load shows "Loading…" forever (`:12, :26`). Children *and* grandchildren indent the same `pl-6` (`:30`). The amber "inactive" note relies on the buggy `effective` (`:34-36`) |

**Frontend read sites:** `Sidebar.tsx:89-90, 106`; `MobileTabBar.tsx:24-26`; `CommandPalette.tsx:83, 86`; `DashboardHomeView.tsx:125, 146, 166, 170, 505-507`; `DashboardApp.tsx:865, 879, 881`; `UploadModal.tsx:76-77`; `VideoEditorStudio.tsx:823`; `ClipBrollPanel.tsx:147`; `ReelsView.tsx:387, 413`; `PlanSelectionModal.tsx:157`; `ConnectedPlatformsPanel.tsx:269-284`. Only `ConnectedPlatformsPanel` tells loading apart from off. Everywhere else, flagged navigation pops in once the request completes. `DashboardApp.tsx:879/881` render an empty main area on a deep link to `/dashboard/reels` or `/dashboard/editor` until flags arrive.

### 1.3 The parent-flag bug

`resolve()` checks only `stored[flag.parent]` (`service.py:23-24`), and it checks the parent's *stored* value, not its effective one. Concrete failure:

- Admin turns `broll_studio` **off**, leaving `broll_studio.reels` and `broll_studio.reels.footage` stored **on**.
- `broll_studio.reels` → off (correct).
- `broll_studio.reels.footage` → `stored[footage] and stored[reels]` → **on**. `/edits` (`edit_engine/route.py:30`) stays open.
- `…footage.opus_director` → on if stored on, so Pro footage reels still bill at 1.5x (`edit_engine/service.py:90`, `jobs.py:242`).
- The UI hides Reels because `DashboardApp.tsx:879` checks `broll_studio.reels`. The API stays open behind a hidden UI, so an admin who turned off the master switch believes B-roll is off when it is not.
- The admin page shows no amber warning for the grandchild (`FeatureSwitches.tsx:34`), because `effective` is wrong.

### 1.4 Entitlements (stay separate)

`subscription/entitlements.py:97-250` holds a frozen `Entitlements` per plan slug. It is resolved by `SubscriptionService.get_entitlements` (`subscription/service.py:321-324`) and served at `GET /subscription/entitlements`. It is enforced with `PRO_REQUIRED`, `LIMIT_REACHED` and related codes, which open the upsell modal (`lib/api.ts:496-507`). This design keeps it as is. §3.7 states exactly where the two systems meet.

### 1.5 What exists for real-time and caching

- In-process SSE broker, per user only: `notifications/broker.py:19-45`. It is single-process by design (`:3-6`), streamed at `notifications/service.py:49-61`, and consumed by `useNotificationInbox` with backoff reconnect ([audit/02 §4.6](audit/02-data-layer.md)).
- In-process GCRA rate limiter: `core/rate_limit.py:16-20`, default `300/min` (`:41`).
- One uvicorn process with in-process workers (`main.py:50-63`: `social_worker()` in the lifespan).
- No Redis client, no Next.js middleware (`frontend/middleware.ts` absent). The auth token lives in `localStorage` (`lib/auth.ts:9-33`), so Next server code cannot know who the user is today.

---

## 2. Requirements → design at a glance

| Need (00-audit §6.3, audit/07 §3.6, audit/02 §7.3) | Design |
|---|---|
| Typed definitions, one source | `FlagDefinition` / `ConfigDefinition` in Python; generated TS (§3.1, §8.4) |
| Owner, description, default, parent, dependency, expiry | Fields on the definition; registry validated at import and in tests |
| Global, per-user, per-workspace, per-plan, % rollout, staff | Targeting: overrides → ordered rules (segment/plan/user/workspace + rule %) → fallthrough % (§3.3) |
| Kill switch overriding everything | `killed` column; cascades to descendants and dependants; dedicated permission and endpoint (§3.4) |
| Fix the hierarchy | Full ancestor chain and `requires`, each evaluated with the same rules (§3.5) |
| Server-side, no flicker | Bootstrap payload into `FlagsProvider` from a server component once auth is a cookie; snapshot fallback until then (§4) |
| Kill reaches an open tab within seconds | `flags.changed` event on the real-time channel + `FEATURE_DISABLED` handler + focus/poll fallback (§4.4) |
| Remote config | Same engine, typed values, validated by Pydantic `TypeAdapter` (§5) |
| Audit log | Append-only `flag_audit_log` with before/after/reason; permissions (§6) |
| Signed-out pages | Anonymous evaluation with a first-party `cn_anon` id, only for flags marked `public` (§4.2) |
| Tests force flags | `force_flags` fixture / `flags.override()`; dev-only env forcing; no production client forcing (§11) |

---

## 3. Target model

### 3.1 Flag definitions (Python, the source of truth)

`backend/feature_flags/registry.py` keeps its role and grows:

```python
FlagKind = Literal["release", "ops", "experiment"]
#   release:    temporary; ships a new thing; has an expiry; removed after 100%
#   ops:        permanent kill switch / cost switch (social_publishing, ai_shots, opus_director)
#   experiment: temporary A/B, compared by cohort; has an expiry

@dataclass(frozen=True)
class FlagDefinition:
    key: str
    label: str
    description: str
    owner: str                                   # role or person, e.g. "frontend-lead"
    kind: FlagKind
    created: date
    default: bool = False                        # value when no DB row exists
    parent: str | None = None                    # hierarchy: off parent ⇒ off child, any depth
    requires: tuple[str, ...] = ()               # non-hierarchical dependencies
    bucket_by: Literal["user", "workspace"] = "user"
    client: bool = True                          # sent in the bootstrap payload
    public: bool = False                         # evaluated for signed-out visitors
    live_update: Literal["immediate", "next_navigation"] = "immediate"
    expires: date | None = None                  # required for release/experiment
```

Import-time validation (also a unit test):
- every `parent` and `requires` exists;
- no cycles across `parent` and `requires` combined;
- `release` and `experiment` flags have `expires`, at most 180 days after `created`;
- a `public` flag is also `client`;
- keys match `^[a-z0-9_]+(\.[a-z0-9_]+)*$` and are at most 100 characters (the existing column is `String(100)`).

**Why in code, not the DB:** a typo still fails loudly, a flag can never exist without the code that reads it, and generated TS types stay exact (AGENTS.md "API Contracts"). The DB holds only *state*: targeting, kills and overrides.

### 3.2 Evaluation context

```python
@dataclass(frozen=True)
class FlagContext:
    user_id: str | None
    workspace_id: str | None
    plan: str | None            # effective plan slug from SubscriptionService.get_effective_plan
    role: str | None            # "user" | "admin"
    email: str | None           # segment matching by domain only; never logged
    anon_id: str | None         # signed-out visitors (§4.2)
```

- **Built once per request** by a `FlagContextDep` dependency. Plan is loaded **only if** the snapshot contains a rule that references plans (`snapshot.needs_plan`), so most requests add no query. Today a plan lookup is a DB read (`subscription/service.py:317-319`).
- **Workspace.** No request carries a workspace id today ([audit/02 §7.2](audit/02-data-layer.md)). Use an `X-Workspace-Id` header validated against membership once Wave 3 adds it. Until then, `workspace_id = None`, and `bucket_by="workspace"` falls back to the user id.
- **Background work.** Workers build the context from the job's `user_id` (`FlagContext.for_user(session, user_id)`). Today `pipeline/service.py:815` and `edit_engine/jobs.py:242` evaluate globally. That is harmless today, but it ignores targeting once targeting exists.
- **Pinning.** A long-running unit of work evaluates release flags once at start and stores the result (`flag_snapshot` jsonb on the run/job row, §7.1). A run started under `prompt_streaming_v2` finishes under it. Kills are still honoured at the next safe point (§3.4).

### 3.3 Targeting

Stored state per flag (one row in `feature_flags`, extended in §7):

| Field | Meaning |
|---|---|
| `enabled` (existing column) | Targeting on. False ⇒ everyone gets **off** (rules and overrides ignored). Kept as the legacy "switch" |
| `killed`, `killed_reason`, `killed_by`, `killed_at` | Emergency off; overrides everything (§3.4) |
| `rules` jsonb | Ordered list, first match wins |
| `rollout_bps` | Fallthrough percentage in basis points 0–10000 (0.01% resolution). **Server default 10000**, so every existing `enabled=true` row stays on for everyone |
| `bucket_salt` | Defaults to the key; changing it reshuffles cohorts (audited, admin action "Reshuffle") |
| `version` | Optimistic concurrency + cache invalidation |

Overrides (per user, per workspace) live in `targeting_overrides` so they can be listed and purged by subject.

**Rule shape** (shared by flags and config):

```json
{
  "id": "r_staff",
  "description": "Staff see it first",
  "when": { "segments": ["staff"], "plans": [], "user_ids": [], "workspace_ids": [] },
  "rollout_bps": 10000,
  "serve": true
}
```

- Within `when`, every non-empty list must match (AND). Within a list, any value matches (OR).
- A rule with `rollout_bps < 10000` matches only users in its bucket range. Otherwise evaluation continues to the next rule.
- At most 20 rules per flag and 500 overrides per flag. Beyond that the console says to use a segment.

**Segments** (`flag_segments` table): named sets matched by `user_ids`, `email_domains` and `roles`. Two are built in by the migration:
- `staff`: role `admin`, plus an explicit user list that the owner fills.
- `beta`: empty, for later opt-in.

Segments are cached in the same snapshot.

**Stable hashing**

```
bucket(flag, unit_id) = int.from_bytes(sha256(f"{salt}:{unit_id}".encode()).digest()[:8], "big") % 10000
in_rollout = bucket < rollout_bps
```

- `unit_id` is the user id, or the workspace id for `bucket_by="workspace"`, or `anon_id` when signed out. No unit means not in the rollout.
- The salt is per flag, so the same 10% of users do not get every new flag.
- Raising the percentage only *adds* users. Someone in at 1% stays in at 10%, 50% and 100%.
- The hash lives on the server only; the frontend never computes it.

### 3.4 Kill switch

`killed = true` makes the flag **off** for every context, before any other step. Compared with "targeting off", a kill:

1. **Cascades** to every descendant and every flag that `requires` it, without touching their stored state. Un-killing restores exactly the previous targeting.
2. **Needs its own permission** (`flags.kill`, §6.2), so on-call can kill without being able to roll out.
3. **Requires a reason and typing the key**, writes an audit entry, notifies every admin in-app, and pushes `flags.changed` with the killed keys so open tabs drop the feature at once (§4.4).
4. **Reaches background work.** Jobs re-check `flags.is_enabled(key, ctx)` at their safe points (each pipeline step, each agent step, each social publish attempt, as `social/publisher.py:100-102` already does). A kill stops new work within one step. It never corrupts a step in progress.

### 3.5 Evaluation order (flags)

```
evaluate(key, ctx):
  1. unknown key                      → raise KeyError (tests/dev); production: False + error log
  2. snapshot[key].killed             → OFF  reason=KILLED
  3. any ancestor or `requires` (recursively, memoised per call) evaluates OFF
                                      → OFF  reason=ANCESTOR_OFF / REQUIREMENT_OFF (names the key)
  4. no DB row                        → definition.default  reason=DEFAULT
  5. not row.enabled                  → OFF  reason=TARGETING_OFF
  6. user override                    → value  reason=USER_OVERRIDE
  7. workspace override               → value  reason=WORKSPACE_OVERRIDE
  8. first matching rule              → rule.serve  reason=RULE (rule id)
  9. fallthrough: bucket < rollout_bps → ON/OFF  reason=ROLLOUT_IN / ROLLOUT_OUT
```

- Step 3 evaluates each ancestor with the **same context and full rules**, not its stored value. This fixes §1.3: if `broll_studio` is off, every descendant is off at any depth. If a parent is at 10%, a child can only be on for that same 10%.
- An override cannot beat a kill or an off ancestor. That is deliberate: kill means kill.
- Expiry never changes the value. It only produces warnings and a CI failure (§10.4). Silently flipping a flag on a date is a production incident waiting to happen.

### 3.6 Fail-safe behaviour

| Situation | Behaviour |
|---|---|
| Snapshot refresh fails | Keep the last good snapshot, log, expose `snapshot_age_seconds` in the admin API; health warns over 300 s |
| Cold start and DB unavailable | Code defaults. Release flags default off, so new UI fails closed |
| Bootstrap request fails on the client | Last good payload for this user if present (§4.3), else definition defaults from the generated file |

### 3.7 Flags vs entitlements — the boundary

| Question | System | Error | Client reaction |
|---|---|---|---|
| Is this feature released to this person yet / still alive? | Flags | 403 `FEATURE_DISABLED` | Hide it; refresh flags |
| Does their plan include it / how much of it? | Entitlements | `PRO_REQUIRED`, `LIMIT_REACHED`, … | Upsell modal (existing, `lib/api.ts:551-555`) |

Rules:
- A plan-targeted flag rule is a rollout tactic, for example "Pro first". It is never the way to make something Pro-only.
- The "(Pro)" in the `broll_studio.ai_shots` label (`registry.py:82`) is enforced by entitlements already (`broll/generation.py:123-125`); the label suffix is dropped.
- A component that needs both checks combines them with one helper in Wave 3 (`useAccess(feature)` returning `{visible, allowed, reason}`), which [audit/02 §7.3](audit/02-data-layer.md) asks for. This doc only fixes that the flag half comes from `useFlag`.
- Remote config values that are **plan promises** are read *through* entitlements (§5.3), so the UI keeps one "what my plan allows" source.

---

## 4. Server-side evaluation, delivery and no flicker

### 4.1 Backend cache

```
Postgres (feature_flags, targeting_overrides, flag_segments, remote_config, flag_state)
   │  load all rows (≈ tens of rows; overrides capped)          ← startup, after a local write,
   ▼                                                               on NOTIFY, or every 15 s poll of flag_state.version
FlagSnapshot (immutable, in-process, swapped atomically)
   ▼
flags.is_enabled(key, ctx)  — synchronous, pure, no I/O
```

- **Zero queries per check**, compared with one `SELECT` per check today (`service.py:33-35`). This matters most for the router-level dependencies, which run on every request to `/uploads`, `/reels`, `/broll`, `/edits` and `/editor`.
- **Invalidation.** Every write bumps `flag_state.version` in the same transaction and runs `NOTIFY flags_changed, '<version>'`.
  - The writing process swaps its snapshot immediately.
  - Other processes swap on `LISTEN`, through one dedicated asyncpg connection.
  - A 15 s poll of the single-row `flag_state` table is the safety net (about 5,800 primary-key reads a day).
  - Today's one-process deployment needs only the first path. The others make scaling to more workers free.
- **Why not Redis:** it adds a service to run and pay for, for a dataset of a few kilobytes that Postgres already serves with change notification. Reconsider only if we run more than about 10 API processes.

### 4.2 The bootstrap payload

`GET /api/v1/flags/bootstrap`, with **optional** auth (contract in §8.2):

- **Signed in:** every `client=True` flag evaluated for the caller, every `client=True` config value, and the snapshot version.
- **Signed out:** only `public=True` flags and config. The unit is a first-party `cn_anon` cookie (random 128-bit id, 1 year, `SameSite=Lax`, not linked to a user). It is set by the Next server or by this endpoint, and used only for bucketing. The compliance pass's cookie notice already covers first-party functional cookies; confirm this is listed (owner question 4).
- **Never** sends descriptions, owners, rules, overrides or `client=False` keys. Today `/features` sends every key, including `opus_director` (`route.py:20-22`); the legacy endpoint keeps doing so for compatibility (§9), but new consumers read the bootstrap.
- `Cache-Control: private, no-store`. Correct per user, so not cacheable by a CDN.

### 4.3 Getting it into Next.js without flicker

**Target (needs the httpOnly session cookie, which Wave 3 / security S-1 in [audit/07 §7](audit/07-settings-billing-admin.md) is expected to deliver):**

1. `frontend/lib/flags/server.ts` exports `getFlags()`. It is wrapped in React `cache()` so one request makes one call, reads `cookies()`, and calls the bootstrap endpoint server-to-server with `cache: 'no-store'` and a 300 ms timeout. On timeout it returns `null`.
2. The root signed-in layout (`app/dashboard/(shell)/layout.tsx` in its Wave 3 form) awaits `getFlags()` and renders `<FlagsProvider bootstrap={payload}>`. Server components can branch directly (`if (flags.new_ui_shell)` picks the shell), so the first HTML already has the right navigation. No loading state, no layout shift.
3. **Middleware is not used for flags.** Calling the API from the edge on every navigation adds latency, and HMAC-signed flag cookies would need a shared secret in Next. Route-level choices happen in the layout. Revisit only if a flag must redirect before any HTML streams.

**Interim (token still in `localStorage`, server cannot see the user):**

- `FlagsProvider` boots from the **last payload for this user id**, stored under `localStorage['flags:v1:<userId>']` with its version and a 24 h maximum age, and revalidates at once. This removes layout shift for returning users.
- First-ever load has no payload, so it uses the generated defaults (everything a release flag gates is off). Gated slots render a fixed-size skeleton (`<Flagged flag=… fallback={<NavItemSkeleton/>}>`) instead of popping in. This keeps today's "never flash a dark feature" rule without the layout jump.
- A stale snapshot can show a just-killed entry point for the few hundred ms before revalidation. That is acceptable, because the API refuses it, and the global `FEATURE_DISABLED` handler (§4.4) hides it on first use.
- The store is keyed by user id and cleared on sign-out, which fixes today's cross-user module cache.

**One store, not per-hook state.** `FlagsProvider` holds a single external store (`useSyncExternalStore`). A refresh updates every consumer, which fixes `useFeatureFlags.ts:53`. `flags.new_ui_*` values are **sticky per page session**: a change with `live_update="next_navigation"` is applied at the next route change or reload, never by swapping the whole shell under someone mid-edit. If a `next_navigation` flag is killed, a quiet banner offers "Clipnera was updated — reload" and the switch happens on the next navigation.

### 4.4 Kill switch to an open tab within seconds

```
Admin "Kill" ──► POST /admin/flags/{key}/kill
   tx: update row, audit row, bump flag_state.version, NOTIFY flags_changed
   ▼ (same process: immediate; others: LISTEN, < 100 ms)
snapshot swapped ──► realtime.broadcast({type: "flags.changed", version, killed: [key, …descendants]})
   ▼ (SSE, < 1 s)
open tab: store applies killed keys = false immediately → refetches /flags/bootstrap
```

- **Channel.** This rides the per-user real-time stream that Wave 3 is designing (`docs/revamp/architecture/backend.md`, not yet written at the time of this doc — see §14). What this design needs from it:
  1. a `broadcast(event)` to every connected user, which the current broker lacks (`notifications/broker.py:36-42` is per user only);
  2. one event type `flags.changed` with payload `FlagsChangedEvent` (§8.2);
  3. on reconnect, the client refetches the bootstrap, matching the existing inbox pattern ([audit/02 §4.6](audit/02-data-layer.md)).

  Until Wave 3 ships, the same event goes on today's `/notifications/stream` as a second SSE event name (`event: flags`), next to `event: notification` (`notifications/service.py:61`). That is a small, additive change.
- **Payload.** The event carries no evaluated values (they differ per user), just the version and the killed keys. The client applies kills locally and refetches everything else.
- **Fallbacks, in order:**
  1. a global `FEATURE_DISABLED` handler in `authedRequest`, mirroring `UPGRADE_REQUIRED_EVENT` (`lib/api.ts:507, 551-555`), sets that flag off in the store and refetches;
  2. refetch on `visibilitychange` to visible;
  3. while the stream is disconnected, poll the bootstrap every `flags.client_poll_seconds` (config, default 60).

  Worst case without the stream is about 60 s. With it, under 2 s.
- **Ramp-ups** (off → on) use the same event. Values change per `live_update`: `immediate` flags update in place; `next_navigation` flags wait for the next navigation.

---

## 5. Remote config

### 5.1 Definitions

```python
ValueKind = Literal["int", "float", "bool", "string", "enum"]
Unit = Literal["bytes", "seconds", "credits", "ratio", "count", "per_minute"] | None

@dataclass(frozen=True)
class ConfigDefinition:
    key: str
    label: str
    description: str
    owner: str
    kind: ValueKind
    default: int | float | bool | str
    unit: Unit = None
    minimum: float | None = None
    maximum: float | None = None
    choices: tuple[str, ...] = ()           # enum only
    client: bool = False                    # sent in the bootstrap payload
    public: bool = False
    plan_promise: bool = False              # read through entitlements (§5.3)
```

- **Validation.** A `pydantic.TypeAdapter` is built from the definition (`Annotated[int, Field(ge=min, le=max)]`, `Literal[*choices]`, …). It runs on every admin write, on every rule `serve`, and on snapshot load. An invalid stored value (for example after a min/max tightened in code) is ignored in favour of the code default and logged.
- **Targeting.** The same as flags, steps 6–8 of §3.5 (overrides, ordered rules with segments, plans and rule %). The fallthrough is the stored `default_value` or the code default. Config has no kill and no hierarchy.
- **Reading.** `flags.config(key, ctx) -> T`, synchronous from the snapshot.

### 5.2 Catalogue (initial)

| Key | Kind / unit | Default | Bounds | Targeting | Client | Consumed by |
|---|---|---|---|---|---|---|
| `agent.approval_credit_threshold` | int, credits | **60** (= 30 min × `CREDITS_PER_VIDEO_MINUTE` 2.0, `core/config.py:56`; principles §14 Q3) | 0–10000 | plan | yes (card copy) | Wave 3 agent runtime: Edit-mode run pauses on "Go ahead" when the estimate exceeds it (principles §5) |
| `agent.approval_timeline_removal_ratio` | float, ratio | **0.5** | 0.05–1.0 | plan | yes | Same, "removes more than a set share of the timeline" |
| `agent.checkin_credit_threshold` | int, credits | **60** | 0–10000 | plan | yes | Mid-run check-in card when *actual* spend crosses it (principles §9) |
| `agent.auto_retry_cap` | int, count | **1** | 0–3 | global | no | Runtime automatic retries (principles §8, "capped at one") |
| `notifications.email_min_job_seconds` | int, seconds | **300** | 0–86400 | global | yes (settings copy) | Email on completion for jobs longer than this (principles §9, §14 Q4) |
| `uploads.max_bytes` | int, bytes | `settings.UPLOAD_MAX_BYTES` (10 GiB, `core/config.py:102`) | 100 MiB–50 GiB | plan | yes | `uploads/` initiate; `plan_promise=True` |
| `storage.user_library_quota_bytes` | int, bytes | Free **2 GiB**, Pro **50 GiB** (placeholders for Wave 4; owner question 2) | 0–1 TiB | plan | yes | Wave 4 user B-roll library; `plan_promise=True` |
| `rate_limit.default_per_minute` | int, per_minute | **300** (`core/rate_limit.py:41`) | 30–3000 | global only | no | Rate-limit middleware fallback |
| `rate_limit.agent_runs_per_minute` | int, per_minute | **6** | 1–60 | global only | no | Prompt submission route |
| `flags.client_poll_seconds` | int, seconds | **60** | 15–600 | global | yes | Client fallback poll (§4.4) |

- Rate limits are **global only**. `RateLimitMiddleware` runs before the body is read and must stay free of DB and plan lookups (`core/rate_limit.py:10-13`). It reads the snapshot synchronously. Per-plan rate limits are out of scope.
- Values that are product constants with pricing implications (`CREDITS_PER_VIDEO_MINUTE`, credit pack prices) stay in settings and entitlements. Changing a price through a console with no deploy and no review is a finance risk, not a convenience.

### 5.3 Plan promises go through entitlements

For `plan_promise=True` keys, `SubscriptionService.get_entitlements` (`subscription/service.py:321`) reads `flags.config(key, ctx_for_plan)` and returns the value as a new `EntitlementsResponse` field (`max_upload_bytes`, `storage_quota_bytes`). Exceeding one raises a plan error code (`UPLOAD_TOO_LARGE`, `STORAGE_QUOTA_EXCEEDED`), added to `PLAN_ERROR_CODES` (`lib/api.ts:496`) so the existing upsell path handles it. Result:

- the pricing page (`GET /subscription/plans`) and the settings page show the configured numbers;
- the two systems stay separate in code: entitlements *reads* config and does not merge with flags;
- the console labels these keys "Shown to customers on pricing", and saving one requires a second confirmation (§7.3).

---

## 6. Audit log and admin permissions

### 6.1 Audit log

Every write through the admin API produces one row, in the **same transaction** as the change:

| Column | Type | Notes |
|---|---|---|
| `id` | bigint identity PK | ordered |
| `at` | timestamptz | server time |
| `actor_id` | `String(36)` FK users, `SET NULL` | |
| `actor_email` | `String(255)` | snapshot, so history stays readable if the admin is deleted (fixes "Deleted admin" in credits history) |
| `action` | enum | `flag.update`, `flag.kill`, `flag.unkill`, `flag.reshuffle`, `override.set`, `override.delete`, `config.update`, `segment.update`, `legacy.switch` |
| `target_kind` / `target_key` | text | `flag`/`config`/`segment` + key |
| `subject_type` / `subject_id` | text, nullable | for overrides (user or workspace id; never the email) |
| `before` / `after` | jsonb | full state of the target before and after |
| `reason` | text, required, 10–500 chars | the legacy PATCH writes "Legacy switch (no reason)" |
| `request_id`, `ip` | text | from the existing request middleware |

- **Append-only, enforced in the DB.** A `BEFORE UPDATE OR DELETE` trigger raises an exception. The table is tiny and kept forever.
- **Deletion flow.** The account deletion service (compliance pass) deletes `targeting_overrides` and `flag_segments` membership for the user. Audit rows keep only the opaque `subject_id`.
- **Read** at `GET /admin/flags/audit` (all targets) and `GET /admin/flags/{key}/history`, with cursor pagination.

### 6.2 Who may change flags

Today any `admin` can do anything (`auth/dependencies.py:63`; S-3 in [audit/07 §7](audit/07-settings-billing-admin.md)). Proposal: a small permission table, with no change to `UserRole`.

| Permission | Allows | Granted by migration to |
|---|---|---|
| `flags.view` | Read console, history, evaluate tool | every existing admin |
| `flags.kill` | Kill / un-kill | every existing admin |
| `flags.edit` | Targeting, rules, rollout %, overrides, reshuffle | every existing admin |
| `config.edit` | Remote config values | every existing admin |
| `segments.edit` | Segment membership | every existing admin |

- `admin_permissions(user_id, permission)`, PK on both columns. It is checked by a `require_admin_permission("flags.edit")` dependency layered on `get_current_admin`, so the role is still re-read on every request.
- The migration grants everything to current admins, so nothing breaks. The value comes later, when a support or finance admin is added who should not roll out UI.
- Grants are managed by migration or SQL for now. Like the role itself (S-5), they are deliberately not editable in the app.
- **No two-person approval** in phase 1. It is too heavy for a one-to-three-person team. The mitigations are a required reason, a confirmation that shows the diff, the audit log, and in-app notification to every admin on kill and on any 100% ramp of a `release` flag.

---

## 7. Data model and migrations

### 7.1 Tables

```
feature_flags (existing; extended)
  key            String(100) PK                      (existing)
  enabled        Boolean NOT NULL default false      (existing; meaning: targeting on)
  updated_by     String(36) FK users SET NULL        (existing)
  updated_at     DateTime NOT NULL                   (existing)
  rollout_bps    Integer NOT NULL server_default 10000   CHECK 0..10000
  rules          JSONB   NOT NULL server_default '[]'
  bucket_salt    String(100) NULL                    (NULL = key)
  killed         Boolean NOT NULL server_default false
  killed_reason  Text NULL
  killed_by      String(36) FK users SET NULL
  killed_at      DateTime NULL
  version        Integer NOT NULL server_default 1

targeting_overrides
  target_kind    String(16)  ('flag' | 'config')
  target_key     String(100)
  subject_type   String(16)  ('user' | 'workspace')
  subject_id     String(36)
  value          JSONB NOT NULL          (bool for flags; typed for config)
  reason         Text NOT NULL
  expires_at     DateTime NULL           (ignored after; swept daily)
  created_by     String(36) FK users SET NULL
  created_at     DateTime NOT NULL
  PK (target_kind, target_key, subject_type, subject_id)
  INDEX (subject_type, subject_id)       — "what is this user forced into", deletion purge

flag_segments
  key            String(64) PK
  description    Text
  user_ids       ARRAY(String(36)) NOT NULL default '{}'
  email_domains  ARRAY(String(255)) NOT NULL default '{}'
  roles          ARRAY(String(16)) NOT NULL default '{}'
  version, updated_by, updated_at

remote_config
  key            String(100) PK
  default_value  JSONB NULL              (NULL = code default)
  rules          JSONB NOT NULL default '[]'
  version, updated_by, updated_at

flag_state                               (single row, id = 1)
  version        BigInteger NOT NULL     (bumped by every write; NOTIFY payload)

flag_audit_log                           (§6.1) + trigger flag_audit_log_append_only

admin_permissions
  user_id        String(36) FK users CASCADE
  permission     String(32)
  granted_at     DateTime
  PK (user_id, permission)

flag_exposures_daily                     (optional, phase 1 part C)
  day date, flag_key String(100), value bool, plan String(16) NULL, count BigInteger
  PK (day, flag_key, value, plan)
```

- **Run pinning** (§3.2) adds `flag_snapshot JSONB NULL` to the Wave 3 run table, owned by that design. Only `release` and `experiment` flags are stored, typically under 200 bytes.
- **Exposures** are counted in memory by the engine on bootstrap, not per check, and flushed every 60 s as upserts. That gives cohort sizes for the rollout dashboard without a per-request write. Per-request exposure logging is rejected as too costly for what it tells us.

### 7.2 Alembic plan

The head is `20261003010000` (`alembic/versions/20261003010000_add_editor_projects.py:14-15`). Revisions are timestamp ids, matching the repo convention:

| Revision | Content | Reversible |
|---|---|---|
| `20261010010000_extend_feature_flags` | Add the new `feature_flags` columns (server defaults keep existing rows' meaning: `enabled=true` → on for 100%); create `flag_state` with version 1 | yes (drop columns) |
| `20261010020000_add_targeting_tables` | `targeting_overrides`, `flag_segments` (seed `staff` with roles `{admin}`, `beta` empty), `remote_config` | yes |
| `20261010030000_add_flag_audit_log` | Table, enum, append-only trigger; one `legacy.import` row per existing `feature_flags` row recording its current state, so history starts complete | yes (drops history; warn in the downgrade docstring) |
| `20261010040000_add_admin_permissions` | Table; grant the five permissions to every `users.role='admin'` | yes |

No data is rewritten and no key is renamed. The registry rows for new flags (§9.1) are created lazily: no row means the code default.

---

## 8. Contracts

All responses use the `{data, message, error}` envelope (`core/responses.py:16-23`, `ok()`). Errors go through `CustomException` as today. New error codes: `FLAG_VERSION_CONFLICT` (409), `CONFIG_INVALID` (422, `extra.field`), `FORBIDDEN` (403, existing) for a missing permission, and `NOT_FOUND` (404, existing) for an unknown key.

### 8.1 Endpoints

| Method + path | Auth | Request | Response `data` |
|---|---|---|---|
| GET `/flags/bootstrap` | optional | — | `FlagsBootstrapResponse` |
| GET `/features` **(legacy, unchanged shape)** | user | — | `FeatureFlagsResponse` — now evaluated for the caller |
| GET `/admin/features` **(legacy)** | admin + `flags.view` | — | `AdminFeatureFlagListResponse` (unchanged; `effective` now correct to any depth) |
| PATCH `/admin/features/{key}` **(legacy)** | admin + `flags.edit` | `AdminFeatureFlagUpdateRequest` | `AdminFeatureFlagListResponse`; writes `legacy.switch` audit |
| GET `/admin/flags` | `flags.view` | `?q=&kind=&state=&stale=` | `AdminFlagListResponse` |
| GET `/admin/flags/{key}` | `flags.view` | — | `AdminFlagDetailResponse` |
| PATCH `/admin/flags/{key}` | `flags.edit` | `AdminFlagUpdateRequest` | `AdminFlagDetailResponse` |
| POST `/admin/flags/{key}/kill` | `flags.kill` | `AdminFlagKillRequest` | `AdminFlagDetailResponse` |
| POST `/admin/flags/{key}/unkill` | `flags.kill` | `AdminReasonRequest` | `AdminFlagDetailResponse` |
| PUT `/admin/flags/{key}/overrides` | `flags.edit` | `AdminOverrideRequest` | `AdminFlagDetailResponse` |
| DELETE `/admin/flags/{key}/overrides/{subject_type}/{subject_id}` | `flags.edit` | `?reason=` | `AdminFlagDetailResponse` |
| POST `/admin/flags/{key}/evaluate` | `flags.view` | `AdminEvaluateRequest` | `AdminEvaluationResponse` |
| GET `/admin/flags/{key}/history` | `flags.view` | `?cursor=` | `AdminAuditPageResponse` |
| GET `/admin/flags/audit` | `flags.view` | `?cursor=&target_key=` | `AdminAuditPageResponse` |
| GET `/admin/config` / GET `/admin/config/{key}` | `flags.view` | — | `AdminConfigListResponse` / `AdminConfigDetailResponse` |
| PATCH `/admin/config/{key}` | `config.edit` | `AdminConfigUpdateRequest` | `AdminConfigDetailResponse` |
| PUT/DELETE `/admin/config/{key}/overrides…` | `config.edit` | as flags | `AdminConfigDetailResponse` |
| GET `/admin/segments`, PATCH `/admin/segments/{key}` | `flags.view` / `segments.edit` | `AdminSegmentUpdateRequest` | `AdminSegmentListResponse` |
| GET `/admin/flags/health` | `flags.view` | — | `{snapshot_version, snapshot_age_seconds, process_count_seen}` |

### 8.2 Pydantic (`backend/feature_flags/schema.py`)

```python
ConfigValue = Union[bool, int, float, str]          # bool first so True is not coerced to 1
SubjectType = Literal["user", "workspace"]
FlagKind = Literal["release", "ops", "experiment"]
LiveUpdate = Literal["immediate", "next_navigation"]
EvalReason = Literal["KILLED", "ANCESTOR_OFF", "REQUIREMENT_OFF", "DEFAULT", "TARGETING_OFF",
                     "USER_OVERRIDE", "WORKSPACE_OVERRIDE", "RULE", "ROLLOUT_IN", "ROLLOUT_OUT"]

# --- public ---
class FlagsBootstrapResponse(BaseModel):
    version: int
    evaluated_at: datetime
    subject: Literal["user", "anonymous"]
    flags: Dict[str, bool]
    config: Dict[str, ConfigValue]
    poll_seconds: int

class FlagsChangedEvent(BaseModel):            # real-time payload, event name "flags.changed"
    version: int
    killed: List[str] = []

class FeatureFlagsResponse(BaseModel):          # unchanged
    flags: Dict[str, bool]

# --- targeting ---
class TargetCondition(BaseModel):
    segments: List[str] = []
    plans: List[str] = []
    user_ids: List[str] = []
    workspace_ids: List[str] = []

class FlagRule(BaseModel):
    id: str = Field(pattern=r"^r_[a-z0-9_]{1,32}$")
    description: str = Field("", max_length=200)
    when: TargetCondition
    rollout_bps: int = Field(10000, ge=0, le=10000)
    serve: bool

class ConfigRule(FlagRule):
    serve: ConfigValue                          # validated against the definition's TypeAdapter

class OverrideResponse(BaseModel):
    subject_type: SubjectType
    subject_id: str
    subject_label: str                          # email or workspace name, admin only
    value: ConfigValue
    reason: str
    expires_at: Optional[datetime] = None
    created_by_email: Optional[str] = None
    created_at: datetime

# --- admin flags ---
class AdminFlagSummary(BaseModel):
    key: str
    label: str
    description: str
    owner: str
    kind: FlagKind
    parent: Optional[str] = None
    requires: List[str] = []
    default: bool
    client: bool
    public: bool
    live_update: LiveUpdate
    created: date
    expires: Optional[date] = None
    stale: bool                                 # past expires, or release flag at 100% for > 14 days
    enabled: bool
    killed: bool
    rollout_bps: int
    rule_count: int
    override_count: int
    blocked_by: Optional[str] = None            # nearest killed/off ancestor or requirement
    version: int
    updated_at: Optional[datetime] = None
    updated_by_email: Optional[str] = None

class AdminFlagListResponse(BaseModel):
    flags: List[AdminFlagSummary]
    snapshot_version: int

class AdminFlagDetailResponse(AdminFlagSummary):
    rules: List[FlagRule]
    overrides: List[OverrideResponse]
    children: List[str]
    dependants: List[str]
    killed_reason: Optional[str] = None
    killed_at: Optional[datetime] = None
    killed_by_email: Optional[str] = None
    exposures_7d: Dict[str, int] = {}           # {"on": n, "off": n}

class AdminReasonRequest(BaseModel):
    reason: str = Field(min_length=10, max_length=500)

class AdminFlagUpdateRequest(AdminReasonRequest):
    expected_version: int
    enabled: bool
    rules: List[FlagRule] = Field(default_factory=list, max_length=20)
    rollout_bps: int = Field(ge=0, le=10000)

class AdminFlagKillRequest(AdminReasonRequest):
    confirm_key: str                            # must equal the path key

class AdminOverrideRequest(AdminReasonRequest):
    subject_type: SubjectType
    subject: str                                # user email or id / workspace id; resolved server-side
    value: ConfigValue
    expires_at: Optional[datetime] = None

class AdminEvaluateRequest(BaseModel):
    user: Optional[str] = None                  # email or id; None = anonymous
    workspace_id: Optional[str] = None

class AdminEvaluationResponse(BaseModel):
    key: str
    value: ConfigValue
    reason: EvalReason
    rule_id: Optional[str] = None
    blocked_by: Optional[str] = None
    bucket: Optional[int] = None                # 0..9999

# --- audit ---
class AdminAuditEntry(BaseModel):
    id: int
    at: datetime
    actor_email: Optional[str] = None
    action: str
    target_kind: Literal["flag", "config", "segment"]
    target_key: str
    subject_type: Optional[SubjectType] = None
    subject_id: Optional[str] = None
    before: Optional[Dict[str, Any]] = None
    after: Optional[Dict[str, Any]] = None
    reason: str

class AdminAuditPageResponse(BaseModel):
    entries: List[AdminAuditEntry]
    next_cursor: Optional[str] = None

# --- admin config ---
class AdminConfigSummary(BaseModel):
    key: str
    label: str
    description: str
    owner: str
    kind: Literal["int", "float", "bool", "string", "enum"]
    unit: Optional[Literal["bytes", "seconds", "credits", "ratio", "count", "per_minute"]] = None
    minimum: Optional[float] = None
    maximum: Optional[float] = None
    choices: List[str] = []
    client: bool
    plan_promise: bool
    code_default: ConfigValue
    default_value: Optional[ConfigValue] = None     # stored; None = code default
    rule_count: int
    override_count: int
    version: int
    updated_at: Optional[datetime] = None
    updated_by_email: Optional[str] = None

class AdminConfigListResponse(BaseModel):
    configs: List[AdminConfigSummary]

class AdminConfigDetailResponse(AdminConfigSummary):
    rules: List[ConfigRule]
    overrides: List[OverrideResponse]
    by_plan: Dict[str, ConfigValue]                 # resolved value per plan, for the table view

class AdminConfigUpdateRequest(AdminReasonRequest):
    expected_version: int
    default_value: Optional[ConfigValue] = None
    rules: List[ConfigRule] = Field(default_factory=list, max_length=20)

class AdminSegmentResponse(BaseModel):
    key: str
    description: str
    user_count: int
    email_domains: List[str]
    roles: List[str]
    version: int

class AdminSegmentListResponse(BaseModel):
    segments: List[AdminSegmentResponse]

class AdminSegmentUpdateRequest(AdminReasonRequest):
    expected_version: int
    add_users: List[str] = []                       # emails or ids
    remove_users: List[str] = []
    email_domains: Optional[List[str]] = None
    roles: Optional[List[str]] = None
```

The legacy schemas `FeatureFlagsResponse`, `AdminFeatureFlagResponse`, `AdminFeatureFlagListResponse` and `AdminFeatureFlagUpdateRequest` (`schema.py:9-31`) stay unchanged.

### 8.3 TypeScript (`frontend/lib/flags/types.ts`, hand-written, mirrors §8.2 exactly)

```ts
export type ConfigValue = boolean | number | string;
export type SubjectType = 'user' | 'workspace';
export type FlagKind = 'release' | 'ops' | 'experiment';
export type LiveUpdate = 'immediate' | 'next_navigation';
export type EvalReason = 'KILLED' | 'ANCESTOR_OFF' | 'REQUIREMENT_OFF' | 'DEFAULT' | 'TARGETING_OFF'
  | 'USER_OVERRIDE' | 'WORKSPACE_OVERRIDE' | 'RULE' | 'ROLLOUT_IN' | 'ROLLOUT_OUT';

export interface FlagsBootstrapResponse {
  version: number;
  evaluated_at: string;
  subject: 'user' | 'anonymous';
  flags: Partial<Record<FlagKey, boolean>>;      // only client flags; absent ⇒ generated default
  config: Partial<Record<ConfigKey, ConfigValue>>;
  poll_seconds: number;
}
export interface FlagsChangedEvent { version: number; killed: FlagKey[] }

export interface TargetCondition { segments: string[]; plans: string[]; user_ids: string[]; workspace_ids: string[] }
export interface FlagRule { id: string; description: string; when: TargetCondition; rollout_bps: number; serve: boolean }
export interface ConfigRule extends Omit<FlagRule, 'serve'> { serve: ConfigValue }
export interface OverrideResponse {
  subject_type: SubjectType; subject_id: string; subject_label: string; value: ConfigValue;
  reason: string; expires_at: string | null; created_by_email: string | null; created_at: string;
}
export interface AdminFlagSummary {
  key: FlagKey; label: string; description: string; owner: string; kind: FlagKind;
  parent: FlagKey | null; requires: FlagKey[]; default: boolean; client: boolean; public: boolean;
  live_update: LiveUpdate; created: string; expires: string | null; stale: boolean;
  enabled: boolean; killed: boolean; rollout_bps: number; rule_count: number; override_count: number;
  blocked_by: FlagKey | null; version: number; updated_at: string | null; updated_by_email: string | null;
}
export interface AdminFlagListResponse { flags: AdminFlagSummary[]; snapshot_version: number }
export interface AdminFlagDetailResponse extends AdminFlagSummary {
  rules: FlagRule[]; overrides: OverrideResponse[]; children: FlagKey[]; dependants: FlagKey[];
  killed_reason: string | null; killed_at: string | null; killed_by_email: string | null;
  exposures_7d: Record<string, number>;
}
export interface AdminReasonRequest { reason: string }
export interface AdminFlagUpdateRequest extends AdminReasonRequest {
  expected_version: number; enabled: boolean; rules: FlagRule[]; rollout_bps: number;
}
export interface AdminFlagKillRequest extends AdminReasonRequest { confirm_key: FlagKey }
export interface AdminOverrideRequest extends AdminReasonRequest {
  subject_type: SubjectType; subject: string; value: ConfigValue; expires_at?: string | null;
}
export interface AdminEvaluateRequest { user?: string | null; workspace_id?: string | null }
export interface AdminEvaluationResponse {
  key: FlagKey | ConfigKey; value: ConfigValue; reason: EvalReason;
  rule_id: string | null; blocked_by: FlagKey | null; bucket: number | null;
}
export interface AdminAuditEntry {
  id: number; at: string; actor_email: string | null; action: string;
  target_kind: 'flag' | 'config' | 'segment'; target_key: string;
  subject_type: SubjectType | null; subject_id: string | null;
  before: Record<string, unknown> | null; after: Record<string, unknown> | null; reason: string;
}
export interface AdminAuditPageResponse { entries: AdminAuditEntry[]; next_cursor: string | null }
export interface AdminConfigSummary {
  key: ConfigKey; label: string; description: string; owner: string;
  kind: 'int' | 'float' | 'bool' | 'string' | 'enum';
  unit: 'bytes' | 'seconds' | 'credits' | 'ratio' | 'count' | 'per_minute' | null;
  minimum: number | null; maximum: number | null; choices: string[]; client: boolean; plan_promise: boolean;
  code_default: ConfigValue; default_value: ConfigValue | null; rule_count: number; override_count: number;
  version: number; updated_at: string | null; updated_by_email: string | null;
}
export interface AdminConfigListResponse { configs: AdminConfigSummary[] }
export interface AdminConfigDetailResponse extends AdminConfigSummary {
  rules: ConfigRule[]; overrides: OverrideResponse[]; by_plan: Record<string, ConfigValue>;
}
export interface AdminConfigUpdateRequest extends AdminReasonRequest {
  expected_version: number; default_value: ConfigValue | null; rules: ConfigRule[];
}
export interface AdminSegmentResponse {
  key: string; description: string; user_count: number; email_domains: string[]; roles: string[]; version: number;
}
export interface AdminSegmentListResponse { segments: AdminSegmentResponse[] }
export interface AdminSegmentUpdateRequest extends AdminReasonRequest {
  expected_version: number; add_users?: string[]; remove_users?: string[];
  email_domains?: string[] | null; roles?: string[] | null;
}
```

### 8.4 Generated file (`frontend/lib/flags/registry.gen.ts`)

`backend/scripts/gen_flag_types.py` writes this file from the registry. It contains:
- `FlagKey` (union of every key);
- `ConfigKey`;
- `ConfigValues` (`{ 'agent.auto_retry_cap': number; … }`, typed per kind);
- `FLAG_DEFAULTS`, `CONFIG_DEFAULTS`, `FLAG_LIVE_UPDATE` and `FLAG_PARENTS`.

A pytest test regenerates it in memory and fails on any diff, so a Python change without regeneration fails CI. `lib/api.ts:1705-1718` becomes `export type FeatureFlagKey = LegacyFlagKey` (the 13 keys, re-exported from the generated file), so existing imports compile unchanged. `ALL_OFF` (`useFeatureFlags.ts:8-22`) is replaced by `FLAG_DEFAULTS`.

### 8.5 SDKs

**Backend** (`backend/feature_flags/engine.py`, module singleton `flags`):

```python
flags.is_enabled(key: str, ctx: FlagContext) -> bool          # sync, snapshot only
flags.require(*keys: str, ctx: FlagContext) -> None           # 403 FEATURE_DISABLED, same body as today
flags.config(key: str, ctx: FlagContext) -> ConfigValue       # sync, validated
flags.explain(key: str, ctx: FlagContext) -> Evaluation       # value + reason + rule + bucket
flags.bootstrap(ctx: FlagContext) -> FlagsBootstrapResponse
await flags.refresh() / flags.start(app) / flags.stop()       # lifespan wiring, LISTEN, poll

# FastAPI
FlagContextDep = Annotated[FlagContext, Depends(get_flag_context)]
require_flag(key) -> dependency                               # same name and signature as today
await FlagContext.for_user(session, user_id)                  # workers
```

`FeatureFlagService` (`service.py:29`) stays as a thin compatibility facade over the engine in global context during phase 1, then is removed once the call sites in §1.1 move to `flags.*`.

**Frontend** (`frontend/lib/flags/`):

```ts
// client
<FlagsProvider bootstrap={payload | null} userId={id | null}>
useFlag(key: FlagKey): boolean                       // never undefined: falls back to FLAG_DEFAULTS
useConfig<K extends ConfigKey>(key: K): ConfigValues[K]
useFlagsStatus(): { ready: boolean; version: number | null; source: 'server' | 'snapshot' | 'defaults' }
<Flagged flag="new_ui_dashboard" fallback={<Skeleton/>}>…</Flagged>

// server (RSC / route handlers)
getFlags(): Promise<FlagsBootstrapResponse | null>   // cache()d per request
getFlag(key): Promise<boolean>
```

`useFeatureFlags()` stays as a facade returning `{flags, isLoading, refresh}` from the same store, so the existing call sites in §1.2 keep working unchanged.

---

## 9. Flag catalogue

### 9.1 New flags for the revamp

| Key | Kind | Parent / requires | Default | Bucket | Live update | Owner | Expires | Notes |
|---|---|---|---|---|---|---|---|---|
| `new_ui_shell` | release | — | off | user | next_navigation | Frontend lead | 2027-03-31 | New shell, navigation and prompt bar; gates every `new_ui_*` page |
| `new_ui_dashboard` | release | parent `new_ui_shell` | off | user | next_navigation | Frontend lead | 2027-03-31 | Home, projects, upload |
| `new_ui_editor` | release | parent `new_ui_shell`; requires `agent_editor` | off | user | next_navigation | Frontend lead | 2027-03-31 | New Editor screens; a session in progress is never swapped |
| `new_ui_settings` | release | parent `new_ui_shell` | off | user | next_navigation | Frontend lead | 2027-03-31 | Settings and billing |
| `new_ui_admin` | release | — | off; rule `staff` only | user | next_navigation | Backend lead | 2027-03-31 | Admin console (Wave 6 area 10); admin-only by nature, so it never goes to a percentage |
| `prompt_streaming_v2` | release | requires `agent_editor` | off | user | next_navigation | Backend lead | 2027-01-31 | Wave 3 run event stream v2; evaluated at run start and pinned to the run (§3.2); `client=True` so the UI picks the matching parser |
| `broll_platform_library` | release | parent `broll_studio` | off | user | immediate | Product owner | 2027-03-31 | User-facing browse of the curated library (Wave 4). The admin library is unaffected, as today (`registry.py:64-65`) |
| `broll_user_library` | release | parent `broll_studio` | off | user | immediate | Product owner | 2027-03-31 | Personal uploads; quotas from `storage.user_library_quota_bytes` |

`public=True` is off for all of these. Marketing-page experiments are added as `experiment` flags when needed.

### 9.2 The 13 existing keys

No key is renamed, so every consumer listed in §1 keeps working. Existing rows keep their exact effective value, apart from the grandchild fix.

| Key | New kind | Owner | Expires | Parent | Change |
|---|---|---|---|---|---|
| `social_publishing` | ops | Backend lead | — | — | Permanent kill switch (platform outage, API cost) |
| `social_publishing.youtube` | ops | Backend lead | — | `social_publishing` | — |
| `social_publishing.instagram` | ops | Backend lead | — | `social_publishing` | — |
| `social_publishing.tiktok` | ops | Backend lead | — | `social_publishing` | Product scope is YouTube + Instagram; kept off; review at the first cleanup |
| `social_publishing.x` | ops | Backend lead | — | `social_publishing` | Same; X bills every post (`registry.py:54`) |
| `video_upload` | ops | Backend lead | — | — | Becomes a permanent kill switch for storage cost spikes |
| `broll_studio` | ops | Product owner | — | — | Master switch |
| `broll_studio.cutaways` | release | Product owner | 2027-01-31 | `broll_studio` | Remove after stable 100% |
| `broll_studio.reels` | release | Product owner | 2027-01-31 | `broll_studio` | — |
| `broll_studio.ai_shots` | ops | Product owner | — | `broll_studio` | Veo cost switch; "(Pro)" dropped from the label (§3.7) |
| `broll_studio.reels.footage` | release | Product owner | 2027-01-31 | `broll_studio.reels` | **Grandparent fix applies** |
| `broll_studio.reels.footage.opus_director` | ops | Backend lead | — | `broll_studio.reels.footage` | `client=False` (server behaviour); **grandparent fix applies** |
| `agent_editor` | release | Backend lead | 2027-03-31 | — | Required by `new_ui_editor` and `prompt_streaming_v2` |

**Transition for `GET /features`:**
- The shape `{flags: {key: bool}}` is unchanged. It now returns the 13 legacy keys, plus every new `client=True` key, evaluated for the caller. Extra keys are safe for `Record<FeatureFlagKey, boolean>` consumers.
- It is marked deprecated in the OpenAPI description, and the frontend stops calling it once `FlagsProvider` ships (phase 1 part B).
- It is removed only after one release with no calls in the access logs.

---

## 10. Admin console UX (phase 2; built in Wave 6 area 10 with the new design system)

This replaces `/admin/features` and the switch block in `/admin/social`. The social page keeps a read-only "Feature status" strip that links to the console, so the platform health view is unchanged. Per AGENTS.md, removing the switches from `/admin/social` needs the owner's confirmation (owner question 6).

### 10.1 Flag list (`/admin/flags`)

- **Header.** "Feature flags", environment badge (`APP_ENV`), snapshot age if over 60 s, and a "Remote config" tab.
- **Toolbar.**
  - Search across key, label and owner, with `/` to focus.
  - Filters: Kind (Release, Ops, Experiment), State (Off, Staff only, Rolling out, On, Killed, Default), "Needs cleanup" (stale).
  - A Tree / Flat toggle. The tree indents per depth level, which fixes the single 24 px indent (`FeatureSwitches.tsx:30`).
- **Row:**
  - label and key in monospace;
  - a state chip: `Off`, `Staff only`, `12.5%`, `On`, `Killed` (red), or `On by default`;
  - a "Blocked by `broll_studio`" note whenever an ancestor or requirement is off;
  - owner, last change ("2h ago by a@…"), stale badge, and an override count.
- **Row click** opens the detail page. There is no inline toggle, so no accidental flips (today one click flips with no confirmation).

### 10.2 Flag detail (`/admin/flags/[key]`)

- **Header.** Label, key with a copy button, kind, owner, description, created/expires, parent and children as links, `requires`.
- **Primary actions:**
  - **Kill** (red, needs `flags.kill`). When killed, the button becomes **Restore**, and a red banner shows the reason, who and when.
  - **Check a user**: email in, value and reason chain out ("Off — blocked by `broll_studio` (killed)").
- **Targeting tab:**
  1. "Targeting" switch (the stored `enabled`).
  2. **Overrides.** Users and workspaces with On/Off, reason, optional expiry. Add by email or workspace id, with an autocomplete of existing users.
  3. **Rules.** An ordered list you can drag to reorder. Each rule is a chip builder (Segment is staff / Plan is Pro / User is … / Workspace is …), plus a rule percentage and Serve On/Off. "Add rule" offers presets: "Staff only", "Pro first".
  4. **Everyone else** rollout slider, with stops at 0, 1, 10, 50 and 100 and a numeric field to 0.01%. Beside it, "≈ N of M active users" from `flag_exposures_daily`.
  5. **Save bar.** Sticky while there are unsaved changes. Shows a plain-language diff ("Rollout 10% → 50%; added rule 'Pro first'"), a required reason (10+ characters) and Save. A 100% ramp of a `release` flag adds "This turns it on for everyone" and notifies all admins.
- **History tab.** A timeline of audit entries: who, when, action, reason, and an expandable before/after diff. Cursor "Load more".
- **Usage tab.** Seven-day on/off exposure counts by plan. Links to the code reference (generated from the registry: `registry.py` line of the definition).

### 10.3 Remote config (`/admin/config`)

- **List.** Key, label, current default with unit formatting (bytes as GB, seconds as minutes, ratio as %), a "Shown on pricing" badge for `plan_promise`, and last change.
- **Detail:**
  - typed editor: number with unit and inline min/max validation, enum select, bool switch;
  - a **per-plan table** (Free | Pro | legacy Pro+) showing the resolved value with "from rule / default";
  - rules and overrides as for flags;
  - the same save bar and history.
- **Plan-promise keys** need a second confirmation: "This changes what customers are promised on the pricing page."

### 10.4 States (every screen)

| State | Behaviour |
|---|---|
| Loading | Skeleton rows matching the layout; no "Loading…" text that can stick (today's bug, [audit/07 §6.6](audit/07-settings-billing-admin.md)) |
| Load failed | Inline error with Retry; the rest of the admin shell stays usable |
| Empty search | "No flags match '…'" + Clear filters |
| No history | "No changes since this flag was created" |
| Saving | Save button busy; the form is read-only; other flags stay interactive (today all switches lock) |
| Saved | Toast "Saved — live for everyone within seconds" with a link to the history entry |
| Version conflict (409) | "Someone changed this flag while you were editing", with their diff and a choice: reload, or reapply mine on top |
| Validation error (422) | Field-level message from `extra.field` |
| No permission | Read-only view, lock icon on actions, "You can view flags but not change them" |
| Killed | Red banner at the top of detail and a red chip in the list; targeting is editable but shown as "Inactive while killed" |
| Blocked by parent | Amber banner naming the blocking ancestor, with a link |
| Stale | Amber "Past its expiry — remove the flag or extend it" with owner; extend requires a reason |
| Snapshot stale | Header warning if `snapshot_age_seconds > 300` |
| Mobile | List, detail, Kill/Restore and Check a user work at phone width (on-call); the rule builder collapses to stacked fields |

Kill dialog: a real modal, not `window.confirm` (S-8 in [audit/07 §7](audit/07-settings-billing-admin.md)). It contains:
- the impact: "Turns off for everyone, including N dependent flags: …";
- a required reason;
- "Type `broll_studio` to confirm";
- a red **Kill feature** button.

Restore uses the same dialog, without the typing step.

---

## 11. Testing

**Backend unit tests (pure, no DB): `tests/test_flag_engine.py`**
- Evaluation order: one test per step of §3.5, including that an override loses to a kill and to an off ancestor.
- Hierarchy:
  - a killed or off ancestor at depth 1, 2 and 3 turns descendants off (the regression test for §1.3, using the real `broll_studio.reels.footage.opus_director` chain);
  - `requires` is respected;
  - cycles are rejected at registry load.
- Hashing:
  - **golden vectors**: fixed `(salt, unit_id) → bucket` pairs checked into the test, so any change to the hash is caught (it would silently reshuffle every rollout);
  - **monotonic ramp**: for 10,000 random ids, in at p implies in at q for all q > p;
  - **distribution**: 100,000 ids at 1,000 bps land in the 9.5–10.5% band;
  - **independence**: two flags at 50% overlap by about 25%, not 50%.
- Config: TypeAdapter rejects out-of-range and wrong-type values; an invalid stored value falls back to the code default; `bool` is not coerced to `int`.
- Registry: release flags have an expiry; `client`/`public` consistency; **generated TS is up to date**; **expired + 14 days grace ⇒ fail** (the cleanup forcing function).

**Backend integration (throwaway Postgres + `TEST_DATABASE_URL`, per the existing plans-DB pattern):**
- the migration upgrades from `20261003010000` with existing rows and preserves effective values, except the grandchild case;
- the audit row is in the same transaction (a failed write leaves no row);
- the append-only trigger rejects UPDATE and DELETE;
- `expected_version` produces a 409;
- permissions return 403;
- the legacy `GET/PATCH /admin/features` and `GET /features` shapes are unchanged (snapshot test against `schema.py:9-31`);
- NOTIFY causes a snapshot swap.

**Forcing flags in tests** (replaces the hand-written `Flags` fakes in `tests/test_broll_flags.py:18-40` and `tests/test_generation.py:90`):

```python
@pytest.fixture
def force_flags():
    with flags.override({"broll_studio": True, "broll_studio.cutaways": True}, config={"agent.auto_retry_cap": 0}) as f:
        yield f   # f.set("agent_editor", False) inside a test
```

`flags.override()` swaps in a snapshot overlay. It is honoured only when `settings.APP_ENV != "production"`; production raises. Hierarchy still applies to forced values, so a test cannot accidentally pass with an impossible state.

**Development forcing:** `FLAGS_FORCE="new_ui_shell=on,agent.auto_retry_cap=0"`, read by `DevelopmentConfig`/`TestingConfig` only and ignored with a warning in `ProductionConfig`. In production, staff test with a **per-user override on themselves** ("Turn on for me" in the console), which is audited. There is no URL-parameter or `localStorage` forcing in production builds, because that would let anyone open dark features.

**Frontend:**
- `FlagsProvider` takes a `bootstrap` prop, so component tests render with any combination.
- A `tsc --noEmit` check covers the generated union (no `next build` while the user's dev server runs).
- Store tests: a refresh updates every consumer; sign-out clears; a `FEATURE_DISABLED` response flips the flag; a `flags.changed` kill applies before the refetch resolves; `next_navigation` flags defer.

---

## 12. Rollout runbook (every `release` flag; required for `new_ui_*` and `prompt_streaming_v2`)

**Before stage 1:**
- The flag is defined with owner and expiry.
- Both paths, old and new, are deployed and tested.
- The kill path has been rehearsed in staging: kill, confirm the UI drops within 5 s in an open tab, restore.
- The metric queries below are saved.

| Stage | Targeting | Minimum dwell | Watch | Advance when | Roll back (kill) when |
|---|---|---|---|---|---|
| 0. Internal | Rule `staff` serve on; fallthrough 0% | 2 days of real use by staff | Every error in logs tagged with the flag; staff feedback | No P0/P1 bugs open | Any data loss or wrong-charge bug |
| 1. 1% | + fallthrough 100 bps | 24 h and ≥ 50 exposed users | 5xx rate on gated routes vs control; `FEATURE_DISABLED` counts; run/pipeline failure rate; credits refunded; support contacts | Guardrails within threshold | 5xx > 2× control or > 1% absolute; run failure > control +20% relative; any wrong charge |
| 2. 10% | 1,000 bps | 2 days | Above + experience budgets (principles §5: first plan text p50 < 1.5 s, p95 < 3 s for `prompt_streaming_v2`); AI cost per source minute (admin AI usage page); export failure rate | Budgets met; cost within +10% | Budget p95 missed for 2 h; cost > +25% |
| 3. 50% | 5,000 bps | 3 days | Above, at volume; DB load (`pg_stat_statements` top queries); SSE connection count | Stable, no new error class | As above |
| 4. 100% | 10,000 bps | 14 days stable | Same; old path traffic now zero | → cleanup | As above |

**Rules for every stage:**
- **Rollback = kill switch, never a deploy.** Kill, investigate, fix, deploy, then **Restore**. Restore returns to exactly the same percentage and cohort, because the salt is unchanged. Advance again from that stage; never jump straight to the next one.
- **Cohort comparison** uses the pinned `flag_snapshot` on runs and exports (§7.1) to split failure, cost and latency by on/off. It uses `flag_exposures_daily` for cohort sizes. Gaps: there is no client error reporting and no real-user page metrics today. Wave 3/7 must add a client error beacon and web-vitals reporting, tagged with the flag version, before `new_ui_*` passes stage 1 (owner question 5).
- **Kill switches are not experiments.** If a flag gets killed twice at the same stage, the owner writes a short note in the flag's history before the next attempt.

**Cleanup policy:**
1. At 100% for 14 days with no kill → the flag shows **stale** in the console and CI starts warning.
2. Within the next 14 days, the owner removes the old UI and code path, removes the definition, regenerates TS, and adds a migration that deletes the row and its overrides. Audit rows are kept.
3. Past `expires` + 14 days, CI fails until the flag is removed or its expiry is extended with a reason (the extension is a code change, so it is reviewed).
4. `new_ui_*` flags are removed together with the old components they replace. Removing old UI needs the owner's explicit confirmation per AGENTS.md "UI Rules"; the cleanup PR lists every component it deletes.
5. `ops` flags never expire. They are reviewed every quarter for "is this still a real kill switch?".

**Pre-deploy check for phase 1 (the grandchild fix changes behaviour).** Before deploying, run this against production:

```sql
SELECT c.key FROM feature_flags c
  JOIN feature_flags p  ON p.key  = regexp_replace(c.key, '\.[^.]+$', '')
  JOIN feature_flags gp ON gp.key = regexp_replace(p.key, '\.[^.]+$', '')
 WHERE c.enabled AND p.enabled AND NOT gp.enabled;
```

The registry's `parent` is what counts; this query approximates it from the dotted keys. Any row it returns is a feature that is **live today only because of the bug** and goes dark on deploy. The owner decides per row whether to switch on the ancestor first.

---

## 13. Phased implementation plan

### Phase 1 — engine and API, backward compatible, no visible UI change

| Step | Work | Files (indicative) | Done when |
|---|---|---|---|
| 1.0 | Run the pre-deploy query (§12) on production; owner decides any rows | — | Decision recorded |
| 1.1 | Migrations §7.2 | `alembic/versions/2026101001…04` | Upgrade/downgrade pass on a copy of prod data |
| 1.2 | Registry v2: metadata on the 13 + 8 new flags; config definitions; import-time validation | `feature_flags/registry.py`, new `feature_flags/config_registry.py` | Registry tests green |
| 1.3 | Engine: snapshot loader, pure `evaluate()`, hashing, context builder, `flags` SDK, LISTEN + poll, lifespan wiring | new `feature_flags/engine.py`, `context.py`; `main.py` lifespan | Engine tests green; zero DB queries per check |
| 1.4 | Compat: `require_flag` and `FeatureFlagService` delegate to the engine; legacy endpoints audited; `resolve()` fixed to the full chain | `dependencies.py`, `service.py`, `route.py` | Legacy contract tests unchanged |
| 1.5 | Move the 13 call sites to `flags.*` with real context; workers use `FlagContext.for_user` | sites in §1.1 | Existing tests pass with `force_flags` |
| 1.6 | New public + admin endpoints, schemas, permissions, audit | `feature_flags/route.py`, `schema.py`, new `admin_permissions` | Contract tests; envelope everywhere |
| 1.7 | Config consumers that exist today: `uploads.max_bytes` via entitlements, `rate_limit.default_per_minute`, `notifications.email_min_job_seconds` (when the email job lands) | `subscription/service.py`, `core/rate_limit.py`, `uploads/` | Defaults equal today's values, so no behaviour change |
| 1.8 | TS codegen + hand-written types; `featuresApi`/`adminFeaturesApi` unchanged | `scripts/gen_flag_types.py`, `lib/flags/registry.gen.ts`, `lib/flags/types.ts` | Freshness test; `tsc --noEmit` |

**Phase 1 part B — frontend plumbing (still invisible):**
- `FlagsProvider`, `useFlag`, `useConfig` and the `getFlags()` server helper;
- `useFeatureFlags` re-implemented over the store with the same return shape;
- the global `FEATURE_DISABLED` handler;
- the snapshot fallback;
- the `flags.changed` listener on today's notification stream (`event: flags`).

The only perceptible change is that flagged navigation no longer pops in for returning users. That is a layout-shift fix, not a UI change, but it is listed for the owner's awareness.

**Phase 1 part C:** `flag_exposures_daily` and the `flag_snapshot` pin on run rows, landing with Wave 3's run table.

### Phase 2 — admin console (Wave 6 area 10)

§10 built with the new design system behind `new_ui_admin` (staff rule). The old `/admin/features` stays until the console is at 100% for admins, and then it is removed with the owner's confirmation.

### Phase 3 — cleanup

- Remove the `FeatureFlagService` facade, the `GET /features` call sites and the `ALL_OFF` constant.
- Remove the TikTok/X keys if the product confirms they will not return.
- Then follow §12 per flag.

**Dependencies on other waves:** the real-time channel and run table (Wave 3, `architecture/backend.md`); httpOnly cookie auth for flicker-free server rendering (Wave 3 / security); the client error beacon and web-vitals reporting (Wave 3/7); `X-Workspace-Id` on requests (Wave 3); B-roll quotas (Wave 4).

---

## 14. Alignment notes

- **`docs/revamp/architecture/backend.md` did not exist** when this was written (checked 3 October 2026). §4.4 states the minimum this design needs from the real-time channel: `broadcast()`, a `flags.changed` event carrying `FlagsChangedEvent`, and refetch on reconnect. If backend.md picks a different envelope (for example a typed `{type, data}` event on one multiplexed stream), adopt its envelope and keep the payload. If it picks Redis for fan-out across processes, the engine's `NOTIFY` path can publish there instead; the design does not depend on which one.
- `prompt_streaming_v2` assumes the Wave 3 run stream exists and has a v1 to compare against. If Wave 3 ships only one protocol, the flag gates the whole streaming prompt experience instead, and its kind and rollout stay the same.

---

## 15. Open owner questions

| # | Question | Default if unanswered |
|---|---|---|
| 1 | Who is in the `staff` segment beyond admins? | Admins only |
| 2 | User B-roll library quotas per plan | Free 2 GiB, Pro 50 GiB (placeholders until Wave 4 prices storage) |
| 3 | Approval and check-in credit thresholds: same value, and per plan? | Both 60 credits (30 min of source) for every plan; tune after stage 2 data |
| 4 | Is a first-party `cn_anon` bucketing cookie acceptable under the current cookie notice? | Yes, as functional; list it on `/cookies` before any `public` flag is used |
| 5 | Add a client error beacon and web-vitals reporting (self-hosted, posting to our API) before `new_ui_*` goes past 1%? | Yes; required by the runbook |
| 6 | Once the console ships, remove the switch block from `/admin/social` in favour of a read-only status strip linking to the console? | Keep both until confirmed (AGENTS.md UI rule) |
| 7 | Retire `social_publishing.tiktok` and `.x` keys, given the YouTube + Instagram scope? | Keep, off, until the phase 3 review |
| 8 | Do any production flags currently rely on the grandchild bug (§12 query)? | Run the query before deploy; ask per row |
| 9 | Separate permissions now, or keep one admin role until a second kind of admin exists? | Ship the table with all permissions granted to every admin (no behaviour change) |
