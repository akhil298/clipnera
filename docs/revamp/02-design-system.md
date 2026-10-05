# Clipnera UI revamp — Wave 2, part 1: design system

Date: 3 October 2026. Builds on [00-audit.md](00-audit.md), [01-experience-principles.md](01-experience-principles.md) and the slice audits in [audit/](audit/).

This document is the contract for every screen Wave 2 and later waves design. It covers tokens, components, motion, writing and accessibility. Where a component exists in code, the spec names its file; where it does not yet, the spec is the brief for whoever builds it.

**What exists in code after this wave (all new, nothing wired into a screen):**

| Kind | Where |
|---|---|
| Token source of truth | `frontend/lib/design/tokens.ts` |
| Generated CSS variables | `frontend/app/tokens.css` (one `@import` line added to `globals.css`) |
| Tailwind keys | `cn-*` keys added to `frontend/tailwind.config.ts` |
| Shared helpers | `frontend/lib/design/` — `styles.ts`, `motion.ts`, `layers.ts`, `focus.ts`, `useAnchoredPosition.ts`, `useControllableState.ts`, `useAutosize.ts`, `useReducedMotion.ts`, `refs.ts` |
| Components | 31 new files in `frontend/components/ui/` (list in §11) |
| Gallery | `/design-system` (`frontend/app/design-system/`), development only |

**Locked decisions this document works within:** amber on neutral, with emerald, rose and sky for status and no other hue; dark and light designed, dark ships first and is the default; no assistant persona or model picker; interface motion 150–250 ms with one 600 ms highlight; WCAG 2.2 AA.

---

## 1. Principles

1. **Calm by default, amber with intent.** Neutral surfaces carry the interface. Amber marks the one primary action, the current selection and live work. If two things on a screen are amber, one of them is wrong.
2. **The footage is the brightest thing on screen.** Chrome stays low-contrast and flat so video, posters and captions read first. No gradients, glows or glass on chrome.
3. **One way to do each thing.** One button, one dialog, one status language, one focus ring. A screen that needs something new adds it here first.
4. **State is always visible and always true.** Every control shows hover, focus, pressed, disabled, loading and error. Loading never hides behind a bare spinner (01 §3.1); progress names the step.
5. **Keyboard first, pointer equal.** Everything reachable and operable by keyboard, with a visible ring, in a logical order. Pointer users get the same affordances, never extra hidden ones.
6. **Quiet motion that explains.** Motion shows where something came from or that something changed. It never decorates, and it disappears under reduced motion.
7. **Plain words.** Sentence case, verbs on buttons, numbers over adjectives, no jargon (§7).
8. **Tokens, not values.** Screens use `cn-*` tokens. A raw hex, a `text-[11px]` or a `z-[60]` in new code is a review comment.

---

## 2. Tokens

Source: `frontend/lib/design/tokens.ts`. Every CSS variable is namespaced `--cn-*`; the legacy variables in `globals.css` (`--border`, `--primary`, …) are untouched, so no existing screen changes.

### 2.1 Colour

Colours are semantic. Screens never use a scale step (`neutral-800`) for a role that has a token.

| Token | Dark (default) | Light | Role |
|---|---|---|---|
| `bg` | `#0a0a0a` neutral-950 | `#fafafa` neutral-50 | The page |
| `surface` | `#171717` neutral-900 | `#ffffff` | Cards, panels, sidebars |
| `surface-raised` | `#1c1c1c` | `#ffffff` | Menus, popovers, dialogs, toasts |
| `field` | `#111111` | `#ffffff` | Inside inputs and the prompt bar |
| `surface-hover` | `#262626` neutral-800 | `#f5f5f5` neutral-100 | Hover fill for rows and quiet buttons |
| `surface-active` | `#2e2e2e` | `#e5e5e5` neutral-200 | Pressed or selected neutral fill |
| `overlay` | `#000000` | `#0a0a0a` | Scrim; always with alpha (`bg-cn-overlay/60`) |
| `border` | `#262626` | `#e5e5e5` | Dividers, card edges (decorative) |
| `border-strong` | `#404040` neutral-700 | `#d4d4d4` neutral-300 | Emphasised edges, floating panels |
| `control-border` | `#6b6b6b` | `#8a8a8a` | Edges that identify a control (3:1) |
| `fg` | `#fafafa` | `#0a0a0a` | Primary text |
| `fg-secondary` | `#a3a3a3` neutral-400 | `#525252` neutral-600 | Supporting text |
| `fg-muted` | `#8c8c8c` (the project's lightened neutral-500) | `#6b6b6b` | Hints, meta, placeholders |
| `fg-disabled` | `#525252` | `#a3a3a3` | Disabled text (exempt from contrast) |
| `accent` | `#f59e0b` amber-500 | `#f59e0b` | Primary fill, selection, live dot |
| `accent-hover` | `#fbbf24` amber-400 | `#fbbf24` | Primary hover |
| `accent-pressed` | `#d97706` amber-600 | `#d97706` | Primary pressed |
| `accent-fg` | `#0a0a0a` | `#0a0a0a` | Text and icons on amber |
| `accent-text` | `#fbbf24` amber-400 | `#b45309` amber-700 | Amber text and links on neutral |
| `accent-subtle` | `#362a15` | `#fffbeb` amber-50 | Selected chip, accent badge background |
| `accent-border` | `#f59e0b` | `#b45309` | Edge of a checked or selected control |
| `success` / `-text` / `-subtle` | emerald-500 / emerald-400 / `#162e26` | emerald-500 / emerald-700 / emerald-50 | Ready, done |
| `danger` / `-text` / `-subtle` | rose-500 / rose-400 / `#361d21` | rose-500 / rose-700 / rose-50 | Failed, destructive, errors |
| `danger-solid` / `-hover`, `on-danger` | rose-600 / rose-700, white | same | Destructive button |
| `info` / `-text` / `-subtle` | sky-500 / sky-400 / `#162b34` | sky-500 / sky-700 / sky-50 | Scheduled, informational |
| `focus` | `#fbbf24` amber-400 | `#b45309` amber-700 | Focus ring |

**Why these choices**
- **Three intermediate neutrals** (`#1c1c1c`, `#111111`, `#2e2e2e`) give dark mode elevation without shadows doing the work. They are neutral, not a new hue. `#2e2e2e` equals today's legacy `--border`, so it already reads as "Clipnera grey".
- **`control-border` exists because WCAG 1.4.11** needs the edge that identifies a control (an input, checkbox, switch track) at 3:1 against its surroundings. Decorative card edges do not, so they stay soft.
- **Light theme amber text is amber-700.** Amber-400/500 text on white is 1.7–2.2:1. Amber-700 is still amber; the fill stays amber-500 in both themes so the brand does not shift.
- **Errors are rose only.** The audit found rose and red both used for failure (P-12). `red-*` is retired.
- **Violet is retired** (audit P-11): `StatusPill`'s `ai` tone becomes `accent`; violet decorations become neutral or accent. Platform brand colours (YouTube red, Instagram gradient) appear **only on the platform mark itself**, never on buttons, cards or charts.
- **Destructive fill is rose-600**, not rose-500: white on rose-500 is 3.7:1.

**Contrast, measured** (WCAG 2.x relative luminance; script output, not estimates). Every pair a component actually uses is listed.

**Dark (default)**

| Foreground | on | Values | Ratio | Needs | Use |
|---|---|---|---|---|---|
| `fg` | `bg` | #fafafa / #0a0a0a | 18.97:1 | 4.5:1 pass | Body text |
| `fg` | `surface-raised` | #fafafa / #1c1c1c | 16.33:1 | 4.5:1 pass | Text in menus, dialogs |
| `fg-secondary` | `bg` | #a3a3a3 / #0a0a0a | 7.85:1 | 4.5:1 pass | Supporting text |
| `fg-secondary` | `surface-raised` | #a3a3a3 / #1c1c1c | 6.76:1 | 4.5:1 pass |  |
| `fg-secondary` | `surface-hover` | #a3a3a3 / #262626 | 6.00:1 | 4.5:1 pass | Hovered row |
| `fg-muted` | `bg` | #8c8c8c / #0a0a0a | 5.89:1 | 4.5:1 pass | Hints, meta, placeholders |
| `fg-muted` | `surface` | #8c8c8c / #171717 | 5.33:1 | 4.5:1 pass |  |
| `fg-muted` | `surface-raised` | #8c8c8c / #1c1c1c | 5.07:1 | 4.5:1 pass |  |
| `fg-muted` | `field` | #8c8c8c / #111111 | 5.62:1 | 4.5:1 pass | Placeholder |
| `fg-muted` | `surface-hover` | #8c8c8c / #262626 | 4.50:1 | 4.5:1 pass |  |
| `accent-fg` | `accent` | #0a0a0a / #f59e0b | 9.22:1 | 4.5:1 pass | Primary button label |
| `accent-fg` | `accent-pressed` | #0a0a0a / #d97706 | 6.21:1 | 4.5:1 pass | Pressed primary |
| `accent-text` | `bg` | #fbbf24 / #0a0a0a | 11.86:1 | 4.5:1 pass | Amber links and labels |
| `accent-text` | `surface` | #fbbf24 / #171717 | 10.74:1 | 4.5:1 pass |  |
| `accent-text` | `accent-subtle` | #fbbf24 / #362a15 | 8.39:1 | 4.5:1 pass | Selected chip, accent badge |
| `success-text` | `surface` | #34d399 / #171717 | 9.33:1 | 4.5:1 pass |  |
| `success-text` | `success-subtle` | #34d399 / #162e26 | 7.52:1 | 4.5:1 pass | Success badge |
| `danger-text` | `surface` | #fb7185 / #171717 | 6.66:1 | 4.5:1 pass | Error text |
| `danger-text` | `danger-subtle` | #fb7185 / #361d21 | 5.76:1 | 4.5:1 pass | Danger badge |
| `on-danger` | `danger-solid` | #ffffff / #e11d48 | 4.70:1 | 4.5:1 pass | Destructive button |
| `on-danger` | `danger-solid-hover` | #ffffff / #be123c | 6.29:1 | 4.5:1 pass |  |
| `info-text` | `surface` | #38bdf8 / #171717 | 8.37:1 | 4.5:1 pass |  |
| `info-text` | `info-subtle` | #38bdf8 / #162b34 | 6.86:1 | 4.5:1 pass | Scheduled badge |
| `control-border` | `bg` | #6b6b6b / #0a0a0a | 3.72:1 | 3:1 pass | Input, checkbox, switch edge |
| `control-border` | `surface` | #6b6b6b / #171717 | 3.36:1 | 3:1 pass |  |
| `control-border` | `surface-raised` | #6b6b6b / #1c1c1c | 3.20:1 | 3:1 pass |  |
| `control-border` | `field` | #6b6b6b / #111111 | 3.54:1 | 3:1 pass |  |
| `accent-border` | `surface` | #f59e0b / #171717 | 8.35:1 | 3:1 pass | Checked control edge |
| `focus` | `bg` | #fbbf24 / #0a0a0a | 11.86:1 | 3:1 pass | Focus ring |
| `focus` | `surface` | #fbbf24 / #171717 | 10.74:1 | 3:1 pass |  |
| `focus` | `surface-raised` | #fbbf24 / #1c1c1c | 10.21:1 | 3:1 pass |  |

**Light**

| Foreground | on | Values | Ratio | Needs | Use |
|---|---|---|---|---|---|
| `fg` | `bg` | #0a0a0a / #fafafa | 18.97:1 | 4.5:1 pass | Body text |
| `fg` | `surface-raised` | #0a0a0a / #ffffff | 19.80:1 | 4.5:1 pass | Text in menus, dialogs |
| `fg-secondary` | `bg` | #525252 / #fafafa | 7.49:1 | 4.5:1 pass | Supporting text |
| `fg-secondary` | `surface-raised` | #525252 / #ffffff | 7.81:1 | 4.5:1 pass |  |
| `fg-secondary` | `surface-hover` | #525252 / #f5f5f5 | 7.17:1 | 4.5:1 pass | Hovered row |
| `fg-muted` | `bg` | #6b6b6b / #fafafa | 5.11:1 | 4.5:1 pass | Hints, meta, placeholders |
| `fg-muted` | `surface` | #6b6b6b / #ffffff | 5.33:1 | 4.5:1 pass |  |
| `fg-muted` | `surface-raised` | #6b6b6b / #ffffff | 5.33:1 | 4.5:1 pass |  |
| `fg-muted` | `field` | #6b6b6b / #ffffff | 5.33:1 | 4.5:1 pass | Placeholder |
| `fg-muted` | `surface-hover` | #6b6b6b / #f5f5f5 | 4.89:1 | 4.5:1 pass |  |
| `accent-fg` | `accent` | #0a0a0a / #f59e0b | 9.22:1 | 4.5:1 pass | Primary button label |
| `accent-fg` | `accent-pressed` | #0a0a0a / #d97706 | 6.21:1 | 4.5:1 pass | Pressed primary |
| `accent-text` | `bg` | #b45309 / #fafafa | 4.81:1 | 4.5:1 pass | Amber links and labels |
| `accent-text` | `surface` | #b45309 / #ffffff | 5.02:1 | 4.5:1 pass |  |
| `accent-text` | `accent-subtle` | #b45309 / #fffbeb | 4.84:1 | 4.5:1 pass | Selected chip, accent badge |
| `success-text` | `surface` | #047857 / #ffffff | 5.48:1 | 4.5:1 pass |  |
| `success-text` | `success-subtle` | #047857 / #ecfdf5 | 5.21:1 | 4.5:1 pass | Success badge |
| `danger-text` | `surface` | #be123c / #ffffff | 6.29:1 | 4.5:1 pass | Error text |
| `danger-text` | `danger-subtle` | #be123c / #fff1f2 | 5.72:1 | 4.5:1 pass | Danger badge |
| `on-danger` | `danger-solid` | #ffffff / #e11d48 | 4.70:1 | 4.5:1 pass | Destructive button |
| `on-danger` | `danger-solid-hover` | #ffffff / #be123c | 6.29:1 | 4.5:1 pass |  |
| `info-text` | `surface` | #0369a1 / #ffffff | 5.93:1 | 4.5:1 pass |  |
| `info-text` | `info-subtle` | #0369a1 / #f0f9ff | 5.57:1 | 4.5:1 pass | Scheduled badge |
| `control-border` | `bg` | #8a8a8a / #fafafa | 3.31:1 | 3:1 pass | Input, checkbox, switch edge |
| `control-border` | `surface` | #8a8a8a / #ffffff | 3.45:1 | 3:1 pass |  |
| `control-border` | `surface-raised` | #8a8a8a / #ffffff | 3.45:1 | 3:1 pass |  |
| `control-border` | `field` | #8a8a8a / #ffffff | 3.45:1 | 3:1 pass |  |
| `accent-border` | `surface` | #b45309 / #ffffff | 5.02:1 | 3:1 pass | Checked control edge |
| `focus` | `bg` | #b45309 / #fafafa | 4.81:1 | 3:1 pass | Focus ring |
| `focus` | `surface` | #b45309 / #ffffff | 5.02:1 | 3:1 pass |  |
| `focus` | `surface-raised` | #b45309 / #ffffff | 5.02:1 | 3:1 pass |  |

Notes:
- `fg-muted` on `surface-hover` (dark) is 4.50:1, exactly the floor. Do not darken `fg-muted` or lighten `surface-hover`.
- `fg-muted` on `surface-active` (dark) is 4.0:1: never put muted text on a pressed fill; use `fg-secondary`.
- Amber fill on white is 2.2:1. A primary button is identified by its text (9.2:1), which is allowed; anything identified by the amber alone (a checked box, a selected chip) also gets `accent-border` (5:1).
- Dots in badges are decorative: the word carries the meaning.

**Mapping from today's classes** (for Wave 2 screen work; nothing has been migrated):

| Today | Token class |
|---|---|
| `bg-neutral-950` | `bg-cn-bg` |
| `bg-neutral-900` (cards) | `bg-cn-surface` |
| `bg-neutral-900`/`950` in menus | `bg-cn-surface-raised` |
| `hover:bg-neutral-800` | `hover:bg-cn-surface-hover` |
| `border-neutral-800` | `border-cn-border` |
| `border-neutral-700` on inputs | `border-cn-control-border` |
| `text-white`, `text-neutral-100` | `text-cn-fg` |
| `text-neutral-300`/`400` | `text-cn-fg-secondary` |
| `text-neutral-500` | `text-cn-fg-muted` |
| `bg-amber-500 text-neutral-950` | `bg-cn-accent text-cn-accent-fg` (or `<Button>`) |
| `text-amber-300`/`400` | `text-cn-accent-text` |
| `bg-amber-500/10` | `bg-cn-accent-subtle` |
| `text-rose-300`/`red-400` | `text-cn-danger-text` |
| `violet-*`, `fuchsia-*`, `purple-*` | `accent` or neutral, per screen |

The legacy `* { border-border }` rule (default border colour `#2e2e2e`) stays. Token components always set an explicit border colour, so they never rely on it.

### 2.2 Typography

**Faces** — no new font, all already self-hosted:

| Face | Token | Use | Why |
|---|---|---|---|
| Plus Jakarta Sans | `font-cn-sans` | All UI text | Already the body face; open apertures and a tall x-height hold up at 12–14 px on dark; 400–800 loaded |
| Syne | `font-cn-display` | Wordmark, marketing display headings (32 px and up) only | It is the brand's wordmark face; too wide and quirky for UI text |
| JetBrains Mono | `font-cn-mono` | Timecodes, durations, credits, counts, shortcuts | Fixes audit P-13 (`font-mono` system stack vs JetBrains): one mono everywhere. Always with `tabular-nums` |

Caption faces (Anton, Bangers, …) are content, not UI, and stay out of the token set.

**Scale** (`text-cn-*`; each step carries its line height):

| Token | Size / line | Weight | Use |
|---|---|---|---|
| `caption` | 12 / 16 | 500 | Meta, badges, timecodes. **The floor for anything a user must read.** |
| `label` | 13 / 18 | 500–600 | Controls, table cells, dense panels |
| `body` | 14 / 20 | 400 | App default |
| `body-lg` | 16 / 24 | 400 | Prompt bar (hero), marketing body, mobile inputs (16 px stops iOS zoom) |
| `title-sm` | 18 / 26 | 600 | Card and dialog titles |
| `title` | 20 / 28 | 600 | Section headings, mobile page titles |
| `title-lg` | 24 / 32 | 700 | Page titles (`PageHeader`) |
| `display-sm` | 32 / 40 | 700 | Home hero on mobile |
| `display` | 48 / 56 | 700 | Home hero |
| `display-lg` | 64 / 68 | 700 | Marketing hero |

Display steps carry negative tracking (−0.02 to −0.03 em). Rules: sentence case everywhere; no all-caps labels (the audit counted many `uppercase tracking-wider` headings — they become `caption` in `fg-muted`); never below 12 px (audit P-15 found 400+ uses of 9–11.5 px); prose at most 70 characters wide.

### 2.3 Spacing

A 4 px grid using Tailwind's own steps (0.5, 1, 1.5, 2, 3, 4, 5, 6, 8, 10, 12, 16 → 2–64 px). Arbitrary values (`px-[18px]`, `py-[50px]`) are not used.

| Context | Value |
|---|---|
| Inside a control | 8–14 px horizontal |
| Between related controls | 8 px (`gap-2`) |
| Inside a card | 16 px (`p-4`); 24 px for roomy cards |
| Between groups in a panel | 24 px |
| Between page sections | 40–48 px |
| Page gutter | 16 px phone, 24 px tablet, 32 px desktop |

**Control heights:** `sm` 32 px, `md` 36 px (default), `lg` 44 px (phones, primary actions). Every target is at least 24×24 px (WCAG 2.5.8); on touch layouts primary targets are 44 px.

### 2.4 Radius

| Token | Value | Use |
|---|---|---|
| `rounded-cn-xs` | 4 px | Kbd, checkbox |
| `rounded-cn-sm` | 6 px | Small buttons, menu items, chips in bars |
| `rounded-cn-md` | 8 px | Buttons, inputs |
| `rounded-cn-lg` | 12 px | Cards, menus, popovers, toasts |
| `rounded-cn-xl` | 16 px | Dialogs, drawers, panels |
| `rounded-cn-2xl` | 20 px | Home prompt bar |
| `rounded-cn-full` | pill | Chips, badges, switches, avatars |

Replaces the 11+ radii found in the audit. Nested radius = outer minus padding (a 12 px card with 4 px padding holds 8 px items).

### 2.5 Elevation

Dark mode shows depth through surface lightness first, then a hairline, then shadow.

| Level | Surface | Shadow token | Use |
|---|---|---|---|
| 0 | `bg` / `surface` | none | Page, cards at rest |
| 1 | `surface` | `shadow-cn-1` | Hovered interactive card, switch thumb, selected segment |
| 2 | `surface-raised` + `border-strong` | `shadow-cn-2` | Menus, popovers, tooltips, toasts, hero prompt bar |
| 3 | `surface-raised` + `border-strong` | `shadow-cn-3` | Dialogs, drawers |

Shadows are themed (`--cn-shadow-1..3`): heavier black in dark, soft neutral in light.

### 2.6 Layers (z-index)

Every overlay renders in a portal on `<body>`, so these are global values. Classes: `z-cn-*`.

| Layer | Value | What |
|---|---|---|
| `base` | 0 | Page |
| `raised` | 10 | Inside a component: sticky table header, buttons above a card's link overlay |
| `sticky` | 100 | App header, landing navbar, editor top bar, mobile tab bar |
| `banner` | 200 | Cookie notice, plan banner |
| `drawer` | 300 | Drawers, sheets, mobile navigation |
| `dialog` | 400 | Modal dialogs |
| `popover` | 500 | Menus, popovers, select lists, slash menu — above a dialog that opened them |
| `toast` | 600 | Toasts |
| `tooltip` | 700 | Tooltips |
| `skiplink` | 800 | Skip link |

**The z-50 collision (audit 03 §4).** The sign-in modal and the sticky navbar are both `z-50`, so the navbar can paint over the modal's scrim. Under this scale the navbar is `sticky` (100) and the modal is `dialog` (400) in a portal: the collision cannot happen. The cookie notice moves from `z-[60]` (above every dashboard modal, P-19) to `banner` (200), under every overlay. Legacy mapping for migration: `z-10/20` → `raised`, `z-30/40` → `sticky`, `z-50` modals → `dialog`, `z-50` navbar → `sticky`, `z-[60]` snackbars → `toast`, `z-[60]` cookie notice → `banner`, `z-[70]` skip link → `skiplink`, `z-[1000]` Select menu → `popover`.

### 2.7 Motion tokens

| Token | ms | Use |
|---|---|---|
| `duration-cn-stream` | 120 | Streaming text word-group fade (01 §10) |
| `duration-cn-fast` | 150 | Hover, press, tooltip, step tick, page cross-fade, exits |
| `duration-cn-base` | 200 | Menus, popovers, dialogs, height collapse, tab indicator |
| `duration-cn-slow` | 250 | Drawers and sheets (they travel further) |
| `duration-cn-highlight` | 600 | An operation landing on the timeline — the one exception |

| Easing | Curve | Use |
|---|---|---|
| `ease-cn-out` | `cubic-bezier(0.16, 1, 0.3, 1)` | Anything entering or responding to input |
| `ease-cn-in` | `cubic-bezier(0.4, 0, 1, 1)` | Anything leaving |
| `ease-cn-in-out` | `cubic-bezier(0.65, 0, 0.35, 1)` | Moving or resizing in place |

Delays: tooltip 500 ms (then 0 ms for 300 ms after one closes), media hover preview 150 ms. Full spec in §6.

### 2.8 Breakpoints and layout

Tailwind defaults, restated in `tokens.ts` for JavaScript: `sm` 640, `md` 768, `lg` 1024, `xl` 1280, `2xl` 1536.

| Range | Layout |
|---|---|
| < 640 | Phone. Single column, bottom tab bar, dialogs become bottom sheets, prompt bar is a bottom sheet over the preview |
| 640–1023 | Tablet. Collapsible sidebar rail **that can expand** (audit 04: today it cannot) |
| ≥ 1024 | Desktop. Sidebar, editor three-pane layout |
| ≥ 1280 | Wide. Content max width 1280 px (app) or 1440 px (marketing); one container per area (audit 03 found four) |

No horizontal page scroll at 320 px. `overflow-x-hidden` on `<body>` (audit P-42) should be removed once screens are rebuilt, so overflow bugs surface instead of hiding.

### 2.9 Using tokens

| Need | Use |
|---|---|
| In Tailwind | `bg-cn-surface`, `text-cn-fg-muted`, `border-cn-control-border`, `text-cn-body`, `rounded-cn-lg`, `shadow-cn-2`, `z-cn-dialog`, `duration-cn-base`, `ease-cn-out`, `font-cn-mono`, `outline-cn-focus`. Alpha works: `bg-cn-accent/10` |
| In CSS | `rgb(var(--cn-surface))`, `var(--cn-radius-lg)`, `var(--cn-duration-base)` |
| In TypeScript | `import { duration, colors } from '@/lib/design/tokens'` |
| Change a token | Edit `tokens.ts`, run `node lib/design/write-tokens-css.mts`, then `npm test` (fails if `app/tokens.css` is out of date) |
| Theme | Dark on `:root`. `data-theme="light"` on any element switches that subtree; `data-theme="dark"` forces dark inside light. `color-scheme` is set only where `data-theme` is explicit, so today's screens keep their native controls |

**Dev-server note.** `next dev` on this machine (Node 26) loads `tailwind.config.ts` through Node's ESM loader, whose cache Tailwind cannot clear. The new `cn-*` utility classes therefore appear only after `next dev` is restarted. The CSS variables (`app/tokens.css`) load without a restart.

---

## 3. Core components

Common rules for every component below:
- **Focus:** the global 2 px ring with 2 px offset (`globals.css`), recoloured per theme by `focusRing` in `lib/design/styles.ts`. Never `outline-none` without a replacement; text fields with adornments ring the wrapper (`focusWithinRing`).
- **Disabled:** 50% opacity, `cursor-not-allowed`, no hover change. Prefer explaining why (hint text or tooltip on a wrapper) over a silent disabled control.
- **Loading:** never a spinner. Buttons keep their width and sweep a 2 px bar along the bottom edge; regions show skeletons; long work shows named steps.
- **Error:** rose text with an icon, linked to the control with `aria-describedby`, `aria-invalid` on the control.
- **Press:** `scale(0.98)` for 150 ms on buttons (`0.95` on icon buttons), motion-safe only.
- Every interactive element is a real `<button>`, `<a>`, `<input>` or has the full ARIA pattern. Every `<button>` has `type`.

### 3.1 Button — `components/ui/Button.tsx`

| | |
|---|---|
| Variants | `primary` (amber; one per view), `secondary` (bordered surface), `ghost` (text only, for low-emphasis and toolbars), `danger` (rose-600, destructive confirmations only) |
| Sizes | `sm` 32, `md` 36, `lg` 44 |
| Parts | optional leading icon, label, optional trailing icon |
| Also | `buttonClasses()` for a Next `<Link>` that looks like a button |

| State | Primary | Secondary | Ghost | Danger |
|---|---|---|---|---|
| Default | `accent` fill, `accent-fg` text | `surface` + `control-border` | `fg-secondary` text | `danger-solid`, white |
| Hover | `accent-hover` | `surface-hover` | `surface-hover` fill, `fg` text | `danger-solid-hover` |
| Focus | ring | ring | ring | ring |
| Active | `accent-pressed`, scale 0.98 | `surface-active` | `surface-active` | scale 0.98 |
| Disabled | 50% opacity, no pointer | same | same | same |
| Loading | label → `loadingLabel` ("Saving"), sweep bar, `aria-busy`, `aria-disabled`, clicks ignored, focus kept | same | same | same |
| Error | — (errors belong to the form or message, not the button) | | | |

A11y: label is a verb ("Export clip", not "OK"). Icon-only → IconButton. Loading uses `aria-disabled`, not `disabled`, so focus is not lost mid-action.

### 3.2 IconButton — `components/ui/IconButton.tsx`

`label` is required: it is the accessible name (via the tooltip, `aria-labelledby`) and the tooltip text. Variants `ghost` (default), `secondary`, `primary`, `danger`; sizes 32/36/44. States as Button, plus **pressed** (`aria-pressed`, `accent-subtle` fill, `accent-text` icon) for toggles such as mute or loop. Tooltip can be turned off where the label is visible nearby (dialog close).

### 3.3 Input — `components/ui/Input.tsx` (with `Field.tsx`)

Label above (`label`, 13 px semibold), control, error (if any), then hint. `leading` (decorative icon or prefix) and `trailing` (unit, clear button). Sizes 32/36/44; `lg` uses 16 px text.

| State | Look |
|---|---|
| Default | `field` fill, `control-border` edge, `fg-muted` placeholder |
| Hover | edge `fg-muted` |
| Focus | ring on the whole field |
| Disabled | `surface` fill, `border`, 60% opacity |
| Read-only | as default without hover; text selectable |
| Error | `danger-text` edge; message with icon below; `aria-invalid`; message first in `aria-describedby`, so it is read before the hint |
| Loading (async validation) | trailing `WorkingText` "Checking", never a spinner |

A11y: always a visible label, or `aria-label` when the context names it (search in a toolbar). Placeholder is an example, never the label. Required fields mark `*` visually (hidden from screen readers) and use `required`.

### 3.4 Textarea — `components/ui/Textarea.tsx`

As Input, plus auto-grow from `minRows` (3) to `maxRows` (8), then scrolls. With `maxLength`, a mono counter "12 / 120" under the field (not a live region; it would talk on every key).

### 3.5 Select (spec; rebuild of `components/ui/Select.tsx`)

Keep the existing behaviour (attached listbox, `combobox`/`listbox` roles, arrows, Home/End, Escape). Add: type-to-select, a disabled and an error state for the whole field, a visible `<label>` via `Field`, a `name` for forms, `z-cn-popover`, `floatingSurface` styling, and `useAnchoredPosition` instead of its own placement code. Then replace the 11 native `<select>`s. States as Input; the open list uses Menu's item styling with a tick on the selected option.

### 3.6 Checkbox — `components/ui/Checkbox.tsx`

A native checkbox restyled (`appearance-none`), so forms, Space and screen readers work unchanged. 16 px box, 4 px radius; the label row is the hit target (≥ 24 px tall). States: unchecked (`control-border`), hover (edge `fg-muted`), checked (`accent` fill, `accent-border` edge, `accent-fg` tick), indeterminate ("mixed", minus sign), disabled (50%), error (rose edge + message). Optional description under the label, linked by `aria-describedby`.

### 3.7 Switch — `components/ui/Switch.tsx`

`role="switch"`, `aria-checked`. For settings that **apply immediately**; inside a submitted form, use Checkbox. Track 36×20, thumb 14 px. Off: `surface-active` track with `control-border`; on: `accent` track, `accent-border` edge, dark thumb. Thumb slides 150 ms (motion-safe). Visible label (start or end) is the accessible name; `hideLabel` keeps it for screen readers only in dense toolbars.

### 3.8 Radio and SegmentedControl

**SegmentedControl** (`components/ui/SegmentedControl.tsx`, built): two to five always-visible options — prompt mode, view switch, theme. `radiogroup` with roving tab stop: Tab enters at the selection, arrows move and select. Selected segment: `surface-active` with `shadow-cn-1`.

**RadioGroup** (spec): for a vertical list of more than five options or options with descriptions (plan choice, export quality). Native radios restyled like Checkbox with a 16 px circle and an 8 px `accent` dot; same states. Group has a visible legend (`<fieldset>` + `<legend>`).

### 3.9 Chip — `components/ui/Chip.tsx`

Pill button. **Toggle chip** (`selected` set → `aria-pressed`): filters; selected = `accent-subtle` fill, `accent-border` edge, `accent-text`. **Action chip** (`selected` unset): prompt suggestions and next steps; a click fills the prompt bar and never sends (01 §4). Sizes 28/32. Disabled at 50%. Removable chips are ContextChip (§4.2).

### 3.10 Badge and StatusBadge — `components/ui/Badge.tsx`

**Badge**: static label, 20 px tall, 12 px semibold, tones `neutral`, `accent`, `success`, `danger`, `info`, optional dot or icon. Not interactive, never focusable.

**StatusBadge** is the one status language (successor to `StatusPill`):

| Status | Tone | Word |
|---|---|---|
| `processing` | accent, dot pulses (motion-safe) | Processing |
| `ready` | success | Ready |
| `failed` | danger | Failed |
| `scheduled` | info | Scheduled |
| `paused` | neutral | Paused |
| `draft` | neutral | Draft |

Prefer the live step over "Processing" wherever it is known ("Transcribing · 42 of 61 min", 01 §9).

### 3.11 Tooltip — `components/ui/Tooltip.tsx`

Supplementary text on hover (500 ms delay, 0 ms within 300 ms of the last one) and on keyboard focus (instant). Meets WCAG 1.4.13: Escape dismisses without moving focus; the pointer can move onto the tooltip; it stays until pointer or focus leaves. Not shown for touch. Text in a hidden node referenced by `aria-describedby` (or `aria-labelledby` for icon buttons), so it is read whether or not the bubble is open. 12 px, `surface-raised`, `border-strong`, `shadow-cn-2`, 6 px from the trigger, flips to stay in view. **Never** the only place information or an action lives.

### 3.12 Menu (dropdown) — `components/ui/Menu.tsx`

WAI-ARIA menu button. Trigger gets `aria-haspopup="menu"`, `aria-expanded`, `aria-controls`. Items: `menuitem`, or `menuitemcheckbox` with a tick. Keyboard: Enter/Space/↓ open on the first item, ↑ on the last; ↑↓ move, Home/End jump, typing a letter jumps to the next match; Enter selects and returns focus to the trigger; Escape closes and returns focus; Tab closes and moves on. Disabled items are shown (`fg-disabled`) and skipped. Groups use a `label` row and `separator`. Destructive items are rose and go last after a separator. Shortcuts show as Kbd, hidden from the item's name. Item states: default, hover/focus (`surface-hover` fill; keyboard focus adds an inset ring), disabled, danger (rose; focus fill `danger-subtle`), checked. Panel: `floatingSurface`, min 192 px, `z-cn-popover`, enters with `rise` (200 ms), leaves 150 ms.

### 3.13 Dialog — `components/ui/Dialog.tsx` (behaviour in `ModalLayer.tsx`)

`role="dialog"` (or `alertdialog` for confirmations that must be answered), `aria-modal`, named by its title, described by its description. Centred, max 384/512/672 px, `rounded-cn-xl`, `shadow-cn-3`, scrim `overlay/60`. On phones it is a bottom sheet with stacked full-width buttons (primary on top) and safe-area padding.

| Behaviour | Rule |
|---|---|
| Open | Focus moves to `initialFocusRef`, else `[data-autofocus]`, else the first control. Page scroll locks without layout shift |
| Inside | Tab and Shift+Tab wrap; focus cannot leave. A menu or popover opened inside takes over until closed |
| Close | Escape (newest layer only), the close button, Cancel, or a backdrop click (`dialog` only; never `alertdialog`) |
| After | Focus returns to the trigger |
| Busy | `dismissible={false}` while a required step is in flight; the primary button shows its loading state |
| Motion | Scrim fades 150 ms; panel `pop` (opacity, scale 0.98→1, y 4→0) 200 ms out-curve; exits 150 ms |

Destructive confirmation: title is a question ("Delete this clip?"), description says what is lost and what stays ("Clips already posted stay posted"), safe button gets initial focus, destructive button names the action ("Delete clip").

Proposal, not built: mark everything outside the open dialog `inert` (today: `aria-modal` + focus trap). Worth adding once the shell renders its own children (audit finding 2), because then the portal root is a known sibling.

### 3.14 Drawer / Sheet — `components/ui/Drawer.tsx`

Same behaviour as Dialog, one layer lower (`drawer`, 300), so a confirmation dialog can open from a drawer. Sides: `right` (version history, notifications, details), `left` (mobile navigation), `bottom` (phone prompt sheet, filters). Widths 320/416/576 px. Slides 250 ms out-curve, leaves 150 ms.

### 3.15 Popover — `components/ui/Popover.tsx`

Non-modal `role="dialog"` attached to a trigger (credits breakdown, filters, colour picker). Focus moves to the first control on open. Escape closes and returns focus; outside click or tabbing away closes without stealing focus. 288 px default width, 16 px padding, `floatingSurface`, `rise` motion. For a list of actions use Menu.

### 3.16 Toast — `components/ui/Toast.tsx`

`ToastProvider` at the app root, `useToast().show({ title, description, tone, action, duration })`.

| Rule | Value |
|---|---|
| Position | Bottom right (24 px inset); full width with 16 px inset on phones, above the tab bar |
| Stack | Newest at the bottom, 3 visible; later ones wait |
| Tones | neutral, success, info, danger (rose icon) |
| Duration | 6 s; danger stays until dismissed; `null` for any that must stay |
| Timer | Pauses on hover, on keyboard focus inside, and while the tab is hidden (keeps the good part of `SnackbarStack`) |
| Action | At most one ("View project", "Try again", "Undo") |
| Announce | Two persistent live regions (polite; assertive for danger) read each toast once. The visible stack is a labelled `section`, not a live region (fixes the double announcement in today's `SnackbarStack`) |
| Motion | Rise 200 ms, neighbours slide with layout (motion-safe), exit 150 ms |

Toasts confirm; they never carry the only copy of an error that needs action. Errors that block work stay in place (inline or ResultMessage).

### 3.17 Tabs — `components/ui/Tabs.tsx`

WAI-ARIA tabs with automatic activation: ←→ move and select, Home/End jump, Tab enters the panel (the panel is focusable). Two looks: `underline` (page sections such as Settings; 2 px amber indicator that slides 200 ms) and `pill` (panel switches such as Steps / Changes). Disabled tabs are skipped. Use tabs for peer views of one thing, not for steps (ProgressSteps) or filters (Chip).

### 3.18 Table (spec)

For admin lists, payments, usage and team. Semantic `<table>` with `<caption>` (visible or `sr-only`) and `scope` on headers. Header row 36 px, `caption`-size `fg-muted` labels, sticky (`z-cn-raised`) in scrolling regions; body rows 44 px, `body` text, `border` dividers, `surface-hover` on hover. Numbers right-aligned in `font-cn-mono tabular-nums`. Sortable headers are buttons with `aria-sort`. Row actions in a trailing Menu; a whole-row link uses the `cardLinkOverlay` technique. Selection uses Checkbox with a select-all (indeterminate) header. Loading: `TableSkeleton` (kept) inside a `SkeletonGroup`. Empty: compact EmptyState spanning the table. Phones: rows become stacked cards; never a horizontally scrolling table for primary data.

### 3.19 Card — `components/ui/Card.tsx`

`surface` with `border`, 12 px radius, padding `sm`/`md`/`lg`. `CardHeader` (title with chosen heading level, description, actions) and `CardFooter`. **Interactive** cards lift on hover (`border-strong`, `shadow-cn-1`) and ring when anything inside has focus; the card is never itself the click target: one real link inside carries `cardLinkOverlay` to cover the card, other controls sit above it (`z-cn-raised`). **Selected**: `accent-border`. This fixes the audit's unreachable clip cards (05 A2).

### 3.20 Skeleton — `components/ui/Skeleton.tsx`

`Skeleton` blocks are silent (`aria-hidden`) and pulse (opacity 1↔0.55, 1.6 s, motion-safe). `SkeletonGroup label="Loading projects"` is the single `role="status"` region (fixes audit P-10: 80 live regions). Skeletons mirror the real layout so nothing jumps; show them only after 300 ms, so fast loads do not flash.

### 3.21 EmptyState — `components/ui/EmptyState.tsx`

Icon (in a 48 px tile), title ("No projects yet"), one or two sentences of why and what acting gets you, one primary action, optional secondary. `compact` for panels and table bodies. Variants by cause: first use (invite to act), no results (offer to clear), error (§7.3 pattern, with retry), no permission (say who can).

### 3.22 ProgressBar and ProgressSteps — `ProgressBar.tsx`, `ProgressSteps.tsx`

**ProgressBar**: `role="progressbar"` with label and value text. Determinate whenever a number is known (width animates 200 ms); indeterminate sweeps a 40% segment (no spinner), static under reduced motion. Tones: accent (working), success (done), danger (stopped). 4 or 6 px track.

**ProgressSteps**: a fixed process with known stages (upload → transcribe → find moments → clips ready; checkout). Horizontal or vertical; markers: done (amber tick), active (`accent-subtle`, number), upcoming (muted number), failed (rose cross). `aria-current="step"` on the active one and the state in words for screen readers. For an AI run's open-ended steps use StepList (§4.5).

### 3.23 Avatar (spec; move `components/dashboard/Avatar.tsx` to `ui/`)

Circle, 24/32/40 px. Image with `alt` = person's name when it is the only name on screen, else `alt=""`. Fallback: initials on `surface-active` in `fg-secondary` (no violet; audit P-11). Workspace avatars are rounded squares (`rounded-cn-sm`) to tell them apart from people. Optional status dot uses StatusBadge colours with a 2 px `bg` ring.

### 3.24 Kbd — `components/ui/Kbd.tsx`

`<kbd>` keys in JetBrains Mono, 20 px tall, `border-strong` with an inset bottom edge. Symbols have spoken names for screen readers (⌘ → "Command", ⇧ → "Shift"; "plus" between keys). Show ⌘ on macOS and Ctrl elsewhere (the caller decides; the component renders what it is given).

### 3.25 WorkingText — `components/ui/WorkingText.tsx`

The spinner replacement: a slow light sweep across in-progress text ("Trimming 14 silences"), 2.4 s linear. Under reduced motion it is static `fg-secondary` text.

---

## 4. Prompt-experience components

These implement 01 §4–§9. All are presentational: the parent owns text, mode, contexts and run state; none fetches data.

### 4.1 PromptBar — `components/ui/PromptBar.tsx`

| Part | Spec |
|---|---|
| Context row | ContextChips above the text; with none, the placeholder says the prompt applies to the whole project |
| Text | Grows 1–6 rows (hero: 2–6), then scrolls. `body-lg` in hero, `body` docked |
| Attach | IconButton "Attach video, image, audio or link" (hidden if no handler) |
| Mode | SegmentedControl Edit / Ask / Plan |
| Hint | Credit cost when known in Edit mode ("Uses about 12 credits"; "12 credits" on phones; never truncated), else "2 waiting" while queued |
| Send | Primary IconButton (↑); disabled when empty. While running it becomes **Add to queue** |
| Stop | Secondary IconButton beside Send while running. Never clears the text |

| State | Look and behaviour |
|---|---|
| Idle, empty | `field` fill, `control-border`; Send disabled |
| Hover | edge `fg-muted` |
| Focus | ring around the whole bar |
| Typing | Send enabled. Enter sends; Shift+Enter new line; IME composition never sends |
| Running | Stop appears; Send queues; typing allowed |
| Disabled | 60% opacity (no project loaded, offline) — say why nearby |
| Error | Sending failed: the text stays; the parent renders an inline line under the bar ("Not sent. Check your connection." + Retry). Not part of the component yet |
| Hero | 20 px radius, `shadow-cn-2`, 12 px padding |
| Phone | Docked bar opens a bottom Drawer over the preview |

Placeholder copy: Edit "Describe an edit to the whole project / the selection"; Ask "Ask about …"; Plan "Describe what you want for … You approve the plan before anything changes."

`⌘K` focuses the bar from anywhere; `/` focuses it when no field has focus (01 §4; the `⌘K` move from the command palette needs the owner's confirmation, 01 §14 q1).

### 4.2 ContextChip — `components/ui/ContextChip.tsx`

Kinds and icons: clip (film), range (↔, mono timecode), caption line (captions, first words in quotes), asset (thumbnail), moment (clock, mono timecode). 28 px tall, max 256 px with truncation; optional meta (duration) in mono. Remove button 24 px, named "Remove clip Opening hook from the prompt". Screen readers hear "Clip: Opening hook". Read-only (no remove) inside a sent message. States: default, remove hover/focus, and **locked** (spec: a clip the run is working on shows a lock icon and cannot be removed until its step ends, 01 §5).

### 4.3 SlashMenu (spec)

Opens when `/` is typed at the start of a word in the PromptBar. A `listbox` attached above the bar (`z-cn-popover`, `matchWidth` from `useAnchoredPosition`), with the textarea as `combobox` (`aria-activedescendant`), so typing keeps filtering. Rows: command (mono, `/captions`), one-line description, matched characters in `fg`. ↑↓ move, Enter or Tab fill the template, Escape closes and leaves the `/` text. Selecting fills an editable template; it never sends (01 §4). Group "Go to" for `/go` navigation. Empty: "No command matches". Max 8 rows visible, then scroll.

### 4.4 ChoiceCard — `components/ui/ChoiceCard.tsx`

A question with up to four options (2×2 grid, one column on phones) and "Skip, use your best guess". Options show a number (1–4) or a small preview (poster, caption sample). Picking one continues the run; the card locks as a record (picked: `accent-border` + `accent-subtle`; others 50%). Number keys pick while the card has focus. `role="group"` named by the question.

### 4.5 StepList — `components/ui/StepList.tsx`

| Mode | Shows |
|---|---|
| Collapsed, running | One line: working text "Trimming silences · step 2 of 4 · 9 of 14 · 0:18" |
| Collapsed, done | "5 steps done · 0:42" |
| Collapsed, failed | "Stopped at step 2 of 3: Adding B-roll" |
| Expanded | Each step: icon (queued dashed circle, active amber dot, done tick, failed rose alert, skipped dash), verb+object label, progress for long steps, what it changed when done, and **Try again** on a failed step |

The header is a disclosure button (`aria-expanded`). A polite live region announces "Step 2 of 4: Trimming silences" once per step (the elapsed clock is not announced). Motion: finished step dims 150 ms; next step rises 4 px and fades in 200 ms; collapse/expand animates height 200 ms in-out.

### 4.6 ResultMessage — `components/ui/ResultMessage.tsx`

| Status | Icon | Content |
|---|---|---|
| `done` | emerald check | Summary with numbers ("Done — 3 clips trimmed, captions added."), what changed |
| `partial` | amber | Summary, a "Not done" box listing each item and why, "Try the rest" as a suggestion |
| `stopped` | neutral | What was done before Stop; completed work is kept as a version |
| `failed` | rose | What happened; what is still safe (`safeNote`); one action (Try again) |

Then: version badge (name from the prompt) with **Undo** and **Compare** beside it (01 §3.4: undo sits on the result). After undo the badge reads "Undone: …" and the button becomes **Redo**. **Details** toggles Tabs: Steps (StepList, expanded) and Changes (timeline operations in plain words). Up to three next-step Chips; a click fills the bar, does not send. The message is an `<article>` named by its summary; the status word is read first ("Partly done: …").

### 4.7 PromptQueue (spec)

Sits directly above the PromptBar while a run is active and something is queued. Header "Up next · 2". Each item: number, first line of the prompt (truncated), context chips (read-only, compact), and actions Edit (inline, Enter saves, Escape cancels), Remove, and reorder (drag handle plus Move up / Move down buttons, so it works by keyboard). An `ol` with `aria-label="Queued prompts"`; reorders are announced politely ("Moved to position 1"). Collapses to one line "2 waiting · Show" when more than two. Items run in order after the current run.

### 4.8 ActivityIndicator (spec)

Header control showing server jobs across projects (01 §9). Idle: hidden. Running: an IconButton-sized pill with an amber dot (pulse, motion-safe) and a count ("2"); its name is "2 jobs running". Opens a Popover listing each job: project name, current step as WorkingText, ProgressBar if determinate, link to the project. Done jobs move to the notification inbox. Failed jobs show a rose dot on the pill until seen.

### 4.9 QualityBadge (spec)

On the video preview, top-left, while proxies are playing: Badge `neutral` "Preview quality" on a `bg/80` backdrop. When full quality is ready the badge fades out 200 ms as the video cross-fades (01 §6). Not interactive; its tooltip-free text is enough. Hidden in screenshots and exports by definition (it is chrome).

### 4.10 VersionHistory item (spec)

Row in the history Drawer: 64×36 thumbnail (16:9; 9:16 shows a pillarboxed frame), name (editable inline by the owner), author ("You" or "Clipnera"), relative time in mono, and badges (Current, Bookmarked). Actions: **View** (opens read-only with a "Viewing an earlier version · Back to latest" bar), **Restore** (makes it newest; nothing is deleted), bookmark toggle, Menu for rename. States: default, hover (`surface-hover`), current (`accent-subtle` left edge), viewing (`accent-border`), restoring (WorkingText "Restoring"). The list is an `ol` newest first; the top bar's history count pulses once when a version is added (motion-safe). Footer note in `fg-muted`: "Restoring does not unpublish posted clips or return credits." (01 §7).

---

## 5. Media components (spec only)

### 5.1 VideoPlayer chrome

- **Layout:** controls in a bottom bar over a gradient scrim (`overlay` 0 → 60%), 44 px tall on touch, 36 px on desktop. Shown on hover, focus inside or pause; hidden 2 s after the pointer stops while playing; always shown under reduced motion and when focus is inside.
- **Controls, left to right:** play/pause (Space, K), current time / duration in mono, scrubber, mute (M) with volume slider on hover, captions toggle (C), QualityBadge, aspect/safe-area overlay toggle, full screen (F).
- **Scrubber:** `role="slider"` with `aria-valuetext="0:42 of 3:10"`; ←/→ ±1 s (Shift ±5 s), Home/End; hover shows a thumbnail and timecode; buffered range in `surface-active`, played in `accent`. 4 px track growing to 6 px on hover.
- **States:** loading (poster + `WorkingText` "Loading preview", no spinner), buffering mid-play (sweep on the scrubber), error (poster dimmed, "This video could not play. Your edit is safe." + Retry), ended (replay).
- **Proxy → full:** same frame, 200 ms cross-fade, no playhead jump (01 §6).
- **A11y:** every control a real button with a name; the player is a `group` labelled with the clip title; shortcuts listed in the shortcuts dialog; captions on by default where the clip has them.

### 5.2 Timeline track and clip

- **Track:** 48 px tall (video), 32 px (audio, text, overlay); header column 120 px with name, mute/lock IconButtons. Colours by kind, all on palette: video `surface-active`, text `accent-subtle`, audio `info-subtle`, overlay `success-subtle`. No fuchsia title lane (audit 05 D1).
- **Clip block:** 6 px radius, 1 px `border-strong`, label and duration in 12 px. Selected: `accent-border` 2 px. Locked by a running step: lock icon, 60% opacity, not draggable. **Landed by the assistant:** `animate-cn-highlight` (2 px amber outline fading over 600 ms), the one long motion. Trim handles 8 px wide, visible on hover/selection, with `cursor-ew-resize`.
- **Playhead:** 2 px `accent` line with a head; separate layer (`z-cn-raised`), updated outside React state per frame (audit 6.4).
- **Keyboard:** the timeline is a `grid`; arrows move between clips and tracks; Enter selects; `[`/`]` trim start/end to playhead; Delete removes (undoable); `,`/`.` nudge one frame. Selection becomes a Range ContextChip.
- **Zoom:** ⌘+/⌘−, pinch; keeps the playhead fixed.

### 5.3 AssetGrid

- Responsive grid: 2 columns on phones, then 3–6; 9:16 or 16:9 tiles chosen by the library filter. Virtualised beyond 60 items.
- `grid` role with roving focus (one tab stop; arrows move). Space toggles selection, Shift+arrows extend, ⌘A selects all; a selection bar shows count and bulk actions.
- Toolbar: search (Input with leading icon), filter Chips (orientation, duration, source: Clipnera library / Your uploads), sort Menu.
- States: loading (skeleton tiles in a `SkeletonGroup`), empty (EmptyState per cause), error (inline with Retry), uploading tiles with a ProgressBar.
- Drag to timeline (pointer) has a keyboard equivalent: "Add to timeline at playhead" in each tile's Menu.

### 5.4 MediaCard

- Poster (`object-cover`), duration in mono bottom-right on a `bg/80` chip, source/licence icon bottom-left with tooltip, optional score (ScoreRing kept).
- **Hover preview:** preload metadata on pointer approach (pointer within 100 px), start muted playback after 150 ms hover or keyboard focus, stop on leave; never under reduced motion or Save-Data (poster only). Cross-fade poster → video 150 ms.
- Title below in `label` (two lines max), meta in `caption` `fg-muted`.
- Interactive per Card rules: one link (open/preview) with `cardLinkOverlay`; checkbox and Menu above it. Selected: `accent-border` 2 px.
- States: default, hover (lift + preview), focus (ring + preview), selected, disabled (taken down / licence expired: 50% + reason badge), loading (skeleton), error (poster missing: neutral tile with film icon and the title, not transparent alt text as today).

---

## 6. Motion spec

Implementation: CSS transitions with `duration-cn-*`/`ease-cn-*` for state changes; `lib/design/motion.ts` presets (`fade`, `rise`, `pop`, `sheet-*`) for framer-motion enter/exit. All motion goes through `useReducedMotion()` (`lib/design/useReducedMotion.ts`) or Tailwind's `motion-safe:`.

| Moment | Spec | Reduced motion |
|---|---|---|
| Page transition | 150 ms opacity cross-fade of the content area only; the shell never re-mounts (01 §10). No slide | Instant |
| Panel open (drawer, sheet) | Slide from its edge 250 ms `ease-cn-out`; scrim fade 150 ms. Close 150 ms `ease-cn-in` | Instant show/hide |
| Dialog | Scrim fade 150 ms; panel opacity + scale 0.98→1 + y 4→0, 200 ms. Exit 150 ms | Instant |
| Menu, popover | Rise 4 px + fade, 200 ms; exit 150 ms | Instant |
| Tooltip | Fade 150 ms | Instant |
| Toast | Rise 200 ms; neighbours re-flow with layout animation | Instant, no layout animation |
| Tab indicator | Slides 200 ms (`layoutId`) | Jumps |
| Streaming text | Word groups fade in over 120 ms each; no blinking caret block | Appears sentence by sentence (01 §10) |
| Working line | `WorkingText` light sweep, 2.4 s linear loop | Static `fg-secondary` text |
| Step progress | Finished step ticks and dims 150 ms; next rises 4 px + fades 200 ms; steps fold to the summary with a 200 ms height collapse | Instant |
| Live dot | Opacity pulse 1.6 s | Still dot |
| Determinate progress | Width eases 200 ms per update | Jumps |
| Indeterminate progress | 40% segment sweeps 1.4 s | Static full track at 40% opacity |
| Operation lands on timeline | `animate-cn-highlight`: 2 px amber outline fades over 600 ms. The one exception to the 250 ms ceiling, because it says "this changed" | A static amber outline for 600 ms, then removed (meaning kept, no animation) |
| Version added | History count pulses once (scale 1→1.15→1, 250 ms) | No pulse |
| Media hover | Preload on approach; preview starts after 150 ms; poster→video cross-fade 150 ms | Poster only |
| Proxy → full quality | 200 ms cross-fade, same frame | Instant swap |
| Button press | Scale 0.98, 150 ms | None |

Rules: animate only `opacity` and `transform` (and height for collapse); no bounce or spring overshoot in interface chrome; nothing loops except live indicators (working text, live dot, indeterminate bar), and each stops under reduced motion; no sound.

**Known gap.** `hooks/usePrefersReducedMotion` starts `false` and corrects itself in an effect, so a component that mounts already open plays its entrance once under reduced motion. The new components use `lib/design/useReducedMotion.ts` (same API, `useSyncExternalStore`, right on first render). Proposal: give the hook in `hooks/` this body and delete the duplicate, making it the single motion gate the audit asked for (§5.7).

---

## 7. UX writing

### 7.1 Voice

Per 01 §11. Clipnera speaks in the first person, present tense, briefly. No persona name; the product is "Clipnera" or nothing. Calm, specific, honest about limits.

| Do | Don't |
|---|---|
| "Trimming 14 silences" | "Processing…" |
| "Done — 3 clips, captions added." | "Your amazing clips are ready! 🎉" |
| "Removed 42 seconds" | "Tightened it up a lot" |
| "I couldn't find enough footage of the product demo." | "Error: insufficient segments" |
| "Uses about 12 credits" | "This may consume credits" |

**Mechanics**
- Sentence case for everything, including buttons, titles and menu items. No Title Case, no trailing colons on labels, no ALL CAPS.
- Buttons are verbs plus object: "Export clip", "Add credits", "Delete project". Avoid "OK", "Submit", "Yes".
- Numbers as digits; durations `m:ss` (`1:07`) in mono; ranges with an en dash (`0:12 – 0:31`); credits with thousands separators (`1,240 credits`).
- Times relative under a day ("2 hours ago"), then a date ("3 Oct"); the full timestamp in a tooltip.
- Indian English spelling to match the legal pages (colour, cancelled); currency `₹` with no decimals unless paise matter.
- No exclamation marks in system text; no emoji in chrome (captions are user content and may use them).

### 7.2 Words to avoid

pipeline, processing (name the step), job (say what it is: "export", "upload"), queue (except the prompt queue the user sees), tokens, model, AI-powered, magic, agent, director, render (say "export" for the user's file, "preview" for proxies), "something went wrong", "oops", "please wait".

### 7.3 Error messages: what happened, what is safe, one action

Every error has these three parts (01 §8), in this order, in at most three short sentences.

| Situation | What happened | What is safe | One action |
|---|---|---|---|
| Upload failed | "interview.mov didn't finish uploading." | "Nothing was charged." | Try again |
| Export failed | "The export of Opening hook didn't finish." | "Your project and its versions are safe." | Try again |
| File unreadable | "I couldn't read the audio in interview.mov." | "Nothing was changed." | Replace file (and name the format to convert to) |
| Out of credits mid-run | "I paused because you're out of credits." | "The 2 steps already done are kept." | Add credits (secondary: Finish with what's done) |
| Connection lost | "Reconnecting." | "Your edit is still running." | — (none needed) |
| Validation (422) | Name the field and the rule: "That link isn't a full YouTube address." | — | Fix in place (focus moves to the field) |
| Second failure | "That didn't work twice." | "Your earlier versions are untouched." | A different suggested prompt; Contact support link |

"Something went wrong" is retired. If the cause is unknown, say what was being attempted and that it was not finished.

### 7.4 Other patterns

- **Empty states:** what is empty, why acting helps, one action. "No projects yet. Add a video or paste a link and Clipnera finds the best moments." → **Add a video**.
- **Confirmations:** title is the question ("Delete this clip?"), body is the consequence and what stays, buttons name both choices ("Keep clip" / "Delete clip").
- **Costs:** shown before the action, on or next to the button: "Export · 4 credits".
- **Limits:** state them plainly where they apply: "Restoring doesn't unpublish posted clips or return credits."
- **Loading copy:** present-tense verb plus object, never "Loading…" alone: "Loading your projects".

### 7.5 Glossary

User-facing names, decided once. Code names in brackets where they differ.

| Term | Means | Notes |
|---|---|---|
| **Project** | One source video (upload or link) and everything made from it | The thing a "folder" card is today. Use "project" in the UI |
| **Folder** | A user-made group of projects | Only if folders become real (audit owner decision 1). Until then, the word is not used |
| **Clip** | A short video cut from a project | |
| **Editor** | The timeline editing tool, with the prompt bar, for a project or a clip | Resolves the collision: today `/dashboard/editor` (tab `video_editor`) is "the new Editor" and the clip studio (tab `editor`) is also called an editor. Recommendation: "Editor" means the timeline tool only; rename code tabs to `editor` (timeline) and `clip_studio` |
| **Clip studio** | Today's per-clip screen at `/projects/:id/edit/:clipId` | Interim name until it is rebuilt on the Timeline model and becomes the Editor opened on one clip |
| **Editor page** | The public marketing page at `/editor` | Recommended to merge into `/` (audit owner decision 5); until then, link text says "See how editing works", never just "Editor" |
| **Reel** | A short video built from images or raw footage in Reels | Not a clip; a clip comes from a project |
| **Prompt** | What the user types into the prompt bar | Not "instruction", "command" or "message" in UI copy |
| **Run** | Everything Clipnera does for one prompt | Internal and in docs; the UI shows steps, not the word "run" |
| **Step** | One named part of a run ("Adding captions") | |
| **Version** | A saved state of a project, one per prompt or per group of hand edits | |
| **Undo / Restore** | Undo reverses the latest AI edit; Restore makes an older version the newest | Neither deletes anything |
| **Compare** | Before and after of a change | |
| **Preview quality** | Playback from low-resolution proxies | Never "proxy" in the UI |
| **Export** | Make the final video file | Not "render" |
| **Publish / Schedule** | Post now / post later to a connected account | |
| **Connected account** | A YouTube or Instagram account linked in Settings | Only YouTube and Instagram are named (audit decision 4) |
| **Brand kit** | Fonts, colours, logo and channel intro | |
| **Channel intro** | The short Pro intro added to exports | |
| **Credits** | What actions cost | "Plan credits" renew monthly; "pack credits" never expire |
| **Clipnera library** | Stock B-roll curated by Clipnera | vs **Your uploads** (the user's own assets). Together: "Library" |
| **Asset** | Any item in the library a prompt can use | |
| **Ask / Edit / Plan** | The three prompt modes | Capitalised as names of modes |

---

## 8. Accessibility checklist

Every screen and component must pass these before it ships. Built components already meet the items marked (built).

**Perceivable**
- [ ] Text contrast ≥ 4.5:1 (≥ 3:1 for 18 px+ bold or 24 px+). Use the token pairs in §2.1; anything not listed is measured first. (built)
- [ ] Control edges, focus rings, checked states and chart marks ≥ 3:1 against neighbours. (built)
- [ ] Colour is never the only signal: status has a word, errors have text and an icon, selected has an edge or tick. (built)
- [ ] Nothing a user must read is below 12 px.
- [ ] Every image has `alt` (empty for decoration); video has captions where the clip has them; icons are `aria-hidden` with a text name on the control. (built)
- [ ] Reflows at 320 px wide and 200% zoom with no horizontal page scroll and no clipped controls.

**Operable**
- [ ] Everything works with the keyboard alone, in a logical order; no keyboard trap except modals, which trap on purpose and release on close. (built)
- [ ] Visible focus on every focusable element, never removed without a replacement; focused elements are not hidden under sticky chrome (WCAG 2.4.11: use `scroll-margin` equal to the sticky header height). (built for components)
- [ ] Targets ≥ 24×24 px (2.5.8); 44 px for primary touch actions.
- [ ] Every drag has a non-drag alternative (2.5.7): trim by keys, reorder by buttons, add to timeline from a menu.
- [ ] Shortcuts use a modifier or can be turned off (single keys only when the timeline or player has focus).
- [ ] Toasts and auto-hiding controls pause on hover and focus; nothing important disappears on a timer. (built)
- [ ] Motion respects `prefers-reduced-motion` per §6; nothing flashes more than 3 times a second. (built)

**Understandable**
- [ ] One `h1` per page, headings in order; landmarks (`header`, `nav`, `main`, `footer`) and a skip link on every page.
- [ ] `lang="en"` on `<html>` (present); page `<title>` per route with one separator style ("Projects · Clipnera").
- [ ] Every input has a visible label; errors name the field and how to fix it, and move focus to the first invalid field on submit. (built)
- [ ] Consistent names and positions for the same thing across screens (§7.5).
- [ ] No re-authentication loses typed work (3.3.7, 3.3.8: sign-in is Google, no cognitive test).

**Robust**
- [ ] Native elements first; ARIA only to fill gaps, and then the full pattern (menu, tabs, dialog, combobox, slider, grid). (built)
- [ ] Every dialog: `role="dialog"`/`alertdialog`, `aria-modal`, a name, focus in on open, trap, Escape, focus return. (built)
- [ ] Live regions exist before their content changes and announce each message once. (built for toast and steps)
- [ ] One `role="status"` per loading area. (built)
- [ ] Tested with VoiceOver (macOS, iOS) and NVDA (Windows) on the critical flows before each wave closes, plus axe in CI (Wave 7).

---

## 9. What changed in the repository

All additive. No existing screen imports anything new, so nothing a user sees has changed.

| File | Change |
|---|---|
| `frontend/app/globals.css` | One line added at the top: `@import "./tokens.css";` |
| `frontend/app/tokens.css` | New, generated: `--cn-*` variables (dark on `:root`, light on `[data-theme="light"]`), `cn-*` keyframes, `.cn-shimmer-text`, `color-scheme` only under explicit `[data-theme]` |
| `frontend/tailwind.config.ts` | New `cn-*` keys only (colours under `cn`, font sizes, radii, shadows, z-index, durations, easings, font families, three animations). Existing keys untouched |
| `frontend/lib/design/*` | New: tokens, generator, test, helpers |
| `frontend/components/ui/*` | 31 new files; the six existing files untouched |
| `frontend/app/design-system/*` | New gallery route; `notFound()` in production; `robots: noindex` |

**Proof of no visual change:** the Tailwind output was compiled before and after with the same content. All 1,572 rules of the old output are present, byte for byte, in the new output and in the same order; the only additions are `cn-*` utilities and a few utilities used by the new files. No selector that existed before gained or lost a declaration.

---

## 10. Decisions made in this wave, and proposals

| # | Decision | Why |
|---|---|---|
| 1 | Token names are semantic (`fg-muted`, `surface-raised`), namespaced `cn-` | Themeable; cannot collide with legacy variables or Tailwind's own scales |
| 2 | Tokens live in TypeScript and the CSS is generated, guarded by a test | One source of truth for CSS, Tailwind and JS (motion durations) |
| 3 | Light theme uses amber-700 for amber text and focus | Amber-400/500 fail contrast on white; still the same hue |
| 4 | A `control-border` token at 3:1 | WCAG 1.4.11; today's input edges (neutral-800 on 900) are about 1.2:1 |
| 5 | No new font; Syne restricted to display | Already self-hosted; Syne is too wide for UI |
| 6 | 12 px type floor | Audit P-15 |
| 7 | z-index scale in hundreds with every overlay portalled | Fixes the z-50 collision and the cookie notice covering modals |
| 8 | No headless UI library | The patterns needed (dialog, menu, tabs, tooltip, popover, toast) are built and tested here in about 1,500 lines with framer-motion already installed. If Wave 3 needs a combobox with virtualised options or a date picker, reconsider `@radix-ui/react-*` primitives (unstyled, accessible, tree-shakeable) rather than writing those |
| 9 | `SegmentedControl` and `WorkingText` added beyond the brief | The prompt bar's mode switch and the spinner-free loading rule needed them |
| 10 | `lib/design/useReducedMotion` alongside `hooks/usePrefersReducedMotion` | The existing hook is wrong on first render (§6); fixing it was outside this wave's files |

---

## 11. Component index

| Component | File | Status |
|---|---|---|
| Button, `buttonClasses`, `LoadingSweep` | `components/ui/Button.tsx` | Built |
| IconButton | `IconButton.tsx` | Built |
| Field (label, hint, error) | `Field.tsx` | Built |
| Input | `Input.tsx` | Built |
| Textarea | `Textarea.tsx` | Built |
| Select | `Select.tsx` (existing) | Spec §3.5, rebuild later |
| Checkbox | `Checkbox.tsx` | Built |
| Switch | `Switch.tsx` | Built |
| SegmentedControl | `SegmentedControl.tsx` | Built |
| RadioGroup | — | Spec §3.8 |
| Chip | `Chip.tsx` | Built |
| Badge, StatusBadge | `Badge.tsx` | Built |
| Tooltip | `Tooltip.tsx` | Built |
| Menu | `Menu.tsx` | Built |
| Dialog | `Dialog.tsx` + `ModalLayer.tsx` | Built |
| Drawer | `Drawer.tsx` + `ModalLayer.tsx` | Built |
| Popover | `Popover.tsx` | Built |
| Toast, ToastProvider, useToast | `Toast.tsx` | Built |
| Tabs, TabList, Tab, TabPanel | `Tabs.tsx` | Built |
| Table | — | Spec §3.18 |
| Card, CardHeader, CardFooter, `cardLinkOverlay` | `Card.tsx` | Built |
| Skeleton, SkeletonText, SkeletonGroup | `Skeleton.tsx` | Built |
| EmptyState | `EmptyState.tsx` | Built |
| ProgressBar | `ProgressBar.tsx` | Built |
| ProgressSteps | `ProgressSteps.tsx` | Built |
| Avatar | `components/dashboard/Avatar.tsx` (existing) | Spec §3.23, move later |
| Kbd | `Kbd.tsx` | Built |
| WorkingText | `WorkingText.tsx` | Built |
| Portal, useIsClient | `Portal.tsx` | Built |
| PromptBar | `PromptBar.tsx` | Built |
| ContextChip | `ContextChip.tsx` | Built (locked state: spec) |
| SlashMenu | — | Spec §4.3 |
| ChoiceCard | `ChoiceCard.tsx` | Built |
| StepList | `StepList.tsx` | Built |
| ResultMessage | `ResultMessage.tsx` | Built |
| PromptQueue | — | Spec §4.7 |
| ActivityIndicator | — | Spec §4.8 |
| QualityBadge | — | Spec §4.9 (a Badge plus placement) |
| VersionHistory item | — | Spec §4.10 |
| VideoPlayer, Timeline, AssetGrid, MediaCard | — | Spec §5 |

The gallery at `/design-system` shows every built component in every state, in dark and light (toggle in the header). It returns 404 in production.

---

## 12. Open questions for the owner

| # | Question | Default if unanswered |
|---|---|---|
| 1 | Approve the glossary's resolution of the two editors (§7.5): "Editor" = timeline tool; today's per-clip screen is "Clip studio" until rebuilt | Yes |
| 2 | Light theme: ship a user toggle in Wave 2, or keep dark-only until all screens are on tokens? | Dark only until screens are migrated; then a toggle in Settings plus "match system" |
| 3 | Replace the body of `hooks/usePrefersReducedMotion` with the synchronous version (§6) | Yes, in the next wave that touches `hooks/` |
| 4 | Restart `next dev` to pick up the new Tailwind keys (§2.9) | Needed before viewing `/design-system` styled |
| 5 | Indian English spelling in UI copy (colour, cancelled), matching the legal pages | Yes |
| 6 | Platform marks: use official YouTube and Instagram brand assets (and their colours) on connect buttons only | Yes, marks only |
| 7 | framer-motion: keep (as `motion/react` + `LazyMotion`) or replace with CSS, given frontend architecture §5 says remove (§13) | Keep, switch to `LazyMotion` in Phase 0 |

---

## 13. What the Wave 3 architecture means for the design system

Read against [04-architecture.md](04-architecture.md) and [architecture/frontend.md](architecture/frontend.md).

| Architecture point | Effect on the design system |
|---|---|
| New UI is built in `app/v2/` behind `new_ui_*` flags (§1, R7) | `components/ui/` and the tokens are shared by both trees. Legacy screens keep working because every token, class and keyframe is `cn-` namespaced and nothing legacy was changed (§9) |
| `frontend.md` §1: root layout loads UI fonts with `next/font/local` and imports `tokens.css` | `next/font` generates hashed family names. When that lands, `fontFamily` in `tokens.ts` should point at the font's CSS variable (for example `var(--font-jakarta)`) instead of the literal family names, then regenerate `tokens.css`. The `@import` in `globals.css` can move to the layout at the same time |
| `frontend.md` §5: "`framer-motion` — remove; motion uses CSS and tokens; if a sequence needs it, use `motion/react` with `LazyMotion`" | **Conflict to settle.** This wave's brief allowed framer-motion and seven components use it for enter/exit (`Menu`, `ModalLayer`, `Popover`, `StepList`, `Tabs`, `Toast`, `Tooltip`), all through `lib/design/motion.ts`. Options: (a) keep, switching to `motion/react` with `LazyMotion` + `m.*` (about 5 KB; the presets already isolate the API); (b) replace with CSS transitions plus a small presence helper for exit animations. Recommendation: (a) — exit animations and the tab indicator's shared layout are the parts CSS does poorly, and the change touches only those seven files and `motion.ts` |
| CSS budget 30 KB gzipped (§6) | `tokens.css` adds 1.7 KB gzipped; the whole compiled stylesheet including the gallery's classes is about 21 KB gzipped |
| Event contract (events.md): `run.step.*`, `run.operation.applied`, `run.result`, `sync.reset` | Maps one-to-one onto the presentational props: steps → `StepList.steps`; `run.operation.applied` → the timeline's `animate-cn-highlight`; result → `ResultMessage`; `sync.reset` → keep showing the last state with `WorkingText` "Reconnecting" until snapshots refetch. Components stay stateless; the run store owns the data |
| `423 ITEM_LOCKED` during a run (§5) | The ContextChip **locked** state and the timeline clip lock (§4.2, §5.2) are the visible side of this code. Copy: "Clipnera is editing this clip. It's yours again when the step ends." |
| `409 STALE_VERSION` and rebase toast (frontend §4.5) | Toast, neutral tone, naming what was replaced: "Your edit to Opening hook was replaced by Clipnera's change." with **Undo** if the version allows it |
| Error envelope `{code, message, details, request_id, retryable}` (R13) | Error UIs choose by `code`, never by message text. Show **Try again** only when `retryable` is true; otherwise the one action is the fix (§7.3). `VALIDATION_FAILED` details map to `Field` errors on the named inputs. `request_id` goes in a "Copy details" action for support, never in the main message |
| Long work returns `202` with a Job or Run (§5) | Every such action uses the Button loading state only until the 202 arrives (well under a second), then hands over to `ActivityIndicator`, `ProgressSteps` or `StepList`. Buttons never stay busy for the length of a job |
| O11: the clip studio URL opens the new Editor on that clip | Confirms the glossary (§7.5): one tool named **Editor**; "Clip studio" lasts only until `new_ui_editor` is on |
| `lib/design/tokens.ts`, `app/tokens.css`, `components/ui/**`, `app/design-system/**` are owned by the Design System (frontend §8) | Matches the file list in §9. `tailwind.config.ts` is owned by Platform; the `cn-*` keys added here should be kept when Phase 0 rewrites that file (they are generated from `tokens.ts`, so it is one spread) |
| Next.js upgrade to 15.5.x (F1, O5) | No design-system code depends on 15.1 behaviour. Re-run the gallery and the CSS comparison in §9 after the upgrade |
