# Wave 6 — 07 Visual direction

Date: 5 October 2026. Owner: Design Director. Readers: every Wave 6 screen builder and the Design System engineer.

This is the single visual contract for Wave 6. **Where it disagrees with `02-design-system.md`, this document wins.** Where it says nothing, 02 still applies. Behaviour rules still come from `01-experience-principles.md`.

Inputs: `research/perplexity.md`, `research/lovable-visual.md` and `research/cardboard-compass.md` (their "What Clipnera should take" sections), plus the earlier `cardboard.md` and `lovable.md`. None of these studies involved hands-on use, so every number below is **Clipnera's decision**. Where a reference value was evidenced (Cardboard's CSS motion tokens, Lovable's state-layer alphas), the number is borrowed and the source is named.

**Token changes made with this document:** `frontend/lib/design/tokens.ts`, with `frontend/app/tokens.css` regenerated. No token was renamed or removed. §10 lists every change.

---

## 0. The stance in one paragraph

Clipnera should look like a **quiet, near-black editing room where the footage is the brightest thing and amber means "act" or "live"**. It takes three things from the references:

- From Perplexity: the calm, one centred box, and answers that cite their sources. In Clipnera, the sources are **moments in your video**.
- From Lovable: a composer that feels like one object, and a single rule for hover and press.
- From Cardboard: the stepped dark surfaces, the four-zone editor, the counted step list, and the AI's changes shown **on the timeline**.

Clipnera's signature elements are the **amber timecode citation**, the **quote-shaped moment card** and the **AI edge** on changed clips. Nothing else on screen competes with them.

---

## 1. Rules that override everything below

1. **Amber budget: at most one amber *action* per view.** Amber is also allowed for *signals*: the current selection, the playhead, the live dot, the composer's working edge, AI-change markers from the latest run, and timestamp-citation hover. A second amber button on a screen is a bug.
2. **No glows, gradients or glass on chrome.** This explicitly rules out Lovable's ambient backdrop and composer halo (see §9). The only gradients allowed are the working cues in §4.4 and the scrim over video controls.
3. **The footage sits on `stage` (pure black).** Anything placed on the stage (player controls, quality badge, frame-check label) renders inside `data-theme="dark"` in both themes.
4. **Numbers are real or absent.** Counters, percentages, scores and "N× faster" lines appear only when the backend sends them. Placeholders use skeletons, never invented numbers.
5. **`cn-*` tokens only.** No raw hex, no arbitrary `[..px]` values, no new z-index. Layout sizes in §5 are chosen to sit on Tailwind's scale (`w-60`, `w-96`, `h-12` …). Resizable panels read their limits from `layout` in `tokens.ts`.

---

## 2. Colour, surfaces, edges

### 2.1 The neutral ladder (dark is the default)

Cardboard separates its surfaces with five evenly spaced neutral steps. Clipnera's ladder had a gap between `surface` (#171717) and `surface-raised` (#1c1c1c) that was too small to read, so a menu over a panel barely separated. This wave lifts `surface-raised` to **#202020** and adds two roles: `surface-sunken` for wells and `stage` for footage. No hue was added.

| Step | Token | Dark | Light | Used for |
|---|---|---|---|---|
| −1 | `stage` **new** | `#000000` | `#000000` | Preview stage, player, letterbox, video tiles before the poster loads |
| 0 | `bg` | `#0a0a0a` | `#fafafa` | Page; gutters between editor panels |
| 0.5 | `surface-sunken` **new** | `#111111` | `#f5f5f5` | Wells inside a panel: timeline track area, transcript gutter, code-like blocks |
| 0.5 | `field` | `#111111` | `#ffffff` | Inside inputs (not the composer) |
| 1 | `surface` | `#171717` | `#ffffff` | Panels, sidebar, cards, conversation panel |
| 2 | `surface-raised` **changed** | `#202020` (was `#1c1c1c`) | `#ffffff` | Composer, menus, popovers, dialogs, toasts, hover peeks |
| 3 | `surface-hover` | `#262626` | `#f5f5f5` | Hover fill on neutral rows and controls |
| 4 | `surface-active` | `#2e2e2e` | `#e5e5e5` | Pressed or selected neutral fill, selected segment |

Contrast on the new `surface-raised` #202020 (measured): `fg` 15.61:1, `fg-secondary` 6.46:1, `fg-muted` 4.85:1, `control-border` 3.06:1, `accent-text` 9.76:1, `danger-text` 6.05:1. All pass. `control-border` is now 0.06 above the 3:1 floor, so do **not** lighten `surface-raised` further.

Text rules carried forward and tightened:
- `fg-muted` may sit on `bg`, `surface-sunken`, `surface`, `surface-raised` and `surface-hover` (4.50:1, exactly at the floor). **Never** put it on `surface-active` (4.04:1) or on any state-layer overlay. Text inside a pressed or selected row steps up to `fg-secondary`.
- UI body text is `fg`, and supporting text is `fg-secondary`. Lovable's dim body text (tertiary colour) is used **only** for marketing sublines, in `fg-secondary`.

### 2.2 Amber, and the status colours

The values are unchanged from 02 §2.1. The rules for using them:

| Colour | Means | Never |
|---|---|---|
| Amber (`accent*`) | The one primary action; selection; playhead; live work; AI-changed; citation hover | Decoration, category colour, track colour, illustration |
| Emerald (`success*`) | Ready, done, posted, render verified | Track kind, "AI" |
| Rose (`danger*`) | Failed, destructive, **timeline conflict** (overlap, caption off-frame) | Warnings that need no action |
| Sky (`info*`) | Scheduled, informational, "preview quality" | Links (links are `accent-text` or `fg` underlined) |

**02 §5.2 is overridden here.** Timeline tracks are **not** coloured by kind. 02 used `accent-subtle` for text tracks, `info-subtle` for audio and `success-subtle` for overlays. Instead, every clip block is neutral (`surface-active` fill, `border-strong` edge). Its kind is shown by an icon and by the purpose-named track header ("Captions", "Voice", "Music", "B-roll"). This keeps the status hues meaning status.

### 2.3 Edges

The existing tokens already match Cardboard's hairlines: `border` ≈ white at 6% over `surface`, and `border-strong` ≈ white at 16%. So no new edge colours were needed.

| Edge | Token | Where |
|---|---|---|
| Hairline | `border` (1 px) | Only where content touches content: list dividers, table rows, the panel's inner header line |
| Emphasis | `border-strong` (1 px) | Floating surfaces (composer, menus, dialogs), timeline clip blocks |
| Control | `control-border` (1 px) | Inputs, checkbox, switch track, radio: the 3:1 identifying edge |
| Selected | `accent-border` (2 px) | Selected clip, selected card or tile, picked choice |
| Media hairline | `.cn-media-edge` **new** | An inner 1 px line drawn *over* every thumbnail and video, at `state-layer` alpha 16% dark / 12% light, so the edge reads on any picture |

**Panels are separated by gutters, not outlines.** In the editor and the shell, adjacent panels are `surface` on a `bg` page with a **4 px gutter** (`gap-1`) and `rounded-cn-lg` corners. A border line between two panels is not used. Cards inside a panel use a hairline only when they sit on the same step as the panel.

### 2.4 Hover and press: the state-layer model

There is one rule with two implementations, and both give the same pixels:

1. **Neutral surfaces on the ladder** (rows, ghost and secondary buttons, menu items, tabs) keep their baked fills: hover becomes `surface-hover` and press becomes `surface-active`. These equal a white overlay of 6% and 10% over `surface`, and keeping them baked holds `fg-muted` at a passing contrast.
2. **Everything else** (amber buttons, status fills, tinted chips such as `accent-subtle`, media tiles, the composer's send button) adds the class **`.cn-state`**. It overlays `state-layer` at `--cn-state-hover` (dark 0.06 / light 0.04) and `--cn-state-press` (0.10 / 0.08). The values are borrowed from Lovable's 8% / 12% and tuned so they match the baked neutrals.

Timing for both: **hover turns on instantly (0 ms) and fades off over `fast` (120 ms, `ease-cn-standard`)**. Press is instant. Hover applies only under `@media (hover: hover)`. Disabled controls get no state layer.

The rule replaces 02's `accent-hover` swap for primary buttons. `accent-hover` and `accent-pressed` stay valid, but new code should prefer the overlay, because it works for every fill.

Media tiles follow their own pattern:
- Hover: the poster stays at full brightness, and the hover preview starts after 150 ms. The media hairline goes from 16% to 24% (Design System engineer: implement with `.cn-media-edge` and a hover modifier).
- Press: `brightness(0.9)`.
- Lovable's 95% dimming on hover is not used, because footage is the brightest thing on screen.

`.cn-state` sets `background-image`. Don't combine it with another background-image on the same element; put the sheen or the sweep on a child.

### 2.5 Elevation

| Level | Fill | Edge | Shadow | Use |
|---|---|---|---|---|
| 0 | `bg` / `surface` | none or hairline | none | Page, panels, cards at rest |
| 1 | `surface` | `border-strong` | `shadow-cn-1` | Hovered interactive card, floating timeline chip, selected segment |
| 2 | `surface-raised` | `border-strong` | `shadow-cn-2` | Composer (both placements), menus, popovers, tooltips, toasts, sidebar hover peek |
| 3 | `surface-raised` | `border-strong` | `shadow-cn-3` | Dialogs, drawers, bottom sheets |

In dark mode, the surface step carries the depth and the shadow only grounds it. In light mode, the shadow does more of the work. The shadow values are unchanged.

---

## 3. Type

### 3.1 The face: Plus Jakarta Sans for all UI; JetBrains Mono for numbers

**Decision: Plus Jakarta Sans for every piece of UI text, including display headings. JetBrains Mono for timecodes, durations, credits, counts and shortcuts. Syne is kept for the wordmark only** (`LogoMark`). It no longer sets headings, including on marketing pages.

Why:
- **All three references use one sans for everything** (Perplexity: FK Grotesk; Lovable: Camera Plain; Cardboard: Geist). A second display face reads as "marketing site", not "tool". One family makes Clipnera feel like one instrument.
- **Jakarta is the only installed UI sans, and it is good at the job.** It has a tall x-height and open apertures that hold up at 12–13 px on dark backgrounds. Its slightly geometric warmth suits amber and gives Clipnera a voice distinct from Cardboard's Geist. Adding Geist or Inter would need a new npm package (Platform only), and it would make Clipnera look like Cardboard.
- **Jakarta's limits, handled:**
  - The @fontsource build is static (400–800, no variable axis), so Lovable's 450/480 in-between weights are not available. Use 500 where they would use 450.
  - Jakarta sets wide at display sizes, so display tracking is tightened more than in 02 (§3.3).
- **JetBrains Mono** is already loaded at 500 and 700. Use it with `tabular-nums` so timecodes don't jitter while they count. It also marks "this is a measurement", which is how a reader tells a citation chip from prose.

Load only what's used: Jakarta 400/500/600/700 (800 only if the wordmark needs it) and Mono 500. Ask Platform to drop Syne 800 if the wordmark doesn't use it.

### 3.2 Scale

| Token | Size / line | Weight | Tracking | Use |
|---|---|---|---|---|
| `caption` | 12 / 16 | 500 | 0 | Meta, badges, timecodes, chip meta. **The floor.** |
| `label` | 13 / 18 | 500 (600 for field labels) | 0 | Controls, menu items, table cells, editor panels, step rows |
| `body` | 14 / 20 | 400 | 0 | App default; docked composer text on desktop |
| `prose` **new** | 15 / 24 | 400 | 0 | AI replies, moment quotes, result summaries in the conversation panel |
| `body-lg` | 16 / 24 | 400 | 0 | Hero composer; **every input on phones** (no iOS zoom); Ask dialog replies |
| `title-sm` | 18 / 26 | 600 | −0.005em | Card, dialog and panel titles |
| `title` | 20 / 28 | 600 | −0.01em | Section headings, phone page titles |
| `title-lg` | 24 / 32 | 600 | −0.015em | Page titles (`PageHeader`); 600, not 700 |
| `display-sm` | 32 / 40 | 700 | **−0.025em** | Home question on phones |
| `display` | 48 / 56 | 700 | **−0.03em** | Home question, landing hero on tablet |
| `display-lg` | 64 / 68 | 700 | **−0.04em** | Landing hero on desktop |

**Why `prose` exists.** Perplexity sets answers at 16 px with a 1.6 line height in a 768 px column. Clipnera's conversation panel is 384 px wide, where 16 px gives about 42 characters per line, which is choppy. 15 / 24 gives about 48 characters with the same airy leading. AI text is reading, not UI, so it gets the extra line height.

### 3.3 Weight and tracking rules

- **Three working weights:** 400 for reading, 500 for UI, 600 for titles. 700 is for display sizes only. Never use 300. Never use 800 outside the wordmark.
- Hierarchy comes **colour first, then weight, then size**. A panel heading is `label` 600 `fg`, not a bigger size.
- Tracking is 0 at 16 px and below. It tightens as size grows, following the table. Never add positive tracking, and never use all-caps labels (02 rule kept).
- **Numerals:** every number that changes or lines up uses `font-cn-mono tabular-nums`. Prose numbers ("6 clips") stay in Jakarta.
- **Measure:** prose is at most 72 characters (`reading-max` 720 px). The conversation panel is narrower than that by design.

---

## 4. Shape, density, motion

### 4.1 Radius

| Token | px | Use |
|---|---|---|
| `xs` | 4 | Kbd, checkbox, **timeline clip blocks** (02 said 6), timestamp citation chip |
| `sm` | 6 | Menu items, small buttons inside toolbars, chips inside bars |
| `md` | 8 | Buttons, inputs, segmented controls, IconButtons that are not round |
| `lg` | 12 | **Cards, thumbnails and tiles**, menus, popovers, toasts, editor panels |
| `xl` | 16 | Dialogs, drawers, **docked composer** |
| `2xl` | 20 | Bottom-sheet top corners |
| `3xl` **new** | 24 | **Hero composer** (Home, landing) |
| `full` | — | Pills, badges, avatars, the send button, the live dot |

Nested radius = outer radius minus padding (a 16 px composer with 8 px padding holds 8 px chips).

### 4.2 Control heights and density

| Token | px | Tailwind | Use |
|---|---|---|---|
| `xs` **new** | 28 | `h-7` | Editor toolbars, timeline header toggles, context chips, the composer's mode pill. Hit area is at least 32 px through padding |
| `sm` | 32 | `h-8` | Dense panels, chips, the docked send button, table row actions |
| `md` | 36 | `h-9` | App default; the hero send button |
| `lg` | 44 | `h-11` | Every primary target on touch layouts (< 768 px or `pointer: coarse`) |

There are three densities, chosen by screen and never by user setting:

| Density | Screens | Text | Default control | List row | Panel padding |
|---|---|---|---|---|---|
| **Comfortable** | Home, Projects, Library, Brand kit, Settings, landing | `body` 14 | 36 | 48 | 24 |
| **Compact** | Editor, Clip studio, admin tables | `label` 13 | 32 (toolbars 28) | 32 | 12 |
| **Touch** | anything < 768 px | `body` 14, inputs `body-lg` 16 | 44 | 56 | 16 |

Spacing stays on the 4 px grid (02 §2.3). Rhythm: 8 px between related controls, 16 px inside cards, 24 px between groups, 48 px between page sections (64 px on the landing page, 104 / 160 px between landing sections, per Lovable).

### 4.3 Motion: durations and easings

**How the two sources reconcile.** 01 and 02 set a 150–250 ms budget as "Clipnera's own decision, not measured". Cardboard's CSS gives evidenced values of 120 / 180 / 280 ms, all set to 0 under reduced motion. The evidenced values win, because they give a crisper response with a longer, gentler travel time for sheets. The window is now **120–280 ms**, with the 600 ms highlight as the one exception. The token **names are unchanged and the values moved**, so every component picks this up automatically.

| Token | Was | Now | Use |
|---|---|---|---|
| `instant` | 0 | 0 | Hover-on, press, reduced motion |
| `stream` | 120 | 120 | Streaming-text word-group fade |
| `fast` | 150 | **120** | Hover-off, tooltip, step tick and dim, exits, page cross-fade, chip indent |
| `base` | 200 | **180** | Menus, popovers, dialogs, height collapse, tab indicator, composer focus edge |
| `slow` | 250 | **280** | Drawers, sheets, panel collapse and expand, sidebar rail ↔ full |
| `highlight` | 600 | 600 | An operation landing on the timeline (the one exception) |

| Easing | Curve | Use |
|---|---|---|
| `standard` **new** | `cubic-bezier(0.2, 0, 0, 1)` | State changes in place: colour, opacity, state layer, small transforms (Cardboard "standard") |
| `out` | `cubic-bezier(0.16, 1, 0.3, 1)` | Entering (Cardboard "decelerate", same curve) |
| `in` | `cubic-bezier(0.4, 0, 1, 1)` | Leaving (Cardboard "accelerate", same curve) |
| `in-out` | `cubic-bezier(0.65, 0, 0.35, 1)` | Resizing or moving in place: height collapse, panel drag release |

Rules kept from 02 §6: animate only opacity and transform (plus height for collapse); no spring overshoot; no sound; under `prefers-reduced-motion`, everything is instant and loops stop.

### 4.4 The "working" cues: what moves while Clipnera works

Every cue is driven by a real run or job event. None has a fixed duration that pretends to be progress. Spinners are not used anywhere.

| Cue | Where | Spec | Loop token | Reduced motion |
|---|---|---|---|---|
| **Working edge** | The composer, while a run is active | `.cn-working-edge`: a 2 px amber segment, 40% of the width, sweeps along the bottom edge inside the corner radius | `sweep` 1600 ms, `in-out` | A static amber line at 40% opacity |
| **Working text** | The active step line, "Reconnecting" strips | `.cn-shimmer-text`: `fg-secondary` → `fg` sweep | `shimmer` 2400 ms linear | Static `fg-secondary` |
| **Live dot** | Running step, activity pill, rendering card, "Processing" badge | 6 px amber dot, opacity pulse (`animate-cn-pulse`) | `pulse` 1600 ms | Still dot |
| **Pending sheen** | A *known* object still being made: a clip rendering, a moment card streaming in, a B-roll candidate being checked | `.cn-pending-sheen`: a slow diagonal sheen at hover alpha | `sheen` 3600 ms | None (static fill) |
| **Skeleton pulse** | An *unknown* shape loading (page data) | `cn-pulse` opacity 1 → 0.55 | 1600 ms | Static |
| **Funnel counter** | Any search: moments, B-roll | Mono numbers that tick as events arrive: "Watching 132 clips · 3 fit". Numbers swap without a fade | — | Same |
| **Frame check** | Over the preview after an edit lands, *while the backend's check step runs* | `overlay/40` scrim fades in over `base`, a centred `WorkingText` "Checking the result", fades out over `base` when the step ends | Event-driven, not 2.6 s | Static scrim and label |
| **Change highlight** | Timeline clip an operation just touched | `animate-cn-highlight`: 2 px amber outline fades out over 600 ms, then the AI edge stays (§6.5) | `highlight` | A static outline for 600 ms, then removed |
| **Determinate progress** | Uploads, renders | Width eases over `base` per update | — | Jumps |

The Tailwind animation `cn-sweep` is still hard-coded to 1.4 s in `tailwind.config.ts`. See the Requests in §10.

---

## 5. Layout canon

### 5.1 Breakpoints

| Name | Min width | Layout |
|---|---|---|
| phone | 0 | One column, bottom tab bar, sheets instead of dialogs, editor in tabs |
| `sm` | 640 | Larger phone or small tablet; grids go to 2 columns |
| `md` | 768 | Tablet: sidebar rail (56), no tab bar; editor shows preview and timeline, conversation in a drawer |
| `lg` | 1024 | Desktop: full sidebar available; editor in three zones (rail, preview, conversation) plus timeline |
| `xl` | 1280 | Content reaches its 1280 max; editor left panel available on demand |
| `wide` **new** | 1440 | Editor opens with all four zones |
| `2xl` | 1536 | Grids get one more column |

### 5.2 The app shell

| | Desktop ≥ 1024 | Tablet 768–1023 | Phone < 768 |
|---|---|---|---|
| Sidebar | 240 (`w-60`), collapsible to a 56 rail (`w-14`), state saved per user | 56 rail; the expand button opens 240 **over** the page | none |
| Top bar | 48 (`h-12`), inside the content column: breadcrumb or page title left; activity pill, bell right | same | 48: wordmark, activity, bell, avatar |
| Bottom | — | — | Tab bar 56 + safe area: **Home · Projects · New (+) · Library · More** |
| Content | Max 1280, gutters 32 | Gutters 24 | Gutters 16 |

**The sidebar has at most five destinations.** The owner's rule:

1. **Home**
2. **Projects**: includes reels and folders. Reels become a "Reels" filter tab inside Projects; `/dashboard/reels` URLs keep working.
3. **Library**: B-roll, uploads, music, trash
4. **Publish**: scheduler plus post analytics. Shown only when `social_publishing` is on; otherwise the sidebar has four items.
5. **Brand kit**

Everything else is reached another way:
- A **"New video"** button sits at the top of the sidebar. It is an action, not a destination: secondary style, full width, a ⌘N hint. The one amber action on each page stays inside the page.
- **Settings**, keyboard shortcuts, theme, workspace switch and sign out live in the avatar menu at the bottom. Above it sits a **compact credit meter**: balance in mono plus plan name, which opens the credits popover.
- Analytics moves under Publish.
- **"Recent"**: the last 4 projects as plain rows, each with a live dot when running. Hovering a row shows a peek card (`surface-raised`, 16:9 poster, title, status, last edited) after 300 ms.
- Empty groups are hidden, not illustrated.

**Active nav item:** `surface-active` fill, `fg` 600 label, amber icon. This is the only amber in the sidebar.

**There is no global search box.** ⌘K opens the "Ask Clipnera" dialog (01 §4, screens/01 §5.6).

### 5.3 Home

- One centred column, 672 px wide (`composer-max`).
- The column's top sits at **24 svh** on desktop and 15 svh on tablet, so the composer lands at the optical centre on first load. On phones it starts 32 px under the top bar.
- From the top:
  1. Greeting in `label` `fg-muted` ("Good evening, Akhil")
  2. The `h1` question in `display` (`display-sm` on phones): "What should we cut today?"
  3. The **hero composer**, 24 px below
  4. **Four contextual suggestion chips** (32 px), 16 px below. They are hidden while the composer has text, and a click fills the composer and never sends.
- 64 px below the chips is the **Continue** section (`title-sm` "Recent" + "All projects →"):
  - Cards: 3 at ≥ 1024, 4 at ≥ 1536, 2 on tablet, 1 on phones.
  - Each card: 16:9 poster, title, and meta "2 h ago · 9:16 · 0:27" (age · aspect · length).
  - Running projects show the live step in WorkingText.
- Below that come In progress (only when jobs run), Top clips this week and Up next (flag), as screens/01 §7 already specifies. All of them are below the fold, and none competes with the composer.
- There is no feed, no dashboard stat tiles and no separate drop zone. **The composer is the drop zone.**

### 5.4 The Editor: four zones

The Editor is full-screen with no app shell. Zones are separated by 4 px `bg` gutters, and each zone is a `surface` panel with `rounded-cn-lg`.

```
┌──────────────── top bar 48 ──────────────────────────────────────┐
│ ‹ Project · name ▾ (version)        History  Share  [Export ⌘E]  │
├──┬────────────┬───────────────────────────────┬──────────────────┤
│R │ Panel 288  │        Preview (stage)        │  Conversation    │
│a │ media /    │        flexible, ≥ 480        │  384             │
│i │ captions / │                               │  (320–512)       │
│l │ brand …    │                               │                  │
│48├────────────┴───────────────────────────────┤  thread          │
│  │ Timeline 256 (160 – 50% of height)          │                  │
│  │ spans rail + panel + preview                │  [composer]      │
└──┴────────────────────────────────────────────┴──────────────────┘
```

| Zone | Default | Min / max | Notes |
|---|---|---|---|
| Top bar | 48 | — | Left: back, project name with version switcher. Right: History, Share (ghost), **Export ⌘E (the single amber button)** |
| Tool rail | 48 | fixed | Icons: Media, Captions, Brand, Music, B-roll, Settings. Selecting one opens the panel. Each has a tooltip and a shortcut |
| Left panel | 288 | 240 / 400 | Duration-first rows ("0:12 · skyline-dusk.mp4"), search, filter chips |
| Preview | flexible | ≥ 480 wide | `stage` fill, aspect toggle (9:16 / 1:1 / 16:9) and safe-zone switch in its own bottom bar, QualityBadge top-left, floating selection toolbar (Select S · Edit text T · Comment C) at bottom-centre |
| Conversation | 384 | 320 / 512 | Runs **full height** on the right. The thread scrolls, the composer is pinned at the bottom, and the queue sits above the composer |
| Timeline | 256 tall | 160 / 50% | Spans rail + panel + preview. Ruler in seconds, purpose-named tracks with mute and lock, playhead 2 px amber |

Behaviour:
- Splitters have an 8 px hit area (32 px on coarse pointers) and show a 2 px amber line while dragged.
- Sizes are saved per user (`usePersistentState`).
- **⌘B** hides the conversation. **⌘\\** hides the left panel.

| Width | Default arrangement |
|---|---|
| ≥ 1440 | All four zones |
| 1280–1439 | Left panel closed (rail only) |
| 1024–1279 | Rail, preview, conversation at 320; timeline 200 |
| 768–1023 | Rail, preview and timeline stacked. The conversation is a right Drawer (384) toggled by a top-bar "Chat" button. **The composer stays pinned under the preview** as a full-width docked bar |
| < 768 | See §5.7 |

### 5.5 Library (and Projects grid)

- Page header (`title-lg`), then a toolbar: SearchField (36) · Filter (one searchable menu; applied filters become removable chips; "Clear filters") · View (grid or list, plus sort).
- Tabs above the toolbar: Clipnera library · My uploads · Collections · Trash.
- The grid is chromeless. Each tile is a thumbnail at `rounded-cn-lg` with `.cn-media-edge`:
  - Duration in mono, bottom-right, on a `stage/80` chip.
  - Source icon bottom-left.
  - Status badge top-left (Rendering in `info`, Ready in `success`, Failed in `danger`).
  - Title (`label` 500, one line) and meta (`caption` `fg-muted`, "0:12 · Stock · 1080p") **below** the thumbnail.
  - The ⋯ button (28) appears on hover or focus and is always visible on touch.

| Width | 16:9 tiles | 9:16 tiles | Gap |
|---|---|---|---|
| < 640 | 1 col | 2 col | 12 |
| 640–1023 | 2 | 3 | 16 |
| 1024–1279 | 3 | 4 | 16 |
| 1280–1535 | 4 | 5 | 24 |
| ≥ 1536 | 5 | 6 | 24 |

- **Multi-select:** ⌘A, Shift-click or long-press. A floating bottom toolbar (`surface-raised`, `shadow-cn-2`, `rounded-cn-xl`) shows "3 selected · Add to project · Download · Delete · Clear (Esc)".
- Delete moves items to a 30-day Trash with restore.
- The Projects page uses the same grid with 16:9 posters and the meta "age · aspect · length".

### 5.6 Settings

- This is a full page, not a dialog (§9).
- Inside the content column: a 224 px section nav on the left (Account, Workspace, Billing & credits, Connections, Notifications, Appearance), and a 672 px content column.
- A **Search settings** field sits at the top of the nav and understands synonyms ("card" finds Billing, "logo" finds Brand kit).
- Each section is a stack of **group cards**: `surface`, `rounded-cn-lg`, rows divided by hairlines.
- A row is at least 56 px tall: label (`label` 600) and description (`caption` `fg-secondary`) on the left, the control on the right.
- Settings that apply immediately use a Switch with a toast. Form sections end with a Save button that is disabled until something changes.
- Destructive actions (delete workspace, delete account) sit in the last group with a rose edge and a typed confirmation.
- Phones: a section list, then each section as its own page with a back button. Rows stack the control under the label when the label is longer than one line.

### 5.7 Behaviour at 360 px

These rules apply to every screen and are checked at 360 × 740.

- 16 px gutters and no horizontal page scroll. Chip rows scroll sideways inside their own container, with a `mask-image` fade at the edge (a mask, not a coloured gradient).
- The composer is full width (328). Its text is `body-lg` 16, and the mode pill shows its icon only. The credit hint is shortened ("12 credits") and never truncated.
- The tab bar has 5 tabs × 72 px. Each label is `caption` and each icon is 20 px, with a 44 px hit area.
- Dialogs become bottom sheets with `rounded-cn-2xl` top corners and a drag handle. Menus longer than 6 items also become sheets.
- Tables become stacked rows (title line, then the meta line).
- **Editor on a phone:**
  - Top bar 48.
  - The preview stage sits full width at the top: 16:9 is 203 px tall; a 9:16 clip is shown letterboxed at up to 45 svh.
  - Below it, a SegmentedControl (44): **Chat · Timeline · Media**.
  - The Timeline tab shows a compact single "story" track 96 px tall with the playhead. "Expand" opens the full multi-track view as a sheet.
  - The composer is pinned at the bottom above the safe area. In the Chat tab it is always visible; in other tabs it collapses to a 44 px "Ask Clipnera" bar that expands on tap.
- Primary targets are 44 px. Chips can be 32 px visually, with padding that extends the hit area to 44.

---

## 6. Signature elements

These are what make a screenshot recognisably Clipnera. The Design System engineer builds them; screen builders compose them without restyling them.

### 6.1 The composer

**One component with three placements:**

| | Hero (Home, landing) | Docked (Editor, project) | Sheet (phone, ⌘K dialog) |
|---|---|---|---|
| Max width | 672 | panel width − 24 | screen − 32 |
| Radius | `3xl` 24 | `xl` 16 | `xl` 16 (sheet itself `2xl`) |
| Padding | 12 | 8 | 12 |
| Text | `body-lg` 16/24 | `body` 14/20 (16 on touch) | `body-lg` 16 |
| Rows | 2 → grows to 8, then scrolls (cap 35 svh) | 1 → 8 | 1 → 6 |
| Send | 36 round | 32 round | 44 round |
| Mode pill | hidden (Home always "make"; format is AI-picked) | shown | shown when in a project |

**Anatomy, top to bottom:**

1. **Context row** (only when chips exist). ContextChips are 28 px with an 8 px gap. Kinds: source video (16:9 mini poster, title, duration in mono, ×), clip, range (`0:12 – 0:31`), caption line, asset, moment. More than 3 chips collapse to "+2". A chip appearing or disappearing animates over `fast`.
2. **Text field.** Placeholder is in `fg-muted`, and fades out over `fast` on the first keystroke. Copy:
   - Hero: "Paste a YouTube link or drop a video, then say what you want"
   - Docked with nothing selected: "Describe an edit to the whole video"
   - Docked with a selection: "Describe an edit to the selection"
   - After a result: "What next?"
3. **Control row** (32 high). Left to right:
   - Left: **+** (round, 32, ghost). It opens a popover with a search field and rows Upload video · Paste link · From library · Brand kit, each with a chevron. Highlight uses `surface-active`, not amber.
   - Left: **mode pill** (28): "Edit ▾" opens Edit / Ask / Plan, each with a one-line description. ⇧Tab cycles the modes. This replaces 02's SegmentedControl, because a pill reads as part of the box.
   - Spacer.
   - Right: **credit hint** (`caption` mono `fg-muted`): "≈ 12 credits".
   - Right: a reserved mic slot (see §11 Q3).
   - Right: **Send**.

**Shell:**
- Fill `surface-raised`, 1 px `border-strong` edge, `shadow-cn-2` in the hero placement (none when docked).
- Identification under WCAG 1.4.11 comes from the visible placeholder and the 3:1 controls inside the box (+, send). The edge is decorative.
- Hover: the edge goes to `control-border` over `fast`.
- Focus-within: the edge goes to `fg-muted` over `base`. Keyboard focus also shows the standard 2 px amber focus ring around the whole box.
- No glow and no halo (§9).

**Send button states:**

| State | Look |
|---|---|
| Empty | `surface-active` fill, `fg-disabled` arrow, `aria-disabled`, tooltip "Type a prompt or add a video" |
| Ready | `accent` fill, `accent-fg` ↑ arrow, `.cn-state` |
| Running, empty field | Neutral `surface-active` circle with a `fg` ■ — **Stop** |
| Running, with text | Send becomes amber "↑" with tooltip "Add to queue", and Stop sits beside it (secondary, 32). Stop never clears the text |
| Offline / no credits / no project | Disabled, reason in a tooltip and a line under the box |
| Before hydration | Every control rendered `disabled` by the server, so nothing is clickable-but-dead |

**Composer states (all must be designed):**
- idle, hover, focus, typing, slash menu open, chip attached
- uploading attachment (chip with a determinate ring and percentage)
- **drag-over:** the whole box shows `accent-subtle` fill, a 2 px dashed `accent-border` and "Drop video to start"
- running (`.cn-working-edge` plus Stop)
- queued ("2 waiting" in the hint slot; the PromptQueue sits above)
- not sent ("Not sent. Check your connection." + Retry under the box; the text stays)
- out of credits (the hint turns `danger-text` and an Add credits link appears under the box)
- viewing an older version (read-only: "Viewing an earlier version · Back to latest")
- disabled offline (the text is kept)

### 6.2 The run and its step list

A run reads as a small report, not a chat bubble. The user's prompt is the visual heading of each turn: `label` 600 `fg`, with its chips read-only below it. Turns are separated by 32 px and a hairline.

1. **Plan line.** One sentence with counts, in `prose` `fg-secondary`: "I'll pull 6 clips of 30–60 s from this 52-min episode, reframe them to 9:16 and caption them." In Edit mode it is shown, not gated. It is gated only above the credit or removal thresholds (01 §5), and then shown as a "Go ahead" ChoiceCard.
2. **Live line while running.** Collapsed to one line: live dot · WorkingText "Scoring 214 moments" · funnel counter in mono "· 6 strong so far" · elapsed time in mono `fg-muted` right-aligned.
3. **Step groups.** A disclosure "4 steps · 0:42" (`label` `fg-secondary`, chevron). Expanded, each row is 28 px:
   - A 16 px icon: queued is a dashed ring, active is the live dot, done is a tick in `fg-muted`, failed is a rose alert, skipped is a dash.
   - A label in **past tense naming its object** once done ("Transcribed episode-12.mp4", "Found B-roll: 'city skyline at dusk'"), or present tense while active.
   - Duration in mono on the right.
   - Indent 24, no connector lines.
   - Between batches, a short prose status line may appear ("Shots are in. Laying captions on each one.").
4. **Partial findings stream in** as they arrive: a moment strip (§6.4) above the result.
5. **Result.** `ResultMessage` rules from 02 §4.6 apply, plus:
   - The summary leads with counts and ends with an editability line: "6 clips ready · 4 captioned · 2 need a look. Each clip is separate, so you can trim or swap any of them."
   - Then the version chip with **Undo** and **Compare**.
   - Then up to 3 follow-up chips generated from this result.
   - Then an **Outputs** row (rendered files, captions, thumbnails), when there are any.

Motion: a finished step dims over `fast`; the next step rises 4 px and fades in over `base`; groups fold over `base` with `in-out`.

### 6.3 Timestamp citations: Perplexity's sources become video moments

Every claim or cut in an AI reply that points at the footage carries an inline **citation chip**.

- **Look:** inline-flex, 20 px tall, `rounded-cn-xs`, `surface-active` fill, `font-cn-mono` 12 `fg-secondary`, showing the **timecode**, not a number: `12:04`. Ranges show `12:04–12:31`. Three or more citations in one sentence collapse to `12:04 +2`.
  - Why timecodes and not numbers: a timecode is information. A footnote number is not.
- **Hover** (150 ms delay) **or focus:**
  - The chip's text turns `accent-text` and its fill `accent-subtle`.
  - A popover (`surface-raised`, 280 wide) shows the frame (16:9, `.cn-media-edge`), the transcript line with the cited words on `accent-subtle`, and "Play from 12:04 ↵".
  - At the same time, an `accent/20` band marks that range on the timeline ruler.
- **Click / Enter:** seeks the player and pulses the playhead once (`highlight`). Playback does not start until the user presses play. **Shift-click / Shift+Enter:** attaches the range as a ContextChip.
- **Source strip:** when a reply cites 2 or more moments, a horizontal strip of up to 4 compact moment cards plus "+N" sits **above** the prose. It scrolls sideways on phones.
- **Select-to-act:** selecting text in a reply or the transcript shows a small floating bar: **Add to prompt** · **Show in video**.
- **Screen readers:** the chip's name is "Moment at 12 minutes 4 seconds". It is a button.

### 6.4 Moment / quote cards

This is Clipnera's core output, so it gets the most care. A card is a candidate clip, shown as a quote.

```
┌───────────────────────────────────────────────┐
│ ▌9:16 │ "It found the leak faster than I did."│  ← prose 15/24 fg, curly quotes, 3-line clamp
│ ▌poster│ Hot take · 43:50 · 0:13      Score 94 │  ← Badge neutral · mono · mono · (real score only)
│ ▌56×100│ ├──────────●────────────────────┤     │  ← 4 px source bar, amber tick at 43:50 of 50:10
└───────────────────────────────────────────────┘
```

- **Card:** `surface`, `rounded-cn-lg`, 12 padding, 12 gap. The poster is 9:16 at 56 px wide (16:9 at 96 px for landscape outputs) with `.cn-media-edge`.
- **Format tag:** one of the 11 content formats as a neutral Badge. Never coloured per format.
- **Score:** shown only when the backend scored it, as "Score 94" in mono. A ScoreRing is allowed in grid views only.
- **Source bar:** a 4 px `surface-active` track covering the source length, with a 2 px amber tick at the moment's position and an `accent/30` span for its duration. A source-level strip above a set of cards shows every moment's tick together ("3 moments found · 0:00–50:10").

| State | Look |
|---|---|
| Streaming in | `.cn-pending-sheen`, the quote appears as it streams, meta fills when known |
| Rest | As above |
| Hover / focus | Neutral hover fill; the poster plays the moment muted after 150 ms |
| Selected | 2 px `accent-border`; becomes a ContextChip |
| On timeline | Emerald tick, "On timeline at 0:14", with **Swap** and **Remove** |
| Dismissed | 50% opacity, "Hidden · Undo" |
| Failed to cut | Rose icon, reason, **Try again** |

B-roll result cards use the same frame and say where the clip landed: "Welder at work · Archival · 0:08 · Added at 0:14", with Swap and Remove.

### 6.5 The AI-change marker on the timeline

1. **Landing.** Each operation from the run flashes `animate-cn-highlight` (600 ms) on the clip it touched, as its event arrives.
2. **The AI edge.** Each changed clip then keeps a **2 px amber top edge** plus a 12 px spark glyph in the clip's label row. The glyph's screen-reader text is "Changed by Clipnera in 'Trimmed silences'".
3. **The diff chip.** When the clip is hovered, focused or selected, a floating chip (`surface-raised`, `shadow-cn-1`, 24 tall, mono `caption`) appears above it in the ruler lane and says what changed: "4.0s → 2.1s", "+ captions", "Reframed 9:16", "Swapped B-roll". The chip also has **Undo run** (ghost, 24).
4. **The run bracket.** An `accent/15` band on the ruler spans the run's changed range, labelled with the version name. Clicking it scrolls the conversation to that result.
5. **Lifetime.** Markers show only for the **latest run**. They clear on that clip's next manual edit, when the next run lands (and replaces them), or on Undo. History keeps the full record.
6. **Conflicts are not amber.** An overlap or an off-frame caption gets a 1 px dashed `danger` edge and a rose ! glyph, with the reason on hover or focus.

### 6.6 The render card

Shown in the conversation (as the result of `/export`), in the activity popover and on the Project page.

```
┌──────────────────────────────────────────────────┐
│ [poster] Opening hook                           │  label 600
│  9:16   0:42 · 1080×1920 · MP4 · ≈ 38 MB         │  caption mono fg-muted
│         ▓▓▓▓▓▓▓▓░░░░░░  58% · about 0:40 left     │  ProgressBar amber + mono
└──────────────────────────────────────────────────┘
```

| State | Look |
|---|---|
| Queued | "Waiting · 2nd in line" (only if the position is known), static poster |
| Rendering | Live dot, a **real** determinate % and time left, `.cn-pending-sheen` on the poster; "8× faster than real time" only if measured |
| Checking | WorkingText "Checking the export" (every export is verified before it is handed over) |
| Done | Emerald tick "Ready", **Download** (secondary; the page's amber action stays elsewhere), Copy link, Schedule (flag), file size |
| Failed | Rose, what happened, "Your edit is safe", **Try again** (only if retryable) |
| Expired | "Removed after 30 days · Render again" in `fg-muted` |

The export dialog that starts a render offers "Video file" first, then resolution, then a collapsed Advanced section (frame rate, quality, format). The total duration and estimated size sit above the button **"Export video"**.

---

## 7. Hero moment per screen

Each screen must nail the one thing in this table before anything else gets polish.

| Screen | Hero moment |
|---|---|
| Landing | Paste a link and type a prompt in the hero composer while signed out; the prompt survives sign-in |
| Sign in / sign up | One Google button, and the kept prompt is visibly waiting ("Kept from before you signed in") |
| Onboarding | Under 30 s to the first upload; the questions tune the starter chips, nothing more |
| App shell | Never remounts; ⌘K opens Ask from anywhere; at most 5 destinations |
| Home | The composer is the first and only thing in focus; dropping a video onto it starts work |
| New video / upload | The source chip shows the duration and the credit cost before anything is spent |
| Project (processing) | A live step with a real counter, plus moment cards streaming in before the run ends |
| Project (clips ready) | A grid of quote cards you can judge without pressing play |
| Projects list | Find any project in two keystrokes; live status on every card |
| Editor | Prompt → plan line → the timeline changes in place with AI edges → Undo is one click away |
| Clip studio (Editor on a clip) | Opens on that clip, already selected as the prompt's context chip |
| Conversation thread | Every claim cites a timecode that seeks the video |
| Timeline | AI changes are readable at a glance (edge + diff chip), and hand edits are never blocked |
| Versions / history | "View" is read-only and safe; Restore never deletes anything |
| Export dialog | The duration, size and credit cost are visible before the button |
| Render card | A real percentage, then a verified "Ready" |
| Reels | B-roll results say where they landed, with Swap right on the card |
| Library: browse | Hover preview on the footage within 150 ms; duration-first meta |
| Library: uploads | Upload progress inline in the grid; readable names, never hashes |
| Library: collections | Add to a collection from any tile in one move (menu or drag) |
| Library: trash | Restore in one click; the days left are shown on every item |
| Brand kit | Changes preview live on your own footage (caption sample on a real frame) |
| Publish (scheduler) | A week view where every post shows its clip poster and platform mark |
| Publish analytics | One honest number per clip, with no fake trends when data is missing |
| Settings: account | Theme (System / Light / Dark) and data controls findable through Search settings |
| Settings: workspace | Member roles readable in one table |
| Settings: billing & credits | Credits left, what an edit costs, and buying a pack in two clicks |
| Settings: connections | Connection health and the 7-day auto-disconnect date always visible |
| Settings: notifications | Each toggle says exactly what will arrive and where |
| Pricing / plans | Monthly / Yearly toggle with the savings stated; the credit amount is chosen inside the card |
| Notifications drawer | Every row links to the thing it's about; Clear all can be undone |
| Credits popover | Plan and pack credits separated, plus credits held for running work |
| Ask dialog (⌘K) | `/go` reaches any project or page; nothing runs until Send |
| Admin | Dense, compact tables with filters that survive reload |
| Errors / 404 | What happened, what's safe, one action — inside the shell |

---

## 8. Mobile summary (≤ 767 px)

- Bottom tab bar; a composer at the bottom within thumb reach.
- Every overlay is a sheet.
- The source strip and chip rows scroll sideways.
- Card ⋯ menus are always visible, and long-press selects.
- Swipe is never the *only* way to do something.
- The Editor follows §5.7.

---

## 9. Where the studies disagree, and the ruling

| # | Topic | Perplexity | Lovable (+v0/Bolt) | Cardboard | **Ruling** |
|---|---|---|---|---|---|
| 1 | UI typeface | FK Grotesk | Camera Plain (variable, 450/480) | Geist + Geist Mono | **Plus Jakarta Sans + JetBrains Mono**, one family for all UI; Syne only for the wordmark (§3.1) |
| 2 | Chat position in the workspace | Right rail (Comet) | **Left** | **Right**, with tools on the left | **Right, full height.** Footage first in reading order; left holds the sources that feed the timeline (NLE habit); matches the existing mockup |
| 3 | Composer radius | 16 | 28 (v0 12, Bolt 24) | — | **24 hero, 16 docked** |
| 4 | Composer width | ~768 column | 608 (v0 690, Bolt 672) | — | **672** |
| 5 | Composer edge | Hairline | Ring + large shadow + glow halo | Sweep while working | **Hairline `border-strong` + shadow-2 in the hero placement; no glow; the amber working edge from Cardboard** |
| 6 | Landing backdrop | Plain | Animated rainbow ambient | Dark plain | **Plain `bg`.** Lovable's "ember glow" is rejected: it breaks the no-glow rule and the amber budget |
| 7 | Card radius | 12 | 16 | 12–16 | **12** (denser tool; 16 is for dialogs) |
| 8 | Clip-block radius | — | — | 4 | **4** (02 said 6) |
| 9 | Hover model | — | 8% / 12% overlay, instant on, 150 ms off | Fill steps | **Baked fills on neutrals, `.cn-state` overlay elsewhere; 6% / 10%; instant on, 120 ms off** (§2.4) |
| 10 | Motion durations | Not found | Hover-off 150; v0 panel 500 | **120 / 180 / 280**, 0 when reduced | **120 / 180 / 280** (+120 stream, 600 highlight). Replaces 150–250 |
| 11 | Working shimmer | — | 1.8 s | composer sweep 1.6 s, sheen 3.6 s, breathe 2.5 s | Text shimmer **2.4 s** (calmer), edge sweep **1.6 s**, sheen **3.6 s**, live dot 1.6 s |
| 12 | Frame-check cue | — | — | Fixed 2.6 s scrim | **Same scrim, tied to the real check step**, never a fixed timer |
| 13 | Surface steps | Paper-flat, borders | 4 lighter-as-raised steps | 5–6 neutral steps, gutters | **Six-step ladder with stage and sunken; `surface-raised` lifted to #202020; gutters between panels** |
| 14 | Body text colour | Primary | Tertiary (dim) | Primary | **`fg` in the app**; dim only for marketing sublines |
| 15 | AI answer type | 16 px / 1.63, 768 column | — | 12–14 dense | **`prose` 15/24** in a 384 panel; 16/24 in the Ask dialog |
| 16 | Citation form | Numbered chips | — | — | **Timecode chips** (`12:04`) that seek the video |
| 17 | Plan before work | Clarify broad queries first | Plan mode | One sentence with counts, not gated | **One sentence with counts, shown not gated**; one clarifying ChoiceCard only for vague prompts above the credit threshold; Plan mode kept |
| 18 | Step summary wording | "Completed 2 steps" | Details view | "Ran 5 commands" | **"4 steps · 0:42"**; past-tense rows that name their object |
| 19 | Mode / intent control | Intent pill in the box | "Build ▾" pill | Model and aspect pickers | **Pill (Edit / Ask / Plan) in the Editor; none on Home** (format is AI-picked); never a model picker |
| 20 | Suggestions under the home box | Contextual shortcuts | v0 chips + refresh | Template chips | **4 contextual chips**, hidden while typing, no refresh |
| 21 | Home below the fold | Continue / widgets | Project sheet with tabs | Recent row with "Start empty" first | **A Recent row (3–4 cards)**; no sheet, no feed, no "Start empty" (Clipnera needs footage) |
| 22 | Drop target on Home | — | v0 drop overlay | Separate large drop zone | **The composer is the drop zone**, with a full-box overlay on drag |
| 23 | Timeline colours | — | — | A hue per clip type, amber for collisions | **Neutral clips; icons and track names carry the kind; amber = AI change and selection; rose = conflict** |
| 24 | Settings container | Avatar menu | Account settings as a dialog (⌘.), workspace as a page | Sidebar item | **Full page with section nav and Search settings**; entry from the avatar menu |
| 25 | Sidebar | ≤ 5 items, collapses to icons | ~260 wide, many groups, hover peek | Collapsible rail | **240 / 56 rail, ≤ 5 destinations, hover peek on recents, empty groups hidden** |
| 26 | Send button | Round arrow | Round arrow | — (Bolt: "Build now" pill) | **Round arrow**; it names its action in the tooltip and becomes Stop / Queue while running |
| 27 | "Improve prompt" | — | — | Word-by-word rewrite | **Not in v1** (owner question, §11) |
| 28 | Voice input | Hold-to-talk mic | Mic with waveform | — | **Slot reserved, not built** (owner question) |
| 29 | Jump-to-message highlight | — | 1.6 s after a 0.8 s delay | — | **600 ms** (`highlight`), no delay |

---

## 10. What changed in code, and requests

**`frontend/lib/design/tokens.ts`** (and the regenerated `app/tokens.css`). Every existing name still works. New names are additive.

| Change | Detail |
|---|---|
| Colour value | `surface-raised` dark `#1c1c1c` → `#202020` |
| New colours | `surface-sunken` (#111111 / #f5f5f5), `stage` (#000000 both), `state-layer` (#ffffff / #0a0a0a). They map to Tailwind `bg-cn-*` automatically |
| New `stateLayer` | Per-theme `--cn-state-hover`, `--cn-state-press` and `--cn-state-media-edge` |
| Type | New `prose` (15/24). Display tracking −0.025 / −0.03 / −0.04em |
| Radius | New `3xl` 24 px. `xl` / `2xl` comments updated to their new uses |
| Control height | New `xs` 28 px |
| New `layout` | Shell, Home, Settings and Editor dimensions (§5), also emitted as `--cn-layout-*` |
| Motion values | `fast` 150 → 120, `base` 200 → 180, `slow` 250 → 280 |
| Motion additions | New easing `standard`. New `loop` periods (shimmer 2400, sweep 1600, pulse 1600, sheen 3600) as `--cn-loop-*` |
| Breakpoint | New `wide: 1440` (JS only) |
| Generated CSS utilities | `.cn-state` (with a registered `--cn-state-opacity`), `.cn-media-edge`, `.cn-working-edge`, `.cn-pending-sheen`. All are opt-in and static under reduced motion. `.cn-shimmer-text` now reads `--cn-loop-shimmer` |

Checks: `node --test lib/` passes (30/30). `npx tsc --noEmit -p .` shows no errors in `lib/design` or `tailwind.config.ts`.

**Requests**

- **Platform** (`tailwind.config.ts`):
  - Add `screens: { wide: '1440px' }`.
  - Make `cn-sweep` use `cn.loop.sweep` and `cn-pulse` use `cn.loop.pulse` instead of the literals 1.4 s / 1.6 s.
- **Platform** (`app/layout.tsx`): drop `@fontsource/syne/800.css` if the wordmark doesn't need it.
- **Design System engineer** (`components/ui`):
  - PromptBar hero → `rounded-cn-3xl`, `surface-raised` fill; mode SegmentedControl → mode pill (§6.1).
  - Adopt `.cn-state` on primary, danger and media.
  - Add `.cn-media-edge` to `VideoThumb`.
  - StepList summary wording "N steps · 0:42" (§6.2).
  - New components: CitationChip, MomentCard, RenderCard, the TimelineChangeMarker (diff chip + AI edge), and the composer's working edge.
  - Check any component that hard-codes 150/200/250 ms instead of `duration.*`.
- **Screen spec `screens/01` §5.1** is superseded on sidebar width (240, not 256), items (≤ 5) and tab bar height (56).

---

## 11. Open questions for the owner

| # | Question | Default if unanswered |
|---|---|---|
| 1 | Sidebar at 5: Reels folds into Projects as a tab, and Analytics into Publish. OK? | Yes |
| 2 | Conversation on the **right** in the Editor (Cardboard), not the left (Lovable). OK? | Right |
| 3 | Voice dictation in the composer (browser speech API, no backend). Build it in Wave 6? | No; slot reserved |
| 4 | "Improve prompt" (rewrites a vague prompt; may cost a little). Wanted? | Not in v1 |
| 5 | Syne used only for the wordmark (no more Syne headings on marketing pages). OK? | Yes |
| 6 | Motion window 120–280 ms replaces 150–250 ms everywhere, including the legacy-adjacent `components/ui`. OK? | Yes |
