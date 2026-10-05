# Clipnera UI revamp — Wave 6 screens, part 4: admin, publishing, share, reels, analytics, legal

Date: 5 October 2026. Author: Product Designer (Wave 6). Builds on [00-audit.md](../00-audit.md), [01-experience-principles.md](../01-experience-principles.md), [02-design-system.md](../02-design-system.md), [04-architecture.md](../04-architecture.md), [05-broll.md](../05-broll.md), [06-flags.md](../06-flags.md), [architecture/frontend.md](../architecture/frontend.md), [wave6/01-platform-api.md](../wave6/01-platform-api.md), [wave6/02-ui-catalog.md](../wave6/02-ui-catalog.md), and audit slices [06](../audit/06-reels-brand-social.md) and [07](../audit/07-settings-billing-admin.md). Structure follows [01-entry-and-dashboard.md](01-entry-and-dashboard.md). Where `wave6/07-visual-direction.md` exists and disagrees, it wins.

**Covers:**
- **Admin** (`/admin/**`, flag `new_ui_admin`): shell, Overview, Users, User detail, Payments, Credits, Social, AI usage, B-roll curation, Music, and the flags console (`/admin/flags`, `/admin/flags/[key]`, `/admin/config`, `/admin/audit`) that replaces `/admin/features`.
- **Publishing** (flag `new_ui_export`): Scheduler (`/dashboard/scheduler`), Composer (`/dashboard/scheduler/new`), connect flows.
- **Share page** (`/s/[shareId]`, new public URL).
- **Reels** (flag `new_ui_reels`): list and create, footage reel board, image reel board.
- **Analytics** (`/dashboard/analytics`): decision below — it stays hidden.
- **Legal** (`/privacy`, `/terms`, `/refunds`, `/cookies`) and the functional pages `/unsubscribe` and `/data-deletion`, restyled in the new marketing chrome with **content unchanged word for word**.

**Visual direction.** [07-visual-direction.md](../wave6/07-visual-direction.md) governs: admin and its tables use the **Compact** density (07 §4.2: `label` 13 text, 32 px controls and rows, 12 px panel padding) except at < 768 px where **Touch** applies (44 px targets); user screens use **Comfortable**. Plus Jakarta for all text including page titles (no Syne outside the wordmark), JetBrains Mono `tabular-nums` for every changing number, `title-lg` at 600, panels separated by gutters not outlines, `.cn-state` hover/press, status hues mean status only. The user sidebar has five destinations (07 §5.2): **Reels live under Projects** and **Analytics lives under Publish** — this spec follows that.

**Not covered:** Settings → Social accounts placement (Area 9 hosts it, using components exported from §13), the export dialog inside the editor (Area 8, separate spec), the user B-roll library (05-broll).

**Code written for this spec:** none. No mockups yet; each builder unit (§20) adds its state-switchable mock under `app/design-system/screens/<area>` only if the Design System agent agrees to host it.

### Decisions made here (owner to confirm)

| # | Decision | Where it shows |
|---|---|---|
| E1 | **Analytics stays hidden.** No nav entry, the URL renders an honest "not on yet" page. It ships only when the backend reads real post performance from YouTube and Instagram (§17) | Analytics, shell nav |
| E2 | The flags console lives at `/admin/flags`. `/admin/features` 308s there for new-UI admins; legacy users keep the old page | Admin nav, §9 |
| E3 | The Social admin page keeps a **read-only** "Feature status" strip linking to the console; the switches move to the console (06-flags owner Q6) | §7 |
| E4 | Scheduler and Composer show **YouTube and Instagram only**. TikTok and X accounts that exist stay listed as "Not supported in Clipnera any more" with Disconnect (D3 of screens/01) | §11–13 |
| E5 | Fake helpers are not carried over: "Suggested times", sample hashtags, hook ideas, "+41% predicted retention", the hook tester | §12, §17 |
| E6 | The composer is its own URL (`/dashboard/scheduler/new?clip=…`), not a modal, so clip cards, the editor and notifications can link to it | §12 |
| E7 | A finished reel can be published (requires API-S3); until then its board offers Download and "Share link" only | §15, §16 |
| E8 | Admin is desktop-first: full function from 1024 px, read-and-act at 768 px, and at 360 px every page renders without horizontal scroll, lists become cards, and the one-tap actions (approve/reject a payment, kill/restore a flag, force-disconnect) still work | All admin |
| E9 | Admin keeps the legacy client `AdminGate` until cookie auth ships (frontend.md §1.6). The server-side role check in `(admin)/layout.tsx` replaces it then; nothing else changes | §1 |
| E10 | Legal pages render their body from a verbatim copy guarded by a text-parity check against the legacy files (§18). Content that conflicts with E4 (TikTok, X named in Privacy and Terms) is **not** changed here | §18 |

### Rules every screen here follows

- Components from `components/ui` ([02-ui-catalog](../wave6/02-ui-catalog.md)) and `cn-*` tokens only. Anything missing is listed in §21 (DS-A*) with a stand-in the builder writes inside its own folder.
- One amber fill per view. In admin, the page's primary action is amber; row actions are secondary or ghost; destructive actions are `danger`.
- No spinners except the OAuth hand-off. Regions use skeletons after 300 ms; long work names its step (`WorkingText`).
- Every destructive or money action uses `Dialog` (`role="alertdialog"` for destructive), never `window.confirm` or `window.prompt` (fixes audit 07 S-8).
- Errors: what happened, what is safe, one action (02 §7.3). No "Something went wrong".
- Copy: sentence case, Indian English, first person for Clipnera in user screens ("I couldn't…"); admin copy is plain and impersonal ("Couldn't load payments"). No all-caps labels, nothing under 12 px (fixes audit 07 A-08, 06 P-X5).
- Every API call goes through a typed wrapper in `lib/api/<domain>/` whose types match the Pydantic schema field for field. `apiFetch` unwraps the envelope and passes raw bodies through, so today's non-envelope admin routes work unchanged; the envelope gap is API-X1.
- Lists use React Query with keys in `lib/query/keys/<domain>.ts`; filters and tabs live in the URL so Back and links keep them.
- Polling, where an event does not exist yet, pauses when the tab is hidden and refetches on focus (fixes audit 06 P-X3).
- Every flagged page shows a "not on for you" state instead of a blank page (fixes audit 06 P-X1).

---

## 1. Admin shell (`app/v2/(admin)/admin/layout.tsx`)

**Purpose.** One calm frame for operators, mounted once (fixes audit 07 D-07), with everything that needs a human in one glance.

**Gate.** Today: legacy `AdminGate` (client; spinner until `/me` says `role === 'admin'`). Kept as-is (E9) but wrapped so its loading state is the admin skeleton, not a full-screen spinner, and a non-admin sees "This area is for Clipnera staff" with "Back to Clipnera" instead of a silent redirect (audit 07 S-7). The wrapper lives in `components/admin-v2/shell/AdminAccess.tsx`; it imports `AdminGate` read-only and does not change it. If the gate cannot ship a custom not-authorised state without editing it, the wrapper calls `userApi.getMe` itself through `lib/api/admin/me.ts` and drops `AdminGate` — the builder picks the one that keeps the legacy file untouched.

**Layout.**

| Width | Layout |
|---|---|
| ≥ 1024 | `Sidebar` 240 px (collapsible to a 56 px rail, persisted with `usePersistentState('cn.admin.rail')`). `TopBar` 48 px (`h-12`, 07 §5.2): Breadcrumbs · environment Badge · "Back to Clipnera" ghost link · `AvatarMenu`. Content column max 1280 px, gutter 32 px |
| 768–1023 | Rail 56 px; expand opens 240 px over the page |
| < 768 | No sidebar. `TopBar` start = menu `IconButton` ("Admin sections") opening a left `Drawer` with the same nav; Breadcrumbs collapse to a back link. Gutter 16 px. No tab bar |

**Sidebar.** Header: `Wordmark` (link "Clipnera home" → `/dashboard`) + neutral Badge "Admin" (no violet, fixes R40). Sections:

| Section | Items (icon) | Count / dot |
|---|---|---|
| Operate | Overview (LayoutDashboard), Users (Users), Payments (CreditCard), Credits (Coins) | Payments: pending count from `GET /admin/overview` (refetch 60 s) |
| Platform | Social (Share2), AI usage (Cpu) | Social: dot when `recent_failures` in the last 24 h > 0 |
| Content | B-roll (Clapperboard), Music (Music) | — |
| Controls | Flags (ToggleRight), Remote config (SlidersHorizontal), Audit log (ScrollText) | Flags: rose dot when any flag is killed |

Footer: "Back to Clipnera" item and the admin's email (truncated, Tooltip full).

**Environment badge.** `production` neutral, anything else amber-subtle "Staging" etc., from `NEXT_PUBLIC_APP_ENV` (Platform request RQ-3). Hidden if unset.

**Shared page header (`AdminPageHeader`, DS-A1).** `h1` `text-cn-title-lg`, one-line description `fg-secondary` (max 70 ch), actions slot right (wraps under on < 768), optional `meta` line ("Updated 2 min ago · Refresh"). Every admin page uses it.

**States.** Gate checking: skeleton of sidebar + header + table. Not admin: EmptyState (Lock) "This area is for Clipnera staff" · "Your account doesn't have admin access. If you think it should, ask the owner." · Back to Clipnera. `/me` failed: "Couldn't check your access. Your session is fine; this is usually a connection problem." · Try again (does **not** send to `/login`, fixes S-7). 401: `apiFetch` sends to `/login?next=`. Segment `loading.tsx`/`error.tsx`/`not-found.tsx` exist from Platform (`app/v2/_platform/*`); Area 10 restyles nothing there, it only passes the admin copy.

**Keyboard and screen reader.** Skip link → `main#main`. `aside` "Admin sidebar" holding `nav` "Admin". `g` then a letter jumps (`g o` Overview, `g u` Users, `g p` Payments, `g f` Flags) — listed in a Kbd help dialog on `?`. Counts are spoken ("Payments, 3 to review").

**API.** `GET /me` (role), `GET /admin/overview` (pending count), `GET /admin/social/overview?days=1` (dot), `GET /admin/flags` (killed dot; shares the list cache with §9). Admin permissions for read-only states: API-A1.

**Legacy parity.**

| Legacy (`AdminLayout`, `AdminGate`) | New |
|---|---|
| 240 px rail, 8 links, violet "ADMIN" tag | 240/64 px rail, 11 links in 4 groups, neutral Admin badge |
| "Back to the app" bottom link | Kept (sidebar footer + TopBar) |
| Phone: scrolling chip row of 8 links | Phone: Drawer with the full nav (no clipped chips) |
| Frame remounts on each navigation | Mounted once in the layout |
| Spinner, silent redirect for non-admins, network error → `/login` | Skeleton, explicit not-authorised page, retryable error |
| B-roll and Features missing from the app sidebar's admin list (P-10) | App shell links "Admin" from the account menu (screens/01 R20) to `/admin/overview`; every section reachable here |

---

## 2. Overview (`/admin/overview`)

**Purpose.** An answer, not a dashboard: what needs a person today, then how the business is moving.

**Layout (≥ 1024).**
1. `AdminPageHeader` "Overview" · "What needs attention, then growth. Days are UTC." · meta "Updated 1 min ago · Refresh".
2. **Needs attention** card (Perplexity-style summary): one sentence built from real counts, then up to four rows, each a link with an icon and a count. Rows: "3 payments to review" → Payments; "2 posts failed in the last 24 hours" → Social; "Flag `broll_studio` is killed" → flag detail; "Flags snapshot is 6 min old" (when `snapshot_age_seconds > 300`) → Flags. Empty: success-tone line "Nothing needs you right now."
3. **This month** — 4 `StatCard`s: Free users, Active Pro users, Revenue this month (₹, `font-cn-mono`), Payments to review (`tone="accent"` when > 0, hint "Review now" / "All caught up", whole card links to Payments).
4. **Growth** — heading + `SegmentedControl` 7 / 30 / 90 days (URL `?days=`). 8 `StatCard`s in a 4-column grid, each with a `Sparkline` of its daily series (Total users + "N new", Active today, Active 7 d, Active 30 d, Projects, Clips, Revenue, AI cost → links to AI usage).
5. **Trend** — one Recharts bar chart (DS-A2 `DailyBars`, tokens only) with a `SegmentedControl` choosing the metric (Sign-ups, Active users, Logins, Projects, Clips, Revenue, AI cost) and the range total beside the title ("Active users counts distinct people in the range, not a sum"). Below it, `Disclosure` "Day by day" → `DataTable` (Day + 7 numeric columns, newest first).

Tablet: grids go to 2 columns. Phone: 1 column of StatCards (2 per row from 400 px), chart full width 200 px tall, table becomes cards.

**States.** Loading: StatCard `loading` + chart skeleton (separately for overview and growth). Overview failed: InlineAlert danger "Couldn't load this month's figures. Growth below may still load." · Try again. Growth failed: same, scoped. Zero data: StatCards show "0", chart shows "No activity in this range" instead of an empty plot (fixes `DailyBarChart` empty-plot issue). Partial (growth ok, overview failed): both render independently. Range switching: previous data stays, dimmed, with `WorkingText` "Loading 90 days" (no layout jump).

**API.** `GET /admin/overview` → `AdminOverviewResponse` (raw); `GET /admin/growth?days=` → `AdminGrowthResponse` (envelope); `GET /admin/social/overview?days=1` (failures count); `GET /admin/flags/health`, `GET /admin/flags` (killed). B-roll review count when 05-broll ships (`GET /admin/broll/assets?status=in_review&limit=1` → `total`).

**Legacy parity.**

| Legacy (`AdminOverviewView`, `DailyBarChart`) | New |
|---|---|
| 4 tiles incl. amber "Payments to review" | Kept as StatCards, same links and hints |
| Growth 7/30/90 toggle, 8 tiles | Kept, plus sparklines |
| 7 Recharts instances at once (F-04) | One chart with a metric switch; sparklines are tiny Recharts but no axes |
| Hard-coded hex chart colours | Tokens |
| "Show day-by-day table" | Disclosure "Day by day" |
| No retry, no last-updated | Retry per block, "Updated … · Refresh" |
| — | New "Needs attention" summary (real counts only) |

---

## 3. Users (`/admin/users`)

**Purpose.** Find a person fast and do the three common things (grant, revoke, add credits) without leaving the list.

**URL state.** `?q=&sort=newest|last_active|projects|ai_cost&page=`.

**Layout.** `AdminPageHeader` "Users" · "Grant Pro for refunds, gifts or testing, or revoke it. Open a user to see everything they have done." Toolbar: `SearchField` "Search email or name" (`/` focuses, 300 ms debounce, `loading` while fetching) · sort `Menu` button "Sort: Newest sign-ups" (Newest sign-ups, Recently active, Most projects, Highest AI cost). Then `DataTable`:

| Column | Render | Notes |
|---|---|---|
| User (primary) | Avatar 24 + name (or email) + email below; Badge "Admin" | Row link to detail (`cardLinkOverlay` technique) |
| Plan | Badge accent "Pro" / neutral "Free" + "until 12 Nov 2026" / "No expiry" | |
| Last active | relative day | sortable (`last_active`) |
| Projects | mono | sortable (`projects`) |
| Clips | mono | `hideOnMobile` |
| Credits | mono | `hideOnMobile` |
| Paid | ₹ mono | `hideOnMobile` |
| AI cost | $ mono | sortable (`ai_cost`) |
| Joined | date | sortable (`newest`, descending only) |
| Actions | `Menu` (`IconButton` "Actions for asha@…"): Grant Pro… / Extend Pro…, Revoke Pro… (danger, Pro only), Add credits…, separator, Open user | `hideHeader` |

Only the four server sorts are sortable headers; the rest are plain. `Pagination` in cursor mode (`hasNext` = page returned 50 rows), 50 per page.

**Dialogs (shared with §4, DS-A3 `PlanDialog`, DS-A4 `CreditsDialog`).**
- Grant/Extend Pro (`Dialog sm`): title "Give asha@… Pro" / "Extend Pro for asha@…"; preset `Chip`s 7 · 30 · 365 days; `NumberField` "Days" 1–3650; preview line "Pro until about 12 Nov 2026 (added on top of the time left)"; Cancel / **Give 30 days of Pro** (amber, loading "Saving"). Reason field appears once API-A2 exists.
- Revoke (`alertdialog`): "Revoke Pro from asha@…?" · "They move to Free now. Their credits are capped at the Free allowance. This can't be undone, but you can grant Pro again." · Keep Pro (focused) / Revoke Pro (danger).
- Add credits: see §6 form, pre-filled with the email.

After success: row updates in place from the response (`AdminUserResponse`), toast "asha@… has Pro until 12 Nov 2026".

**States.** Loading: 8 skeleton rows. Empty (no users at all): "No users yet." Empty search: "No users match 'asha'. Search by full email or part of a name." · Clear search. Error: InlineAlert "Couldn't load users. Nothing was changed." · Try again. Page loading: Pagination `loading`, current rows stay. Action pending: that row's Menu trigger `loading`; other rows stay usable. Action failed: danger toast with the server message and the list is refetched (someone else may have changed it). 403 (API-A1): actions hidden, line "You can view users but not change plans."

**360 px.** Rows become cards: name + email, Plan badge, Last active, AI cost, the actions Menu top-right. Search full width; sort Menu as an icon button.

**API.** `GET /admin/users?q&limit=50&offset&sort` → `AdminUserResponse[]` (raw); `PATCH /admin/users/{id}/plan` `AdminUserPlanRequest {plan, days?}` → `AdminUserResponse` (raw). Plan filter: API-A3 (optional). Total count: API-A4.

**Legacy parity.**

| Legacy (`AdminUsersView`) | New |
|---|---|
| Card per user with 7-figure strip | Table row (same 7 figures as columns) |
| Sort select + search | Sortable headers + Sort menu + SearchField |
| Grant/Extend with presets 7/30/365 + days field, inline | Same presets in a Dialog with an end-date preview |
| `window.confirm` for grant and revoke | Dialogs |
| "View activity" link | Whole row links to detail |
| Load more | Pagination (cursor) |
| Violet "ADMIN" | Neutral Badge |

---

## 4. User detail (`/admin/users/[id]`) — the workbench

**Purpose.** Everything about one person and every support action in one place (audit 07 §9).

**Layout (≥ 1024).** Breadcrumbs Users / Asha Rao. Header: Avatar 40, name `h1`, email with copy button, Badges (Pro until…, Admin), "Joined 3 Sep 2026". Actions: **Add credits** (amber, the page's one primary), Grant/Extend Pro (secondary), Menu (Revoke Pro… danger, Copy user id, Check a flag for this user…).

Summary row: 4 StatCards — Plan, Credits left "160 / 200" (hint "Resets 12 Oct"), Total paid, AI cost. A `dl` strip below: Projects · Clips · Days active (hint "since tracking began") · Last active · Last login.

`Tabs` (underline, URL `?tab=`):

| Tab | Content |
|---|---|
| Activity | Timeline merged from sign-up, logins, projects, payments (as legacy). `ol` with mono time, label, detail. First 30, "Show all 214 events". Filter chips: All · Logins · Projects · Payments |
| Projects | DataTable: Project (title + source link, only `http(s)` linkified, `rel="noopener noreferrer"`), Status (StatusBadge), Length, Clips, Credits, AI cost, Created |
| Payments | DataTable: Submitted, Amount, Bought ("Pro, monthly" / "200 credits pack"), Status, Reviewed; row → `/admin/payments?focus=<id>` |
| Credits | DataTable: When, Change (+ emerald / − rose, with sign in text too), Balance, Reason |
| Logins | DataTable: When, Method, IP address (masked "103.21.•.•" with a "Show" toggle per table, S-4), Device ("Chrome on Windows") |
| Flags | Evaluated flags for this user: key, value, reason ("Rule r_staff", "Override", "Blocked by broll_studio"), and their overrides with Remove. API-A5. Until it exists the tab shows the **Check a flag** tool only (works today via `POST /admin/flags/{key}/evaluate {user: email}`) |
| Audit | Admin actions on this user (plan, credits, overrides, disconnects). API-A6. Hidden until it exists |

**Check a flag dialog.** Flag key combobox (from `GET /admin/flags`), result card: value On/Off, reason chain in words (shared `EvaluationResult`, DS-A5, also used in §9), "Bucket 4,312 of 10,000". Link "Open flag".

**States.** Loading: header + StatCard skeletons + table skeleton. Not found (404): admin 404 "No user with this id. They may have deleted their account." · All users. Error: InlineAlert + Try again. Empty per tab: "No projects yet." / "No payments." / "No credit activity." / "No logins recorded yet. Logins are tracked from the day tracking began." Large lists (≥ 200 projects): note "Showing the latest 200" until API-A7 paging. After any action, the detail query is refetched; toast names the result.

**360 px.** Header stacks; actions become Add credits (full width) + Menu. StatCards 2 per row. Tabs scroll horizontally (TabList overflow) — the only allowed horizontal scroll, inside its own region. Tables become cards.

**API.** `GET /admin/users/{id}/detail` → `AdminUserDetailResponse` (envelope); `PATCH /admin/users/{id}/plan`; `POST /subscription/topup` (`CreditTopupRequest`, with the user's email); `POST /admin/flags/{key}/evaluate`; `PUT /admin/flags/{key}/overrides` and `DELETE …/overrides/user/{id}?reason=` (Flags tab, needs `flags.edit`).

**Legacy parity.**

| Legacy (`AdminUserDetailView`) | New |
|---|---|
| 8 tiles | 4 StatCards + 5-item strip (same 8 facts + clips) |
| Timeline, first 30, show all | Kept + type filter |
| Projects / Logins / Payments / Credit history tables | Kept as tabs |
| No actions (read-only dossier) | Grant/extend/revoke Pro, add credits, check flag, overrides |
| IP and user agent always visible | Masked by default, per-table reveal |
| "All users" back link | Breadcrumbs |

---

## 5. Payments (`/admin/payments`) — review queue

**Purpose.** Match each UPI payment against the bank and decide in seconds, keyboard first.

**URL state.** `?status=pending|success|rejected|all&q=&focus=<id>&page=`.

**Layout (≥ 1024): list + detail.** `AdminPageHeader` "UPI payments" · "Match each amount and UTR against your bank or UPI app before approving." Toolbar: `Tabs` (pill) Pending (count) · Approved · Rejected · All (wire value `success` is labelled "Approved") · `SearchField` "Search UTR, email or amount".

- **Left (420 px):** `DataTable` with `activeId`: User (name + email, primary), Amount (₹ mono), Bought, Submitted (relative), Status (StatusBadge mapping pending→processing "To review", success→ready "Approved", rejected→failed "Rejected", failed→failed "Failed").
- **Right (fluid):** `PaymentDetail` (DS-A6): screenshot at up to 560 px tall (`object-contain`, click → full-size Dialog `lg` with zoom by native image size), Amount large mono, Bought, UTR `CopyField` (fixes P-20), user link "asha@… · 2 earlier payments" → user detail, Submitted, Reviewed by/at, Rejection reason. Footer bar (sticky): **Approve** (amber) · Reject (danger secondary) · J/K hint.

**Keyboard.** `J`/`K` next/previous row (focus moves, detail updates), `A` opens Approve, `R` opens Reject, `Enter` on a row focuses its detail, `Escape` closes dialogs. Shown in a Kbd legend under the list.

**Dialogs.**
- Approve (`Dialog sm`): "Approve ₹499 from asha@…?" · body from legacy: "UTR 4123 5678 9012." + "This gives them Pro (monthly), added on top of any time they have left." or "This adds 200 credits that never expire." · Cancel / **Approve payment**.
- Reject (`alertdialog`): "Reject this payment?" · preset Chips "UTR not found", "Amount mismatch", "Screenshot unclear" (fill the field) · `Textarea` "Reason shown to the user" (required, 3–500, `showCount`) · Cancel / Reject payment (danger, disabled until valid).

After either: the row leaves Pending (or updates in All), focus moves to the next row, toast "Approved ₹499 from asha@…" with "Open user". If the server says it was already decided (409/400): InlineAlert "Someone already reviewed this payment" and the list refetches (legacy behaviour kept).

**Screenshot freshness (fixes P-11).** The detail always comes from `GET /admin/payments/{id}` when a row becomes active (fresh signed URL, `staleTime` 5 min); an `<img onError>` triggers one refetch, then shows "The screenshot link expired. Reload it" with a button.

**States.** Loading list (8 rows) and detail (image block skeleton). Empty Pending: EmptyState success "All caught up. New UPI payments appear here." Empty search: "No payments match '4123'." · Clear search. No screenshot: neutral tile "No screenshot uploaded". Error list / error detail separately. Busy: the two footer buttons `loading`, J/K still works for reading.

**Tablet and 360 px.** < 1024: list only; tapping a row opens the detail in a right `Drawer` (full-screen sheet on phones) with the same footer. 360 px: rows are cards (User, Amount, Bought, Submitted, status); the sheet footer has Approve and Reject at 44 px.

**API.** `GET /admin/payments?status&q&limit=50&offset` → `AdminPaymentResponse[]` (raw); `GET /admin/payments/{id}`; `PATCH /admin/payments/{id}/approve`; `PATCH /admin/payments/{id}/reject` `PaymentRejectRequest {reason}`. Pending count: `GET /admin/overview`. Live arrival of new payments: API-A8 (else refetch every 60 s while visible).

**Legacy parity.**

| Legacy (`AdminPaymentsView`) | New |
|---|---|
| Tabs Pending/Success/Rejected/All (no tab semantics, A-05) | Tabs with counts on Pending; "Success" labelled "Approved" |
| Card list with 64 px thumbnail; lightbox (no dialog semantics, A-01) | List + detail with large screenshot; full-size in a real Dialog |
| UTR click-to-copy without feedback | CopyField with "Copied" |
| Inline reject pane with 3 presets | Reject dialog, same presets, same 3–500 rule |
| `window.confirm` approve with summary | Approve dialog with the same summary |
| Stale signed URLs on idle tab | Fresh on open, auto-refresh once on error |
| `PaymentStatusBadge` (red) | `StatusBadge` |
| — | Keyboard review (J/K/A/R) |

---

## 6. Credits (`/admin/credits`)

**Purpose.** Add credits by hand with a reason, and see every top-up.

**Layout.** `AdminPageHeader` "Credits" · "Add credits to a user by hand. Every top-up is logged with who made it." Two parts:

1. **Add credits** card (max 640 px): `Field` "User" — combobox (DS-A7 `UserPicker`): type an email or name, suggestions from `GET /admin/users?q=` (5 rows: name, email, current credits); a typed full email that matches no suggestion is still accepted (the server resolves it). `NumberField` "Credits" 1–100,000 with unit "credits" (fixes P-17 "minutes"). `Input` "Reason" (3–255, placeholder "Refund for failed render"). Preview line when a user is picked: "Asha has 160 credits. After this: 260." **Add credits** (amber) → confirm `Dialog` "Add 100 credits to asha@…?" · "Reason: Refund for failed render. This is logged with your name." · Cancel / Add credits. Success: InlineAlert success "Added 100 credits to asha@…. New balance: 260." (`live="status"`) and the history refetches.
2. **Top-up history**: `SearchField` "Search user" + `DataTable`: When, User (link to detail), Credits (+mono), Balance after, Reason, Added by (email, or "A removed admin" when null). Pagination cursor mode.

**Removing credits** (both directions, audit 07 §9) needs API-A9; until then the dialog title and button say "Add" only.

**States.** Form: field errors inline (invalid email, out of range, reason too short); 404 → field error "No user with that email". Submitting: button `loading` "Adding". History: loading rows, empty "No top-ups yet.", empty search, error with retry.

**360 px.** Form fields stack full width; history rows become cards (User, +Credits, When, Reason).

**API.** `POST /subscription/topup` `CreditTopupRequest {user_email, amount, reason}` → `AdminCreditTopupResponse` (raw); `GET /subscription/topups?q&limit&offset` → `AdminCreditTopupResponse[]`; `GET /admin/users?q=&limit=5` for the picker.

**Legacy parity.**

| Legacy (`AdminCreditsView`) | New |
|---|---|
| Email, Minutes, Reason, Add credits; `window.confirm` | UserPicker, Credits, Reason, preview, confirm Dialog |
| "Added 100 min … New balance: 160 min." | Same sentence in credits |
| History table with "Deleted admin" | Same columns, user links, "A removed admin" |
| Copy-pasted debounce + load more (D-01) | Shared admin list hook (DS-A8 `useAdminList`) |

---

## 7. Social (`/admin/social`)

**Purpose.** Is publishing healthy, and who is connected — without ever showing tokens.

**Layout.** `AdminPageHeader` "Social publishing" · "Watch publishing health and disconnect accounts. Tokens are never shown." Range `SegmentedControl` 1 / 7 / 30 days (URL `?days=`, default 7).

1. **Feature status** strip (E3): one row per `social_publishing*` flag — label, state chip from the flags list (On / Off / Killed / 12.5%), "Blocked by …" note; link "Change in Flags" → `/admin/flags?q=social_publishing`. Read-only.
2. **Platforms**: a Card per platform with accounts (YouTube and Instagram first; TikTok and X shown only if they have accounts or posts in the window, labelled "Not offered to users"): Active N, Needs reconnect N, Published N, Failed N, success rate as a `ProgressBar` with value text "94% posted". Platform mark is a monochrome icon; brand colour only on the mark (audit decision 6).
3. **Quotas**: StatCards "YouTube uploads today (all users)" `used / limit` with a ProgressBar, warning tone over 80%; "X spend this month" shown only when X is present.
4. **Recent failures**: `DataTable`: When, Platform, Account, User (link), Error (message + code in mono), Attempts. Empty: "No failed posts in the last 7 days."
5. **Connected accounts**: `SearchField` (debounced, no Enter needed) + `DataTable`: Account (handle/display name, platform), Audience (`formatAudience`), User (email → detail), Status (StatusBadge: active→ready "Active", needs_reconnect→failed "Needs reconnect", disconnecting→processing, disconnected→neutral), Connected since, Actions: **Force disconnect** (danger ghost) → `alertdialog` "Force-disconnect @asha_clips?" · "Their scheduled posts on this account will be cancelled and Clipnera's access is revoked. They can connect again." · Keep connected / Force disconnect. Pagination (limit 50).

**States.** Each block loads and fails on its own (overview vs accounts). Loading: skeletons (fixes P-14, empty text no longer shows before data). Accounts empty: "No connected accounts." Search empty. Disconnect pending: row button `loading` "Disconnecting"; failure toast.

**360 px.** Platform cards 1 per row; tables to cards; Force disconnect stays reachable in each card.

**API.** `GET /admin/social/overview?days` → `AdminSocialOverviewResponse` (envelope); `GET /admin/social/accounts?q&limit&offset` → `AdminAccountListResponse`; `POST /admin/social/accounts/{id}/disconnect` → `DisconnectPreviewResponse`; `GET /admin/flags` (status strip).

**Legacy parity.**

| Legacy (`AdminSocialView`) | New |
|---|---|
| Feature switches (5 `social_publishing*` flags), one-click, no names (A-02) | Read-only status strip → Flags console (owner Q6 / E3). Until the owner confirms, the strip also offers "Turn off publishing" as a link to the kill dialog of `social_publishing` |
| Platform tiles with 7 d counts | Platform cards, range 1/7/30 |
| YouTube quota, X spend | Kept as StatCards with progress |
| Recent failures list | Table |
| Accounts search on Enter, Force disconnect with `window.confirm` | Debounced search, paged table, alertdialog |
| Empty text before first load (P-14) | Skeleton first |

---

## 8. AI usage (`/admin/usage`)

**Purpose.** What AI costs per minute of video, by model and by project, and whether the director is getting better.

**Layout.** `AdminPageHeader` "AI usage" · "Tokens and dollars spent on AI models, from every call the pipeline makes." Actions: `SegmentedControl` 7 / 30 / 90 days.

1. StatCards: Spend (USD), AI calls, **Cost per source minute** (from `cost_per_minute`, weighted by `source_minutes`; replaces "Average per video (top videos)", which overstated the average — P-15), each with a Sparkline from `by_day` where it applies.
2. "AI cost per source minute" table (Tier "Pro (Claude)" / "Free (Groq)", Videos, Source minutes, Per minute) + note "Credits should earn at least 3× this per minute." Rows whose per-minute cost × 3 exceeds the credit price get a warning Badge "Below 3×" (price from `GET /subscription/plans` is not per minute; so the badge needs API-A10 and is hidden until then).
3. "By model": Model (`provider / model`), Calls, Input tokens, Output tokens, Spend.
4. "Most expensive videos": Project (title — API-A11; until then short id with copy), User (email link — API-A11; until then id linked to `/admin/users/{id}`, which fixes "raw UUID not linked"), Calls, Spend.
5. "Clip quality by director version": Version (mono), Clips, Exported, Edited, Published (as % with a thin bar). Independent loading/error: "Couldn't load clip quality. Spend above is unaffected." · Try again (legacy swallowed this error).
6. "By day": Disclosure → table.

**States.** Range loading keeps old data dimmed; empty "No AI calls in this period."; errors per block.

**360 px.** StatCards 1 per row; tables to cards (primary: model / project).

**API.** `GET /admin/usage?days` → `AdminUsageSummary` (envelope); `GET /admin/clip-quality?days` → `ClipQualityReport` (envelope).

**Legacy parity.** All five tables kept; tiles kept except "Average per video (top videos)" → "Cost per source minute" (owner to confirm the swap, it changes a visible figure); raw ids now linked; quality failure now visible.

---

## 9. Flags console (`/admin/flags`, `/admin/flags/[key]`, `/admin/config`, `/admin/audit`)

Built from [06-flags.md §10](../06-flags.md). Every endpoint it needs **exists** (`backend/feature_flags/route.py`: `/admin/flags`, `/admin/config`, `/admin/segments`, `/admin/flags/audit`, `/admin/flags/health`). Types mirror 06-flags §8.2 exactly and live in `lib/flags/types.ts` (Platform, read-only) — the console imports them and adds no copies.

**URLs.** `/admin/flags?q=&kind=&state=&stale=1&view=tree|flat`, `/admin/flags/[key]?tab=targeting|history|usage`, `/admin/config`, `/admin/config/[key]`, `/admin/audit?target_key=`. `/admin/features` → 308 `/admin/flags` inside the v2 tree (E2; `redirect()` in `app/v2/(admin)/admin/features/page.tsx`). Legacy admins still get the old page.

### 9.1 Flag list

**Layout.** `AdminPageHeader` "Feature flags" · "Who sees what, and the emergency off switch. Every change needs a reason and is logged." Meta: snapshot age when over 60 s ("Live values are 4 min old" warning tone over 300 s, from `/admin/flags/health`). Actions: secondary "Remote config" link, ghost "Audit log".

Toolbar: `SearchField` (key, label, owner; `/` focuses) · `Menu` filters Kind (Release, Ops, Experiment) and State (Off, Staff only, Rolling out, On, Killed, Default) with checked items · Chip "Needs cleanup" (stale) · `SegmentedControl` Tree / Flat.

`DataTable` (compact):

| Column | Render |
|---|---|
| Flag (primary) | label `label` 600, key below in mono `caption` with indent per depth in Tree view (16 px per level, any depth) |
| State | Badge: `Off` neutral · `Staff only` info · `12.5%` accent · `On` success · `Killed` danger · `On by default` neutral — text, not colour only |
| Blocked by | "Blocked by `broll_studio`" warning caption when `blocked_by` is set |
| Owner | caption |
| Last change | "2 h ago by a@…" |
| Flags | Badges "Stale", "3 overrides", kind |

Row → detail. **No inline toggles** (no accidental flips; fixes A-02 and the one-click flip).

**States** (06-flags §10.4): loading skeleton rows; load failed InlineAlert + Retry; empty search "No flags match 'reel'." + Clear filters; snapshot stale header warning; 360 px rows → cards (label, state badge, blocked note).

### 9.2 Flag detail

**Header.** Breadcrumbs Flags / label. Title = label; key `CopyField` mono; Badges kind, owner, "Created 3 Oct 2026 · expires 31 Mar 2027"; description; links to parent, children and `requires` keys.

**Banners.** Killed: danger `Banner` "Killed by a@… on 4 Oct, 14:02 — 'Veo outage, cost spike'" + **Restore**. Blocked: warning "Off for everyone because `broll_studio` is off" + link. Stale: warning "Past its expiry — remove the flag from code or extend it." No permission (403 or API-A1): neutral "You can view flags but not change them", every control read-only with a lock icon.

**Actions** (top right): **Kill** (danger; the page's amber action is Save in the save bar, so Kill is never amber) · "Check a user" (secondary). Kill `alertdialog` (06 §10.4): impact "Turns off for everyone, including 3 dependent flags: …", reason `Textarea` (10–500), "Type `broll_studio` to confirm" `Input`, **Kill feature** (danger, disabled until both valid). Restore: same dialog without typing.

**Tabs.**

| Tab | Content |
|---|---|
| Targeting | (1) `Switch` "Targeting on" (stored `enabled`). (2) **Overrides**: DataTable Subject (email/workspace label), Serve On/Off, Reason, Expires, Added by, Remove (`IconButton` "Remove override for asha@…"); "Add override" → Dialog: `UserPicker` (DS-A7) or workspace id, Serve SegmentedControl On/Off, expiry date (optional), reason. (3) **Rules**: ordered list (DS-A9 `RuleList`); each rule card: description input, condition chips "Segment is staff" / "Plan is Pro" / "User is …" / "Workspace is …" built by a `Menu`, rule % `Slider` + `NumberField`, Serve On/Off; reorder by **Move up / Move down** buttons (keyboard and touch) and drag on pointer; "Add rule" Menu with presets "Staff only", "Pro first", "Empty rule"; 20-rule cap message. (4) **Everyone else**: rollout `Slider` with stops 0 · 1 · 10 · 50 · 100 and a `NumberField` to 0.01% (stored as bps); line "≈ N of M people active last week" from `exposures_7d` (hidden when empty — never a guess). (5) **Save bar** (DS-A10, sticky bottom while dirty): plain-language diff ("Rollout 10% → 50%; added rule 'Pro first'"), reason field (10–500), Discard, **Save** (amber). Ramping a `release` flag to 100% adds the line "This turns it on for everyone and notifies every admin." |
| History | Timeline from `GET /admin/flags/{key}/history?cursor=`: who, when, action in words, reason, `Disclosure` with before/after diff (`DiffList`, DS-A11, key-by-key). "Load more" cursor. Empty "No changes since this flag was created." |
| Usage | 7-day on/off exposure by value from `exposures_7d`; "Where it's read" = registry definition line (shown when the API sends it; otherwise hidden) |

**Check a user** dialog: email or id (UserPicker) and optional workspace id → `EvaluationResult` (DS-A5): value, reason in words ("Off — blocked by `broll_studio` (killed)"), rule id, bucket "4,312 of 10,000".

**States.** Saving: Save `loading`, form read-only, other pages usable. Saved: toast "Saved — live for everyone within seconds" + "View in history". 409 `FLAG_VERSION_CONFLICT`: Dialog "Someone changed this flag while you were editing" with their diff (refetched detail vs. your base) and two choices "Load their version" / "Reapply my changes on top". 422 `CONFIG_INVALID`: field-level message from `fields`. Unknown key: admin 404 "No flag called 'x'. It may have been removed from code." Leave with unsaved changes: browser `beforeunload` + in-app `alertdialog` "Discard changes to this flag?".

**360 px.** Kill/Restore and Check a user work (on-call). Rule builder stacks fields; Slider full width; save bar becomes a bottom sheet footer with reason + Save at 44 px.

**API.** `GET /admin/flags`, `GET/PATCH /admin/flags/{key}` (`AdminFlagUpdateRequest` with `expected_version`), `POST …/kill` (`AdminFlagKillRequest {reason, confirm_key}`), `POST …/unkill`, `PUT …/overrides`, `DELETE …/overrides/{subject_type}/{subject_id}?reason=`, `POST …/evaluate`, `GET …/history`, `GET /admin/flags/health`, `GET /admin/segments` (segment chip choices). After any write: invalidate list + detail, and `config.changed` refetches the admin's own bootstrap.

### 9.3 Remote config (`/admin/config`, `/admin/config/[key]`)

List `DataTable`: Key/label (primary), Current default (unit-formatted: bytes as GB, seconds as minutes, ratio as %, credits in mono), Badge "Shown on pricing" (`plan_promise`), overrides/rules count, Last change. Detail: typed editor (NumberField with unit and min/max inline errors, Menu for enums, Switch for bool, Input for string); **By plan** table (Free | Pro | others from `by_plan`) with "from rule" / "default" captions; rules and overrides as §9.2 (serve is a typed value); same save bar; plan-promise keys get a second confirm "This changes what customers are promised on the pricing page." History uses `GET /admin/flags/audit?target_key=`. States as §9.2.

API: `GET /admin/config`, `GET/PATCH /admin/config/{key}` (`AdminConfigUpdateRequest`), `PUT/DELETE /admin/config/{key}/overrides…`.

### 9.4 Audit log and segments (`/admin/audit`)

`Tabs` "Changes" · "Segments".
- **Changes**: `GET /admin/flags/audit?cursor=&target_key=` → table When, Who, Action in words ("Killed", "Changed targeting", "Added override", "Legacy switch"), Target (link), Reason, expandable diff. Filter by target key (SearchField). Today this covers flags, config and segments only; plan, payment, credit and B-roll actions join when the shared `admin_audit_log` exists (API-A6) — the page title stays "Audit log" and the caption says what it covers: "Flag, config and segment changes. Other admin actions appear here once they are logged."
- **Segments**: `GET /admin/segments` → cards (key, description, N users, domains, roles); Edit → Dialog: add/remove users (UserPicker multi), email domains, roles, reason; `PATCH /admin/segments/{key}` with `expected_version`.

**Legacy parity (§9 as a whole).**

| Legacy (`AdminFeaturesView`, `FeatureSwitches`, switches in `AdminSocialView`) | New |
|---|---|
| One card of switches, child flags indented 24 px, one level | Searchable tree at any depth, filters, state chips |
| Click flips instantly for everyone, no confirm, no name (A-02) | No inline flip; targeting saved with reason and diff |
| "On, but inactive while the main switch is off." | "Blocked by `key`" in list and banner |
| All switches lock while one saves | Only the edited flag's form is read-only |
| No history, `updated_by` never shown | History tab, audit log, last-change column |
| Social flags on a separate page by key prefix (D-08) | One console; Social shows read-only status (§7) |
| — | Kill switch, overrides, rules, percentage, remote config, segments, check a user |

---

## 10. Content: B-roll curation and Music

### 10.1 B-roll curation (`/admin/broll`)

Target design: [05-broll §3.6](../05-broll.md). Today's backend has list, status and ingest only, so this spec ships in **two steps**: v1 against real routes now, and the remaining tabs as their endpoints land (each tab is hidden until its endpoint exists; no fake tabs).

**Layout.** `AdminPageHeader` "B-roll library" · "Licensed shots used in clip cutaways and reels. Users see them only inside their own work." (fixes P-19 wording). `Tabs`: **Library** (v1) · **Ingest** (v1) · Review queue (05 §7.5, hidden) · Upload (hidden) · Collections (hidden) · Moderation (hidden) · Takedowns (hidden).

**Library (v1).** Toolbar: `SearchField` "Search titles, captions and tags" · status `Menu` (All, Live, Ingesting, Blocked, Taken down, Failed — adds `ingesting`, fixes P-18) · `SegmentedControl` Grid / Table · count "1,204 shots" (mono, from `total`).
- **Grid**: `MediaGrid aspect="9:16"` of `VideoThumb` (poster `thumb_url`, `previewSrc` = `proxy_url`, hover/focus preview after 150 ms, never under reduced motion; tap on touch opens the drawer instead of playing — fixes A-09), status Badge top-left, duration bottom-right. Title as the card link → drawer. 2 / 3 / 5 / 6 columns at phone / sm / lg / 2xl.
- **Table**: Shot (thumb 40 + title, primary), Status, Source, Licence, Size (W×H, orientation), Duration, Quality (mono), Added.
- `Pagination` numbered (40 per page; `pageCount` from `total`). Selection and bulk bar arrive with `POST /admin/broll/assets/bulk` (hidden in v1).

**Asset drawer** (right `Drawer` `lg`; full-screen sheet on phones; URL `?asset=<id>`): player on `stage` (proxy, controls), title, Badges status/kind/orientation, `dl` of every field in `BrollAssetResponse` (source + provider link with `http(s)` check and `rel="noopener noreferrer"` — fixes S-9, source id, tags as chips, W×H, duration, quality score, licence code, attribution text with CopyField, status reason, added). Actions by status (footer): Live → **Block…** / **Take down…** (danger); Blocked or Taken down → **Restore…**; Ingesting/Failed → none (no "Restore" on unusable assets, P-18). Each opens a Dialog: reason picker chips ("Licence complaint", "Low quality", "Wrong content", "Shows people without release", "Other") + note (≤ 500) → `reason`. Full licence record, usage and history (05 §3.6) need API-B1/B2 and show "Not available yet" rows hidden, not faked.

**Ingest (v1).** Form card: `Input` "Topic" (2–200, "city at night"), source `Checkbox`es (the providers the backend accepts, default all), `NumberField` "Shots per source" 1–20 (default 5). **Start ingest** (amber) → toast "Ingest queued for 'city at night'. New shots appear in Library as they finish." Below, "Recent ingests" needs API-B3 (runs table); until then a caption "Ingests run in the background. Filter Library by Ingesting to watch them."

**States.** Loading: skeleton tiles at 9:16 / table rows. Empty library: "No shots yet. Start an ingest to fill the library." Empty search: "No shots match 'x'." + Clear. Error with Retry (never the empty message first, P-14). Status change pending: drawer footer `loading`; success toast "Blocked. It left search immediately."; error toast and refetch.

**360 px.** 2-column grid; filters in a bottom sheet; drawer is full screen with actions at 44 px; Ingest form stacks.

**API.** `GET /admin/broll/assets?q&status&limit=40&offset` → `BrollAssetListResponse {items,total}`; `POST /admin/broll/assets/{id}/status` `BrollStatusRequest {status: live|blocked|taken_down, reason?}`; `POST /admin/broll/ingest` `BrollIngestRequest {query, per_source, sources?}`. Platform-only filter (user-owned assets mixed in today): API-B4.

**Legacy parity.**

| Legacy (`AdminBrollView`) | New |
|---|---|
| Ingest bar, fixed `per_source: 5` | Ingest tab with sources and per-source count |
| Search, status select (missing `ingesting`) | SearchField + status Menu incl. Ingesting |
| 9:16 grid 2/3/5, hover-only video | Grid or table, hover/focus preview, tap opens drawer |
| Block / Take down via `window.prompt`; Restore on any non-live | Reason dialog; Restore only on blocked/taken down |
| Previous/Next | Numbered pagination |
| Source link `rel="noreferrer"` without scheme check | Checked, `noopener noreferrer` |

### 10.2 Music (`/admin/music`) — new page, no legacy UI

**Purpose.** The licensed music library behind footage reels (`/admin/music` API exists with no UI, audit 07 §1).

**Layout.** `AdminPageHeader` "Music" · "Free-licence tracks the reel editor can pick. Each needs a licence that allows commercial use and editing." Action **Add track** (amber). `DataTable`: Track (title, artist; primary), Mood, Energy (mono 0–1), BPM, Duration (`TimeCode`), Licence (Badge + link to `licence_url`), Used by (mono), Status (Live success / Pulled neutral), Actions: Play (`IconButton`, one `<audio>` at a time, inline transport), Pull… / Put back live (status dialog), Copy credit text. Filter chips by mood; SearchField (client-side; the list is small and unpaged).

**Add track** `Dialog lg`: `FileDropzone` (audio; single), Title, Artist, Source (Menu), Source URL, Source id, Licence (Menu), Mood (Menu), Energy `Slider` 0–1, BPM `NumberField` 40–240 (optional), Credit text (≤ 500; required hint when the licence needs credit), Checkboxes "Allows commercial use", "Allows editing" (both required; explain "Clipnera refuses tracks without both"). Server 422/400 messages map to fields. Choice lists mirror `edit_engine/music.py` until API-B5 exposes them.

**States.** Loading rows; empty "No tracks yet. Add a free-licence track to give reels music."; error retry; upload `loading` with "Uploading track"; pull confirm `alertdialog` "Pull this track? It stops being picked, and reels that haven't rendered yet drop it."

**360 px.** Cards with play, status and actions; Add track dialog becomes a sheet.

**API.** `GET /admin/music` → `MusicTrackResponse[]`; `POST /admin/music` multipart (fields as the route's `Form` params); `POST /admin/music/{id}/status` `MusicStatusRequest`.

---

## 11. Publish: the Scheduler page (`/dashboard/scheduler`)

**Purpose.** See what goes out when, fix what failed, and start a new post. Nav label **Publish** (07 §5.2; shown only when `social_publishing` is on); page URL unchanged. Hero moment: a week where every post shows its clip poster and platform mark.

**Flag.** `new_ui_export` (route); content needs `social_publishing`. Off → in-shell state "Publishing isn't on for your account yet" · "It's being rolled out in stages. Until then you can download clips and post them yourself." · Go to Projects.

**Layout (≥ 1024, Comfortable).**
- Header: `h1` "Publish" · line "Posts to YouTube Shorts and Instagram Reels, now or on a schedule. Times are in India (IST)." where the zone is a link-button opening a timezone `Menu` (saved per browser with `usePersistentState`; API-S5 to save per account). Actions: **New post** (amber) → `/dashboard/scheduler/new`.
- `Tabs` (underline, `?tab=`): **Upcoming** · **Posted** · **Needs attention** (count of failed + accounts needing reconnect) · Performance (only when E1's flag is on, §17).
- Main column + right rail (`w-80`, 320 px):
  - **Upcoming**: toolbar `SegmentedControl` Week / Month / List, ‹ Today › and the range label ("6 – 12 Oct"). Week view (DS-P1 `WeekGrid`): 7 day columns; each post is a **post chip** (DS-P2): 9:16 mini poster (32×56), time in mono, platform mark (monochrome icon), status by icon + text for screen readers (scheduled sky, publishing amber live dot, published emerald, failed rose, cancelled struck neutral). Today's column has an `accent-border` top edge. Empty day: nothing (no "—"). Month view: day cells with up to 3 chips + "+2". List view: `DataTable` grouped by day.
  - **Posted**: `DataTable` newest first: Clip (poster + title), Platform/account, Posted at, Status, "View post" link (external, says so to screen readers).
  - **Needs attention**: failed posts with the server's error message in rose, attempts, and actions **Post again** (opens the composer pre-filled with the same clip, account, caption and options — real today, it creates a new post), Remove from list is not offered (no API); plus accounts that need reconnecting, each with **Reconnect**.
  - **Right rail "Accounts"**: one row per connected account (§13 `AccountRow`), connection limit "1 of 2 accounts", "Auto-disconnects 11 Oct" caption, and **Connect YouTube** / **Connect Instagram** buttons when allowed.
- **Post detail** (`Drawer` right, `md`; sheet on phones; URL `?post=<id>`): poster player, account, caption (read-only), platform options in words ("Unlisted · Not made for kids"), scheduled time in the chosen zone and in UTC on hover, status with history (attempts, error), actions: **Cancel post** (scheduled only; `alertdialog` "Cancel this post? It won't go out. The clip stays in your project.") · View post (published) · Post again (failed/cancelled). Reschedule and edit need API-S2; hidden until then.

**Tablet.** Rail moves under the calendar as a collapsible "Accounts" `Disclosure`. **360 px.** Week view becomes a vertical agenda (one day per section, chips as full-width rows) — no 7-column horizontal scroller (fixes P-S11 phone sideways scroll). Tabs scroll in their own region. New post is the page's amber button full width under the header.

**States.** Loading: calendar skeleton (7 columns of 2 chips), rail skeleton. Error: "I couldn't load your posts. Nothing scheduled has changed; they'll still go out on time." · Try again (fixes P-S8 empty-queue-on-error). Empty (no posts ever): EmptyState "Nothing scheduled yet" · "Pick a clip and choose when it goes out. Posts appear here with their status." · New post. No accounts: rail shows "Connect YouTube or Instagram to post from Clipnera" + buttons; New post still opens (the composer explains). Partial: posts ok, connections failed → rail InlineAlert with retry only. Offline: last data kept, writes disabled with reason. Plan cannot schedule (`can_schedule=false`): Upcoming shows "Scheduling is part of Pro. You can still publish right away." + See plans (ghost).

**Live updates.** No post events exist (API-S1). Until then: refetch posts every 15 s **only while any post is `publishing`** or a scheduled post is due within 10 minutes, paused when hidden, refetch on focus (fixes P-S8 days-long polling).

**API.** `GET /social/posts?status=&limit=100&offset=` → `PostListResponse`; range filter for Month view needs API-S4 (until then fetch up to 100 and page); `POST /social/posts/{id}/cancel` → `PostResponse`; `GET /social/connections` → `ConnectionsResponse`.

**Legacy parity.**

| Legacy (`SocialSchedulerView`, `PostCalendar`, `ScheduledPostsQueue`) | New |
|---|---|
| Timezone pill, six zones, not saved | Timezone menu in the header line, saved per browser |
| 7-day calendar, inert chips, colour-only status | Week / Month / List; focusable chips with poster, icon + text status, open a detail drawer |
| "Suggested times" (SAMPLE DATA), TikTok/X | **Removed** (E5, E4) |
| Compose card inline on the page | Separate composer page (E6) |
| "Queue" listing every status, cap 50, cancel without confirm | Upcoming / Posted / Needs attention tabs, paged, cancel with confirm |
| Failed posts: no retry | "Post again" pre-filled |
| Cancelled: no re-queue | "Post again" |
| Connections only in Settings | Accounts rail here + Settings (shared components) |
| Polls every 15 s while anything is scheduled | Polls only around publishing, pauses when hidden |

---

## 12. Publish: the Composer (`/dashboard/scheduler/new?clip=<id>&account=<id>&from_post=<id>`)

**Purpose.** One clip, chosen accounts, captions and the rules each platform enforces, then publish now or schedule. Carries over every provider rule (audit 00 §10).

**Entry points.** "New post" (Publish), Schedule on a clip card / Home "Top clips", the render card's Schedule action (07 §6.6), "Post again". Query params pre-fill; unknown ids show an inline error and an empty picker.

**Layout (≥ 1024).** Two columns in the content area: **left 360 px** sticky preview on `stage` (9:16 clip player, title, duration, score badge, "Change clip"); **right** the form (max 640 px). Header: Breadcrumbs Publish / New post; Cancel (ghost, back).

Form sections:
1. **Clip** — if none: "Choose a clip" opens `ClipPicker` (DS-P3, Dialog `lg`): step 1 projects (`GET /clips/projects`, search, ready projects first), step 2 that project's ready clips as a `MediaGrid` of quote-style tiles (title, duration, score). A finished reel cannot be chosen until API-S3 (E7).
2. **Where** — account toggle cards (`ChoiceCard`-like, multi-select, `aria-pressed`): avatar, platform mark, handle, audience, status. Accounts that are `needs_reconnect` or expiring within 24 h **show** with a warning and a Reconnect button instead of vanishing (fixes P-S4); TikTok/X accounts show "Not supported in Clipnera" disabled (E4); platforms unavailable or not in plan show the reason ("Instagram is in review by Meta", "Pro only" → upgrade). No accounts: inline card "Connect YouTube or Instagram to post from here" + Connect buttons (§13; returns here).
3. **Caption** — base `Textarea` (prefilled from the clip title only — no template paragraph, no fake hashtags), `showCount`. "Write a caption" `PromptBar docked` mini ("Hinglish, 3 hashtags, mention the guest") needs API-S6 and is hidden until it exists.
4. **Per account** — one `Card` per chosen account (`Disclosure`, open by default), header "YouTube Shorts · @asha" + count `92 / 100` for the title or caption against `caption_max_chars` (red and **blocking** over the limit; if the limit is missing, no counter — fixes P-S6):
   - Caption override `Textarea` (starts from the base; "Use the main caption" resets).
   - **YouTube:** Title `Input` (required, ≤ 100, no `<`/`>` — validated client-side with the same message the server gives), Privacy `SegmentedControl` Public / Unlisted / Private (default Public), **Made for kids?** radio Yes / No with **no default** (required; YouTube requires the creator to answer).
   - **Instagram:** `Switch` "Also share to the main feed" (default on); **Reels cover** (`CoverPicker`, DS-P4, ported from `ReelsCoverPicker` logic: "Let Instagram choose" / "Pick a frame", three crops Reel 9:16 · Feed 4:5 · Profile grid 3:4, Slider with mono time, hint "Keep faces and text inside the centre of the frame: the profile grid crops the top and bottom." Unique ids per account (fixes P-S14 duplicate id), value clamped to the clip duration, disabled with "Available once the clip has finished rendering" when no rendered URL).
   - TikTok options (privacy with no preselection, comments/duet/stitch, brand disclosure, consent line) are **kept in code** behind the `social_publishing.tiktok` flag only, so the rules survive if the owner re-enables TikTok (E4); hidden while that flag is off.
5. **When** — `SegmentedControl` Publish now / Schedule (Schedule locked with "Pro" and opens the upgrade dialog when `can_schedule=false`). Schedule: date and time fields (native `date` + `time` inputs with labels) in the chosen zone, `min` = now + 5 min, `max` = now + `max_schedule_days`; hint "Up to 30 days ahead · up to 10 posts a day" from `ConnectionsResponse`; changing the zone keeps the same **instant** and re-displays it (fixes P-S7).
6. **Footer** (sticky): summary "2 accounts · Tue 7 Oct, 7:30 PM IST" and **Schedule to 2 accounts** / **Publish now to 2 accounts** (amber). Disabled with the first missing thing named ("Answer 'Made for kids?' for @asha").

**Submit.** One idempotency key per *attempt* (regenerated after success or after any field change — fixes P-S15). Success: toast "Scheduled to 2 accounts for Tue 7 Oct, 7:30 PM" + "View in Publish"; navigate to `/dashboard/scheduler?tab=upcoming` with the new posts highlighted. **All form state resets per clip**: changing clip clears per-account options and captions (fixes P-S2, P-S3). Server 422 problems map to the account card that caused them.

**States.** Loading connections: skeleton account cards (never the endless "Loading connected accounts…", fixes P-S1). Connections failed: InlineAlert "I couldn't load your connected accounts. Nothing has been posted." · Try again. Clip not found / not ready. Submitting: footer `loading` "Scheduling". Partial success (some targets failed validation server-side): the response lists created posts; the form keeps the failed accounts with their error. Leave with changes: confirm. Offline: submit disabled.

**360 px.** One column: preview collapses to a 72 px strip (poster, title, Change); account cards full width; footer fixed above the safe area with the summary on one line and the button at 44 px. Cover picker shows one crop at a time with a `SegmentedControl` Reel / Feed / Grid.

**API.** `GET /social/connections`; `POST /social/posts` `CreatePostsRequest {clip_id, targets: [{account_id, caption, options}], scheduled_at?, idempotency_key}` → `PostListResponse`; `GET /clips/projects`, `GET /clips/{project_id}`, `GET /clips/item/{clip_id}` (untyped today — API-X2); `GET /social/accounts/{id}/tiktok-creator-info` only if TikTok returns. Options shape per provider: YouTube `{title, privacy_status, made_for_kids}`, Instagram `{share_to_feed, thumb_offset?}` (ms).

**Legacy parity.**

| Legacy (`PublishComposer`, `PlatformOptions`, `ReelsCoverPicker`, compose card) | New |
|---|---|
| Clip dropdown from the open project only | ClipPicker across projects |
| Hook ideas (fake), "Refresh ideas", "+41%" | **Removed** (E5); AI caption only when real (API-S6) |
| Hashtag chips (fake) | **Removed** (E5) |
| Account chips without pressed state; expired accounts silently hidden | Toggle cards with state; expired shown with Reconnect |
| Per-account caption + count (non-blocking, "N/undefined") | Blocking count; no counter without a limit |
| YouTube title/privacy/made-for-kids; Instagram feed + cover; TikTok rules | All kept (TikTok behind its flag) |
| Native datetime without label, past times allowed | Labelled date/time with min/max and plan limits |
| Stale options/caption across clips | Reset per clip |
| Spins forever if connections fail | Error with retry |

---

## 13. Publish: connect flows and account components

**Purpose.** Connect, reconnect and disconnect YouTube and Instagram from wherever the person is, and come back there.

**Components (Area 8, exported from `components/publish/index.ts` for Area 9's Settings → Connections):**
- `AccountRow` (DS-P5): Avatar, platform mark, handle/display name, audience, status Badge (Active / Expiring 11 Oct / Needs reconnect / Disconnecting), caption "Auto-disconnects 11 Oct, 9:00 PM. Reconnect to keep posting for 7 more days." Actions: Reconnect (secondary; amber only when it is the page's one action) and Disconnect (`Menu`).
- `ConnectButton`: "Connect YouTube" / "Connect Instagram"; states: default, "Opening YouTube" (`loading`), Pro only (opens upgrade), at limit ("You've connected 2 of 2 accounts"), unavailable ("Instagram is in review by Meta" from `pending_review_note`). A second account on the same platform is allowed when `max_accounts` allows (P-S13, owner to confirm).
- `DisconnectDialog` (`alertdialog`, opened next to the row, focus moved in — fixes P-S17): fetches `GET /social/accounts/{id}/disconnect-preview` → "Disconnect @asha? 2 scheduled posts will be cancelled. Clipnera's access is revoked and its stored tokens deleted." · Keep connected / Disconnect.

**Flow.** Click Connect → before redirect, store `cn_connect_return = {path, ts}` in `sessionStorage` (the composer stores its draft too) → `POST /social/oauth/{platform}/start` → `authorize_url` → platform → back to `/dashboard/connect/[platform]` (path registered with Google/Meta; **never moved**). The callback page is legacy and frozen and sends people to Settings. Two options:
- **Preferred (RQ-1):** Platform adds `/dashboard/connect/*` to the `new_ui_export` rewrite. The URL, query and `Referrer-Policy: no-referrer` header are unchanged by a rewrite; the v2 callback (`app/v2/(app)/dashboard/connect/[platform]/page.tsx`, Area 8) runs the same code exchange, then returns to `cn_connect_return.path` (if under 30 min old and same-origin) with toast "YouTube connected as @asha", else to Settings → Connections.
- **Fallback:** keep the legacy callback; Area 9's `/dashboard/settings/connections` reads `cn_connect_return` and shows a Banner "Connected. Go back to your post" with a link. Works without any shared-file change.

**Callback page states (v2).** Working: centred card with `Spinner` (the one allowed use) "Connecting YouTube". Cancelled at the platform: "The connection was cancelled. Nothing changed." · Back to where you were. Invalid link: "This connection link is invalid or has expired. Start again from Publish." Exchange failed: server message + Try again (restarts the flow). Signed out: "Sign in, then connect again. The link from YouTube can only be used once." · Sign in (the code is single-use, so it is not carried through sign-in). TikTok/X callbacks: "Clipnera no longer connects TikTok/X accounts."

**API.** `POST /social/oauth/{platform}/start` → `ConnectStartResponse`; `POST /social/oauth/{platform}/callback` `{code, state}` → `ConnectedAccountResponse`; `GET /social/accounts/{id}/disconnect-preview`; `DELETE /social/accounts/{id}`; `GET /social/connections`.

**Legacy parity.** `ConnectedPlatformsPanel` status model (active / needs reconnect / disconnecting / expiring soon), plan lock, limit, inline confirm → kept as components, confirm becomes a dialog, platform gradients become monochrome marks; callback returns to the starting page instead of Settings (P-S9) and confirms success.

---

## 14. Share page (`/s/[shareId]`) — new, public

**Purpose.** A clean watch page for one clip or reel that anyone with the link can open without signing in (Cardboard/Lovable share pattern). Started from the render card's **Copy link** (07 §6.6) and the reel board.

**Status: NEEDS-BACKEND end to end** (API-SH1–SH3). Built against a typed stub in `lib/api/share/` and gated by a new release flag `share_links` (public, client; Platform/backend registry request RQ-4). With the flag off, `/s/*` returns the branded 404.

**Route.** `app/(marketing)/s/[shareId]/page.tsx` (frontend.md §8.4, Area 8). New URL, so no middleware rewrite and no legacy conflict. Server component: `generateMetadata` fetches the public share (auth optional) for `<title>`, description and a **static OG image** (the poster, 1200×630 letterboxed on `stage`); `robots: noindex` unless the owner made it listed (API-SH1 `listed`).

**Layout.** Minimal marketing chrome: 48 px header with `Wordmark` (link to `/`) and "Make clips like this" ghost link (to `/`); no footer links except Privacy and Terms. Body centred, max 480 px on phones and 960 px on desktop:
- Desktop ≥ 1024: player left (9:16, up to 80 svh tall, on `stage`, `rounded-cn-lg`, `.cn-media-edge`), details right (title `title`, "From Asha Rao's channel" when the owner shares a name, duration mono, posted date; actions **Download** (only when `allow_download`; amber, the page's one action) and Copy link (secondary)).
- Phone: player full width (max 70 svh), details below, Download full width 44 px.
- Player: native controls via the shared VideoPlayer chrome when it exists (DS list), HLS when `hls_url` (Safari native; other browsers through MSE requires `hls.js`, not installed — RQ-5; until then the progressive `mp4_url`). Captions are burned in, so no track. No autoplay with sound; muted autoplay off under reduced motion and Save-Data.

**States.** Loading: server-rendered, so only the video area shows a poster then the player. Not found / revoked: "This link doesn't work any more. The person who shared it may have turned it off." · Go to Clipnera. Expired: "This link expired on 12 Oct." Processing (`status: preparing`): "Still preparing this video. Try again in a minute." + Refresh. Media error: "The video didn't load. Check your connection and try again." Rate limited (429): "Too many views from this network right now. Try again shortly." Flag off: 404.

**Owner side (not a page).** Share settings popover on the render card and reel board (Area 8 `components/share/ShareMenu.tsx`): Copy link · Allow download Switch · Turn off link (`alertdialog`). Uses API-SH2.

**API (all NEEDS-BACKEND).** API-SH1 `GET /public/shares/{share_id}` (no auth, rate limited) → `{share_id, kind: "clip"|"reel"|"edit", title, owner_display_name: str|null, duration_s, poster_url, hls_url: str|null, mp4_url: str|null, status: "ready"|"preparing", allow_download, listed, created_at, expires_at: datetime|null}`. API-SH2 `POST /shares {kind, target_id, allow_download, expires_at?}` → same shape + `url`; `PATCH /shares/{id}`; `DELETE /shares/{id}`; `GET /shares?target_id=`. API-SH3 view counting is **not** requested (no fake view counts).

**Legacy parity.** None (new). Audit 00: export download is the only way to share today.

---

## 15. Reels: list and create (`/dashboard/reels`)

**Placement.** 07 §5.2 folds Reels into **Projects** as a tab. The URL `/dashboard/reels` is kept and routed by `new_ui_reels`. The page renders the Projects header with a two-item tab strip of **links** — "Videos" (`/dashboard/projects`, Area 3) and "Reels" (this page, `aria-current="page"`). Area 3 adds the mirror link on its page (request RQ-6). No shared component crosses the areas.

**Flags.** Route: `new_ui_reels`. Content: `broll_studio.reels` (image reels), `broll_studio.reels.footage` (footage reels). Both off → in-shell "Reels aren't on for your account yet" state. Footage off → only the photo mode shows, and the copy says so; the title never flips after load because flags come from bootstrap before render (fixes P-R3).

**Purpose.** Hand Clipnera raw clips (or photos and a script), say what it should feel like, get a planned reel you can change for free before spending credits. Hero moment (07 §7): B-roll results say where they landed, with Swap right on the card (§16.1).

**Layout (≥ 1024, Comfortable).**
1. Header "Projects" + tab links; action none (the composer below owns the amber action).
2. **Make a reel** composer card (max 768 px, centred, `surface-raised`, `rounded-cn-xl`):
   - `SegmentedControl` "From my footage" / "From photos and a script".
   - Footage mode: `PromptBar` (docked size) placeholder "Drop your raw videos and photos, then say what it should feel like" with the paperclip / drop target; dropped files become `UploadProgressItem` rows above the bar (thumbnail, name, duration in mono, remove) and a meter line "3 files · 1:42 of 5:00" (rose and blocking when over, with the reason in words, not colour only). The prompt text maps to `intent` (≤ 300).
   - `Disclosure` "Options" (summary "Auto length · English · Bold captions"): Length `Chip`s Auto / 15 / 30 / 45 / 60 / 90 s (locked above `max_output_seconds` with "Pro" and opening the upgrade dialog on click — fixes P-R24), Script `Textarea` + "How should I use it?" Menu (Decide for me, I say this in the video, Read it as a voiceover, Show it as on-screen text, Just use it as direction), Voiceover file, Language Menu (English, Hindi, Telugu, Hinglish, Tenglish), Captions Menu (styles the plan allows), Title (optional, "I'll name it from your footage"), Switch "Render as soon as the plan is ready" (autopilot).
   - Photos mode: Title, "Write it for me" / "My own script" SegmentedControl + Textarea, Language, Style (Clean, Bold, Neon, Warm), photos `FileDropzone` ("2 of 5"; extra or wrong-type files are **reported**, not silently dropped — fixes the audit's silent filter), voiceover (optional).
   - Footer line (real numbers only): "Planning and previews are free. About 24 credits when you render · you have 160." (estimate from the server: API-R5; until then the client estimate with the word "about" and the source noted in code) and **Make the plan** (amber) / **Build scene board** (photos).
3. **Your reels** — `MediaGrid aspect="9:16"`: `VideoThumb` (cover when there is one; footage reels without a cover show a neutral `surface-sunken` tile with the title, not an amber glow — fixes P-R23 until API-R3), StatusBadge (Draft, Planning, Plan ready, Rendering, Ready, Failed), kind caption "Footage" / "Photos", duration, title link, relative time. Sorted newest first.

**Create flow (footage).** `POST /edits` → `POST /edits/{id}/sources/init` → resumable upload per file (reuse `lib/upload/` from Area 7 when published; until then the legacy XHR logic ported with per-file progress) → `POST /edits/{id}/sources/complete` → `POST /edits/{id}/analyze` → navigate to the board. If any step after create fails, the board opens on the **draft** with "Your files didn't all upload. Add them again or remove the missing ones." and Retry — no second reel on retry (fixes P-R5, P-R6).

**States.** List loading (8 tiles), list error "I couldn't load your reels. They're safe." + Try again (fixes P-R4 — no fake "No reels yet"), empty "No reels yet · Your reels show up here with their cover and status.", limits failed to load: the meter says "I couldn't check your plan limits; I'll check when you start" and the server enforces, uploading (per file progress, button "Uploading 42%"), over limit, rejected file (message per file), offline.

**360 px.** Composer full width; mode control full width; Options open as a bottom sheet; grid 2 columns; the amber button full width at 44 px.

**API.** `GET /reels` → `ReelSummary[]`, `GET /edits` → `EditSummary[]` (only when footage flag on), `GET /edits/limits` → `EditLimitsResponse`, `POST /edits` `EditCreateRequest`, `POST /edits/{id}/sources/init|complete`, `POST /edits/{id}/analyze`; photos: `POST /reels` `ReelCreateRequest`, `POST /reels/{id}/assets/init|complete`, `POST /reels/{id}/plan`. A merged, paged list: API-R6 (today two calls, merged and sorted client-side).

**Legacy parity.**

| Legacy (`ReelsView`, `NewReelForm`, `FootageReelForm`) | New |
|---|---|
| Two-column page: 420 px form + grid | Composer card above the grid; Reels as a Projects tab |
| "Edit my footage" / "Build from images" switch | "From my footage" / "From photos and a script" |
| All footage-form fields (title, files, length chips, script + mode, voiceover, feel, language, captions, autopilot) | All kept; "feel" is the prompt text; the rest under Options |
| Per-file progress, limits, duration probing | Kept (logic ported) |
| Silent drop of extra / wrong files | Reported per file |
| Amber-glow title tiles for footage reels | Neutral title tile until covers exist |
| List errors shown as "No reels yet" | Real error state |
| Card is one button, no actions | Same (rename/delete need API-R4) |

---

## 16. Reel boards

### 16.1 Footage reel board (`/dashboard/reels/footage/[editId]`)

**Purpose.** The closest thing to the editor experience: preview plays instantly from proxies, the plan is readable, and you change it by asking. Layout follows the editor canon (07 §5.4): preview on the left, conversation on the right.

**Layout (≥ 1024).** Breadcrumbs Projects / Reels / title. Header: title, StatusBadge, line from status (below), actions: **Render · 24 credits** (amber; when planned), Menu (Try a different plan · 2 left, Download when done).
- **Left (fluid, centred):** the preview on `stage`, 9:16 up to 70 svh (legacy `ReelPreviewPlayer` imported read-only in v1; swapped for Area 5's `lib/media` player when it publishes). Caption under it: "Preview plays in your browser and is close to the final; the render is sharper and fully mixed."
- **Right (`w-96`, 384 px, `surface` panel):**
  - **The plan** card (`dl`, not divs — fixes A11y gap): Type (Talking head / Montage / Vlog), Length (mono + Menu "Auto length", "About 15 s"…), Script ("Following your script · 7 of 9 lines found"), missing-lines callout (warning) with "Leave them out" / "Show them as text cards", removed lines with **Restore** each and "Show all 12" (fixes P-R12), Hook `Input` (60) with Save when changed, Music ("Title · Artist", licence Badge, Menu of moods + "No music"), Look Menu, Captions Menu, Extras ("3 B-roll shots from your footage · 2 pop-ups"; each B-roll moment is a row "0:08 · coffee pour — from your clip 3" with **Swap** when alternates exist).
  - **Conversation**: the person's messages and Clipnera's replies as a thread (`prose` text), newest at the bottom; each reply ends with what changed ("Hook shortened · music → calm"). Needs API-R1 (reply + history). Until then the thread shows the person's message and a system line generated from the plan diff before/after the call ("Changed: hook, music") — derived from real data, no invented reply text.
  - **Composer** (`PromptBar` docked) "Tell me what to change" with "5 changes left" in the footer; disabled with the reason when 0.
  - Footer note: "Changes and previews are free. Credits are taken only when you render, and refunded if it fails." / after a render: "Re-renders cost a quarter of the first render."

**Status lines and states.**

| Status | Header line | Body |
|---|---|---|
| draft | "Not started" | Files list with what's missing + **Start planning** (analyze) or Add files (fixes the header-only dead end, P-R5) |
| analyzing | server `progress` | `ProgressSteps` vertical: Uploading your files · Reading your clips · Listening to what you said · Finding the best takes · Planning the edit; matched by step key (API-R2), falling back to text match; footer "Usually 2–3 minutes. You can leave this page; I'll notify you when the plan is ready." |
| planned | "0:31 · planned from 4:12 of footage. Change anything; the preview updates instantly." | Preview + plan + conversation |
| working (a change in flight) | — | Only the touched plan row shows `WorkingText`; the composer shows the working edge; other controls stay readable but locked |
| rendering | "Rendering your reel. This page updates by itself." | Render card (07 §6.6) with real % when available (`job.progress`), else indeterminate |
| done | "Rendered · 24 credits used" | Final video, render card Done (Download, Share link §14, Schedule when API-S3), "Music credit" and "Instagram caption" cards with `CopyField` |
| failed (plan) | server error | "Try again" re-runs analyze |
| failed (render) | server error | "Try rendering again" re-runs **render**, not the plan (fixes P-R10); "Your plan is safe." |

**Render confirm** (`Dialog sm`, fixes P-R2): "Render this reel?" · "Uses about 24 credits. You have 160. Refunded if the render fails." · Cancel / **Render · 24 credits**; button guarded against double submit and sends an idempotency key once API-X3 exists.

**Live updates.** `job.*` events when the edit's jobs emit them (B10); until then poll `GET /edits/{id}` every 2.5 s while analyzing/rendering, paused when hidden. Signed preview URLs refresh on 403 media errors by refetching the edit (fixes P-R20).

**360 px.** Preview full width (max 45 svh) on top; `SegmentedControl` Plan · Chat below it; Render button fixed at the bottom at 44 px; plan rows stack label over control.

**API.** `GET /edits/{id}` → `EditResponse`; `GET /edits/limits`; `POST /edits/{id}/changes` `EditChangesRequest {changes: [{op, value}]}` (ops: set_script_mode, restore_line, remove_line, set_hook, set_music, set_look, set_caption_style, set_length, remove_pop, skip_missing_lines); `POST /edits/{id}/chat` `{message ≤ 300}`; `POST /edits/{id}/plan` (replan); `POST /edits/{id}/render`; `POST /edits/{id}/analyze`.

### 16.2 Image reel board (`/dashboard/reels/[reelId]`)

**Layout.** Same header pattern; **Render · 18 credits** (amber, confirm dialog, in-flight guard — fixes P-R1). Left: when done, the final video (9:16); otherwise a **scene strip** (one segment per scene, width by duration, label "1 · Headline", kind by icon, not colour) that is a real `tablist` — selecting a scene scrolls to its card. Right/below: scene cards in a grid (2 → 5 columns): 9:16 preview (image, B-roll thumbnail, or the headline card), "0.0–3.4 s" mono, narration line (`prose`, 3 lines), **kind `SegmentedControl` Image / B-roll / Text** (now real: sends `ReelSceneUpdate.kind` — fixes P-R9), then the controls for that kind: photo strip (click = use), B-roll alternates strip (click = use; "Find more" needs API-R7 library search on the board — P-R8), headline `Input` (60) + Use text; AI shot (when `broll_studio.ai_shots`): secondary button "AI shot · 120 credits" with a confirm dialog (price from the server: API-R5; never violet), disabled with "Pro" on Free. Per-card busy (`.cn-pending-sheen` on that card while `generating`) and per-card error.

**Status lines.** draft → "Not planned yet" + **Plan the scenes** (fixes P-R5); planning → "Writing, voicing and laying out the scenes" with WorkingText; ready → "8 scenes · 0:32 · bold style · your voiceover. Pick a scene to change it."; rendering; done → "Rendered · 18 credits used" + Download, Share link, Render again; failed → reason + Try again (render vs plan as §16.1).

**360 px.** Scene strip scrolls in its own region; cards one per row; Render fixed at the bottom.

**API.** `GET /reels/{id}` → `ReelResponse`; `POST /reels/{id}/plan`; `POST /reels/{id}/scenes/{index}` `ReelSceneUpdate {kind, image_index?, asset_id?, headline?}`; `POST /reels/{id}/scenes/{index}/generate` `GenerateShotRequest`; `POST /reels/{id}/render`. Polling 2 s while planning/rendering/generating, paused when hidden.

**Legacy parity (§16).**

| Legacy (`ReelBoard`, `SceneCard`, `FootageReelBoard`, `ReelPreviewPlayer`) | New |
|---|---|
| Plan table (Type, Length, Script, Hook, Music, Look, Captions, Extras), restore lines (max 8) | Same rows as a `dl`; all removed lines restorable |
| Chat box "5 left", message vanishes, no reply | Thread with history; real reply needs API-R1 |
| Try a different plan · 2 left | Kept (header Menu) |
| Render without confirm (image board double-click) | Confirm dialog with credits, guarded |
| Analysing checklist matched by exact string | ProgressSteps by key (API-R2), string fallback |
| Draft: header only | Draft state with the next step |
| Inert Image/B-roll/Text chips | Real kind switch |
| Violet "AI shot · 120 credits" | Secondary button + confirm |
| `<a download>` cross-origin (opens a tab) | Download via the render card (export URL with `Content-Disposition`, API-X4) |
| Music credit + Instagram caption copy | Kept with CopyField |
| Done reel: download only | Download, Share link, Schedule (API-S3) |

---

## 17. Analytics (`/dashboard/analytics`) — decision: stays hidden (E1)

**Why.** Audit 06 §7.1: every number on today's page is a literal, the hook tester ignores its input, and the legend contradicts its own data. The one real endpoint, `GET /analytics/dashboard`, is not post performance either: "hours saved" is clip seconds × 8 (an invented multiplier), "average virality score" is the AI's own score, and "best post window" is the hour clips were **generated**, defaulting to "7:00 PM" (`analytics/repository.py`). Nothing reads YouTube or Instagram performance. 07 rule 4: numbers are real or absent. So there is nothing true to show yet.

**What ships now.**
- No nav entry, no Home card, not in `/go` (screens/01 D2, R26).
- The URL (routed by `new_ui_dashboard`, Area 3) renders an in-shell EmptyState: "Post analytics isn't here yet" · "When it is, you'll see how each posted clip did on YouTube and Instagram, from the platforms' own numbers. Until then, Publish shows every post and its link." · **Go to Publish** (when `social_publishing` on) / Go to Projects. No sample numbers, no "Sample data" badges.
- A new release flag `post_analytics` (default off, parent `social_publishing`; registry request RQ-4) guards the future page.

**What ships later (spec for when API-N1 exists).** It lives under **Publish** as the "Performance" tab (07 §5.2); `/dashboard/analytics` then 308s to `/dashboard/scheduler?tab=performance`. Hero moment: one honest number per clip. Layout: range SegmentedControl 7 / 30 / 90 days; StatCards Views, Average view duration, Likes + comments, Posts (each `null` → "—" until the platform reports); a `DataTable` of posts (poster, platform, posted, views, avg view %, likes, link), sorted by views; "Last updated from YouTube 2 h ago" per platform; per-platform empty "Connect YouTube to see its numbers". No retention-vs-raw comparison, no "virality index", no predicted scores.

**Legacy parity.**

| Legacy (`ViralAnalyticsView`) | New |
|---|---|
| 4 KPI cards of sample numbers | **Removed** (owner confirm; E1) |
| Retention chart (sample) | **Removed** |
| By platform (sample, TikTok/X) | **Removed**; later per-platform from real data |
| Hook tester (random 88–98) | **Removed** (E5) |
| "Sample data" disclosure | Not needed: no sample data is shown |
| Home card linking here | Removed (screens/01 R26) |

---

## 18. Legal pages, unsubscribe and data deletion

**Rule.** The words do not change. Not one. Only the chrome and type change (07: Plus Jakarta for headings, no Syne; `prose` 15/24 body; 720 px measure).

**Routing.** These URLs are deliberately not rewritten today (`wave6/01-platform-api.md`), and the legacy pages (`app/privacy` …) occupy the paths, so a new `app/(marketing)/privacy` would collide. The new pages therefore live at `app/v2/(marketing)/{privacy,terms,refunds,cookies,unsubscribe,data-deletion}/page.tsx` and need **RQ-2**: Platform adds these six paths to the `new_ui_auth` rewrite. A rewrite keeps the URL and query (`?token=`, `?code=` survive), and the auth exemption for `/unsubscribe` and `/data-deletion` is unchanged (they never redirect to sign-in). On a flag-fetch timeout they fall back to the legacy pages, which is safe. Until RQ-2 lands, this unit merges dark (pages exist, unreachable).

**Content source and parity.** Area 2 copies each legacy page's **body JSX** verbatim into `components/marketing/legal/content/<page>.tsx`. Shared pieces are **imported, not copied**, from the legacy `components/legal/LegalPage.tsx` (read-only import): `BUSINESS`, `LEGAL_UPDATED`, `LEGAL_LINKS`, `BusinessDetails`, `ContactLine`, `COOKIE_NOTICE_KEY`. A test `components/marketing/legal/legal-parity.test.mts` (runs with `node --test`, like `lib/editor/timeline.test.mts`) extracts JSX text and `href`s from both the legacy page and the new content file with the TypeScript compiler API and fails on any difference. At cutover the legacy pages are deleted and the content files become the only source. Note for the owner: Privacy and Terms still name TikTok and X (E10); changing that is a content decision outside this spec.

**Layout (`LegalLayout`, Area 2).** Marketing header (wordmark + Sign in / Open Clipnera, from Area 2's marketing chrome) · content column 720 px max, gutters 16/24/32 · `h1` `title-lg` 600 · "Last updated 27 September 2026" caption `fg-secondary` · body `prose` with `h2` `title-sm`, links `accent-text` underlined, lists with 8 px spacing · on ≥ 1024 a sticky **"On this page"** list of the page's `h2`s in a left 224 px column (generated from the headings at render; no content change) · legal links nav (`LEGAL_LINKS`) and the business details block in the marketing footer. Skip link, one `h1`, `nav` "Legal". Print: chrome hidden, body only.

**Unsubscribe (`/unsubscribe?token=`).** Same layout; a `Card` holds the action:
- With token: the legacy sentence "Stop emails about failed posts and accounts that need reconnecting. Clipnera never sends marketing emails." + **Unsubscribe** (amber; loading "Unsubscribing…" as legacy). Still **one click to confirm, never on load** (link scanners).
- Done: success InlineAlert (`role="status"`), legacy text "Done. You will no longer receive account emails from Clipnera. You can turn them back on in Settings → Profile."
- Missing token: danger InlineAlert "This unsubscribe link is incomplete." (legacy text).
- Server error: the server message in a danger InlineAlert (`role="alert"`), button usable again.
- API: `POST /email/unsubscribe` `UnsubscribeRequest {token}` → envelope `data: null`.

**Data deletion (`/data-deletion?code=`).** Body text verbatim. With `?code=`: a status `Card` above the text (moved from the bottom so Meta's reviewers see it first — a position change only): Confirmation code (mono, `CopyField`), Requested (date), Status (legacy text "Completed — the data has been deleted." / "In progress."). Loading: skeleton card. Error: danger InlineAlert with the server message. Without code: no card. API: `GET /social/webhooks/data-deletion/{code}` → `DeletionStatusResponse` (public, `auth: 'optional'`).

**States (all six).** Static pages render on the server (no loading state); cookie notice uses the v2 Banner at `z-cn-banner`; light theme via tokens; 360 px: single column, the "On this page" list becomes a `Disclosure` at the top.

**Legacy parity.**

| Legacy (`LegalPage`, six pages) | New |
|---|---|
| `max-w-3xl`, 14 px text, Syne `h1`, "← Clipnera" link | Marketing header/footer, 720 px measure, `prose` 15/24, Jakarta `h1` |
| Content | **Identical**, enforced by the parity test |
| Legal links nav at the bottom | Kept (footer), same five links |
| Unsubscribe: confirm button, done/error lines | Same behaviour and words; tokenised components |
| Data deletion: status box at the bottom | Same fields, moved above the text |

---

## 19. Removals and moves (owner to confirm each)

Legacy UI stays untouched and working; these describe what the **new** screens leave out or move. Nothing is deleted before cutover sign-off.

| # | Today | Where | Proposal | Why |
|---|---|---|---|---|
| R1 | Feature switches on `/admin/features` and `/admin/social` | `FeatureSwitches` | **Move** to the flags console; Social keeps a read-only strip | One place, reason + audit, no one-click flips |
| R2 | "Average per video (top videos)" tile | `AdminUsageView` | **Replace** with "Cost per source minute" | Overstated (P-15) |
| R3 | "Suggested times" cards, sample hashtags, hook ideas, "+41%" | `SocialSchedulerView` | **Remove** | Sample data (E5) |
| R4 | TikTok and X in composer, calendar and callback | publishing | **Hide** (TikTok code kept behind its flag) | Scope D3 / E4 |
| R5 | Inline compose card on the scheduler page | `SocialSchedulerView` | **Move** to `/dashboard/scheduler/new` | Linkable, one task per page (E6) |
| R6 | Analytics page content | `ViralAnalyticsView` | **Remove**; honest "not here yet" page | E1 |
| R7 | Reels as a top-level nav item | shell | **Move** under Projects (tab) | 07 §5.2 |
| R8 | Analytics nav/Home entry | shell, Home | **Move** under Publish, hidden until real | 07 §5.2, E1 |
| R9 | Violet admin tag, AI-shot violet, platform gradients | admin, reels, publishing | **Change** to neutral / monochrome marks | Palette |
| R10 | Status box at the bottom of `/data-deletion` | page | **Move** above the text | Position only, words unchanged |
| R11 | OAuth return always to Settings | connect callback | **Change** to return where the person started (RQ-1 or fallback) | P-S9 |

---

## 20. Builder units

Each unit is one Wave 6 builder, 1–3 days, one PR, mergeable on its own behind its area flag. Ownership follows [frontend.md §8.4](../architecture/frontend.md): a unit writes **only** the paths listed. Query keys get one file per unit (`lib/query/keys/<name>.ts`); API wrappers one file or folder per unit. Shared pieces inside an area are imported only through that area's `index.ts`. "After" names the unit whose public exports it imports; everything else runs in parallel.

### Area 10 — Admin (flag `new_ui_admin`)

| Unit | Scope | Owns (exact paths) | Days | After |
|---|---|---|---|---|
| **A1 Admin shell, Overview, shared kit** | §1, §2; `AdminAccess` wrapper around the legacy gate; `AdminPageHeader`, `DailyBars`, `UserPicker`, `useAdminList`, `ConfirmDialog` pattern; `/admin` → `/admin/overview` | `app/v2/(admin)/admin/{layout.tsx,page.tsx,loading.tsx,error.tsx,not-found.tsx}`, `app/v2/(admin)/admin/overview/**`, `components/admin-v2/{shell,shared,overview}/**`, `components/admin-v2/index.ts`, `lib/api/admin/{me,overview,users}.ts`, `lib/query/keys/admin-overview.ts`, `lib/query/keys/admin-users.ts` | 3 | — |
| **A2 Users and user detail** | §3, §4; `PlanDialog`, `CreditsDialog`; Check-a-flag dialog lands once A6 merges | `app/v2/(admin)/admin/users/**`, `components/admin-v2/users/**`, `lib/api/admin/{user-detail,credits}.ts` | 3 | A1 |
| **A3 Payments review queue** | §5 incl. keyboard review and screenshot refresh | `app/v2/(admin)/admin/payments/**`, `components/admin-v2/payments/**`, `lib/api/admin/payments.ts`, `lib/query/keys/admin-payments.ts` | 2–3 | A1 |
| **A4 Credits and Social** | §6, §7 (status strip reads the flags list through A1's query) | `app/v2/(admin)/admin/{credits,social}/**`, `components/admin-v2/{credits,social}/**`, `lib/api/admin/social.ts`, `lib/query/keys/admin-social.ts` | 2–3 | A1, A2 (`CreditsDialog` wrapper) |
| **A5 AI usage and Music** | §8, §10.2 | `app/v2/(admin)/admin/{usage,music}/**`, `components/admin-v2/{usage,music}/**`, `lib/api/admin/{usage,music}.ts`, `lib/query/keys/admin-usage.ts` | 2 | A1 |
| **A6 Flags list and detail** | §9.1, §9.2 incl. kill/restore, overrides, rules, save bar, conflict, history; `/admin/features` → `/admin/flags`; exports `EvaluationResult` | `app/v2/(admin)/admin/flags/**`, `app/v2/(admin)/admin/features/page.tsx`, `components/admin-v2/flags/**`, `lib/flags/admin/{api,keys}.ts` | 3 | A1 |
| **A7 Remote config, audit log, segments** | §9.3, §9.4 (reuses A6's rule list and save bar via its index) | `app/v2/(admin)/admin/{config,audit}/**`, `components/admin-v2/{config,audit}/**`, `lib/flags/admin/{config-api,audit-api}.ts` | 2–3 | A6 |
| **A8 B-roll curation v1** | §10.1 Library + Ingest + asset drawer; hidden tabs scaffolded only as routes that 404 | `app/v2/(admin)/admin/broll/**`, `components/admin-v2/broll/**`, `lib/api/admin/broll.ts`, `lib/query/keys/admin-broll.ts` | 3 | A1 |

### Area 8 — Export, share, publish (flag `new_ui_export`)

| Unit | Scope | Owns | Days | After |
|---|---|---|---|---|
| **P1 Accounts and connect** | §13: `AccountRow`, `ConnectButton`, `DisconnectDialog`, return-to logic; the v2 callback page (reachable after RQ-1); exported for Area 9 | `components/publish/accounts/**`, `components/publish/index.ts`, `lib/api/social/{types,accounts}.ts`, `lib/query/keys/social.ts`, `app/v2/(app)/dashboard/connect/[platform]/**` | 2 | — |
| **P2 Publish page (Scheduler)** | §11: tabs, week/month/list, post detail drawer, cancel, accounts rail, timezone | `app/v2/(app)/dashboard/scheduler/{page.tsx,loading.tsx}`, `components/publish/schedule/**`, `lib/api/social/posts.ts` | 3 | P1 |
| **P3 Composer** | §12: ClipPicker, account cards, provider options, CoverPicker, schedule fields, submit | `app/v2/(app)/dashboard/scheduler/new/**`, `components/publish/composer/**`, `lib/api/social/publish.ts` | 3 | P1 (and Area 3's clips wrapper, RQ-7) |
| **P4 Share page and share menu** | §14 against typed stubs (`// NEEDS-BACKEND`), behind `share_links` | `app/(marketing)/s/[shareId]/**`, `components/share/**`, `lib/api/share/**` | 2 | — |

### Reels (Lead to assign; frontend.md proposes Area 4; flag `new_ui_reels`)

| Unit | Scope | Owns | Days | After |
|---|---|---|---|---|
| **R1 Reels list and create** | §15: tab links, composer card, both create flows, grid | `app/v2/(app)/dashboard/reels/{page.tsx,loading.tsx}`, `components/reels/{list,create,shared}/**`, `components/reels/index.ts`, `lib/api/reels/{types,reels,edits}.ts`, `lib/query/keys/reels.ts` | 3 | — |
| **R2 Footage reel board** | §16.1 | `app/v2/(app)/dashboard/reels/footage/**`, `components/reels/footage-board/**`, `lib/api/reels/edit-board.ts` | 3 | R1 |
| **R3 Image reel board** | §16.2 | `app/v2/(app)/dashboard/reels/[reelId]/**`, `components/reels/image-board/**`, `lib/api/reels/reel-board.ts` | 2 | R1 |

### Area 3 and Area 2

| Unit | Scope | Owns | Days | After |
|---|---|---|---|---|
| **N1 Analytics, hidden** | §17 "not here yet" page; reads `useFlag('post_analytics')` only to pick the later redirect | `app/v2/(app)/dashboard/analytics/**` | 1 | — |
| **L1 Legal, unsubscribe, data deletion** | §18: six pages, `LegalLayout`, verbatim content files, parity test | `app/v2/(marketing)/{privacy,terms,refunds,cookies,unsubscribe,data-deletion}/**`, `components/marketing/legal/**`, `lib/api/legal/**` | 2–3 | Area 2 marketing header/footer |

**Definition of done for every unit:** all states in its section reachable (mock via `?state=` in dev only), 360 px checked, keyboard path and screen-reader names checked, `npx tsc --noEmit` clean for its paths, every wrapper's types diffed against the Pydantic schema, `NEEDS-BACKEND` stubs listed in the PR, no legacy file edited.

---

## 21. Design-system additions

| # | Addition | Home | Spec | Stand-in until then |
|---|---|---|---|---|
| DS-A1 | AdminPageHeader | `components/admin-v2/shared` | §1 | — |
| DS-A2 | DailyBars | `components/admin-v2/shared` | One Recharts bar series, tokens only, empty message, `role="img"` + Day-by-day table as its text alternative | — |
| DS-A3/A4 | PlanDialog, CreditsDialog | `components/admin-v2/users` | §3 | — |
| DS-A5 | EvaluationResult | `components/admin-v2/flags` | Value, reason in words, rule, bucket | — |
| DS-A6 | PaymentDetail | `components/admin-v2/payments` | §5 | — |
| DS-A7 | UserPicker | `components/admin-v2/shared` | Combobox on `useListNavigation`, debounced `GET /admin/users?q=` | — |
| DS-A8 | useAdminList | `components/admin-v2/shared` | Debounced search + URL state + offset paging (replaces three copies, D-01) | — |
| DS-A9 | RuleList | `components/admin-v2/flags` | §9.2 | — |
| DS-A10 | **SaveBar** | request to `components/ui` (also Brand kit, Settings) | Sticky dirty bar: diff summary, optional reason, Discard, Save | local copy in `components/admin-v2/flags`, deleted when ui ships |
| DS-A11 | DiffList | `components/admin-v2/shared` | Before/after per key | — |
| DS-P1/P2 | WeekGrid, PostChip | `components/publish/schedule` | §11 | — |
| DS-P3 | ClipPicker | `components/publish/composer` | §12 | — |
| DS-P4 | CoverPicker | `components/publish/composer` | Logic ported from `ReelsCoverPicker`, unique ids, clamping | — |
| DS-P5 | AccountRow, ConnectButton, DisconnectDialog | `components/publish/accounts` | §13 | — |
| DS-U1 | **PlatformMark** | request to `components/ui` | Monochrome YouTube / Instagram / TikTok / X glyphs with accessible names; brand colour only on the mark when `tone="brand"` | Lucide icons + text label |
| DS-U2 | **DateTimeField** | request to `components/ui` | Labelled date + time with min/max and zone caption | native inputs inside `Field` |
| DS-U3 | RadioGroup (02 §3.8, still to build) | `components/ui` | — | native radios in a `fieldset` with `legend` |
| DS-U4 | RenderCard (07 §6.6) | `components/ui` (DS agent) | — | reel boards render the same anatomy locally until it ships |
| DS-U5 | VideoPlayer chrome | `components/ui` / Area 5 | — | native `<video controls>` on `stage` |

---

## 22. NEEDS-BACKEND

Each gap is built against a typed stub in `lib/api/<domain>/` marked `// NEEDS-BACKEND: <endpoint>`; the UI hides the dependent control (never fakes it) until the endpoint exists.

| # | Need | For |
|---|---|---|
| API-X1 | `{data,message,error}` envelope on `/admin/users`, `/admin/users/{id}/plan`, `/admin/overview`, `/admin/payments*`, `/subscription/topup(s)`, `GET /analytics/dashboard` (C-01) | Contract rule |
| API-X2 | `response_model` on `GET /clips/projects`, `GET /clips/{project_id}`, `GET /clips/item/{clip_id}` | Composer ClipPicker types |
| API-X3 | `Idempotency-Key` on `POST /reels/{id}/render`, `/edits/{id}/render`, `/scenes/{i}/generate` (backend.md B8) | Render guard |
| API-X4 | Download URLs with `Content-Disposition: attachment` | Reel download (P-R18) |
| API-A1 | `GET /admin/me → {email, permissions: string[]}` | Read-only states before a 403 |
| API-A2 | Optional `reason` on `AdminUserPlanRequest` (audited) | Plan dialog |
| API-A3 | `plan=` filter on `GET /admin/users` | Users filter |
| API-A4 | Totals on admin list endpoints | Numbered pagination |
| API-A5 | `GET /admin/users/{id}/flags` (evaluated flags, reasons, overrides) | User detail Flags tab |
| API-A6 | Shared `admin_audit_log` (backend.md §8.3) + `GET /admin/audit?subject_id=&cursor=` | User Audit tab; full audit log |
| API-A7 | Paging for the detail sub-lists | User detail (F-06) |
| API-A8 | `payment.submitted` admin event | Live queue |
| API-A9 | Negative top-ups (deduct) with reason | Credits both directions |
| API-A10 | Credit price per source minute in `AdminUsageSummary` | "Below 3×" badge |
| API-A11 | `project_title`, `user_email` in `TopProjectUsage` | Usage table names |
| API-B1–B3 | Asset detail, usage/history, ingest runs (05-broll §7.5) | B-roll drawer and runs |
| API-B4 | Platform-only filter on `GET /admin/broll/assets` | P-19 |
| API-B5 | `GET /admin/music/options` (sources, licences, moods) | Music form choices |
| API-S1 | `post.updated` user event | Publish live status |
| API-S2 | `PATCH /social/posts/{id}` (reschedule, caption, options while scheduled) | Post detail |
| API-S3 | Reels/edits as a post source (`source_type` + `source_id` in `CreatePostsRequest`) | E7 |
| API-S4 | `scheduled_from`/`scheduled_to` on `GET /social/posts` | Month view |
| API-S5 | User timezone preference | Publish |
| API-S6 | `POST /social/caption-suggestions {clip_id, platform, prompt}` | AI caption |
| API-SH1–SH2 | Public share read; share create/update/delete/list (§14) | Share page |
| API-R1 | Chat reply text + persisted turns on `POST /edits/{id}/chat` | Reel conversation |
| API-R2 | Stable `progress_step` key on `EditResponse` | Analysing steps (P-R17) |
| API-R3 | Cover/poster for footage reels | Reels grid (P-R23) |
| API-R4 | Rename / delete reels and edits | Reel card menu |
| API-R5 | Server credit estimate before create; AI-shot price in a response | Create footer, AI shot dialog |
| API-R6 | Merged, paged reels list | Reels grid |
| API-R7 | Library search on the image reel board | "Find more" (P-R8) |
| API-N1 | Platform post analytics ingestion (YouTube Analytics, Instagram Insights) + `GET /social/posts/insights` | Analytics (E1) |

---

## 23. Open questions for the owner

| # | Question | Default used |
|---|---|---|
| Q1 | Confirm E1–E10 and R1–R11 | As listed |
| Q2 | Remove the switches from `/admin/social` once the console ships (06-flags Q6)? | Read-only strip + link to the kill dialog |
| Q3 | Show the payment status `success` as "Approved" to admins? | Yes |
| Q4 | Mask login IP addresses by default in user detail? | Yes, reveal per table |
| Q5 | Allow a second account on the same platform when the plan allows it (P-S13)? | Yes |
| Q6 | Share links: downloads allowed by default? Listed (indexable) ever? | Download off, never listed |
| Q7 | TikTok and X in the Privacy Policy and Terms: update the legal text separately? | Unchanged here |
| Q8 | Who owns Reels (frontend.md §10 Q8)? | Area 4 |
| Q9 | "Cost per source minute" replacing "Average per video" in AI usage? | Yes |

## 24. Requests for shared files

| # | To | Request |
|---|---|---|
| RQ-1 | Platform (`middleware.ts`, `lib/flags/ui-areas.ts`) | Rewrite `/dashboard/connect/*` under `new_ui_export` (URL, query and `Referrer-Policy` unchanged) |
| RQ-2 | Platform | Rewrite `/privacy`, `/terms`, `/refunds`, `/cookies`, `/unsubscribe`, `/data-deletion` under `new_ui_auth`, keeping their auth exemption |
| RQ-3 | Platform | `NEXT_PUBLIC_APP_ENV` for the admin environment badge |
| RQ-4 | Backend registry | Flags `share_links` (release, public, client) and `post_analytics` (release, parent `social_publishing`), then regenerate `registry.gen.ts` |
| RQ-5 | Platform | `hls.js` (share page on non-Safari) — or confirm MP4-only for v1 |
| RQ-6 | Area 3 | "Reels" tab link on Projects (§15) |
| RQ-7 | Area 3 | Publish `lib/api/clips` wrappers for `GET /clips/projects` and `GET /clips/{project_id}` via an index |
| RQ-8 | Lead (frontend.md §8.4) | Add `components/reels/**`, `lib/api/reels/**` (Reels owner), `lib/api/legal/**` (Area 2), `app/v2/(app)/dashboard/connect/**` (Area 8) |
| RQ-9 | Design System | DS-A10 SaveBar, DS-U1 PlatformMark, DS-U2 DateTimeField, DS-U3 RadioGroup |
