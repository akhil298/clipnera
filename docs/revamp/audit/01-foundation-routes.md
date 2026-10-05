# 01 — Foundation, routes and styling (Wave 0 audit)

Audit date: 2026-10-03. Branch `clipnera` at `38f9bd5`. Read-only audit; no source file was changed.
All paths are relative to `frontend/` unless they start with `backend/`.

**Scope read (79 files, all top to bottom):** 40 files under `app/`, 6 in `components/ui/`, 23 in `components/skeletons/`, 2 in `components/legal/`, `scripts/fetch-landing-media.mjs`, `tailwind.config.ts`, `next.config.mjs`, `postcss.config.mjs`, `package.json`, `tsconfig.json`, `env.local.example`, `.eslintrc.json`. `public/` was listed, not read (binary fonts and licence texts).

Notes on method:
- The 13 placeholder pages under `app/dashboard/(shell)/` are three lines each (`return null`); they were printed in full with `cat -n` rather than the Read tool.
- `.env.local` and `.env.example` were not opened.
- Usage counts come from a grep over `app/`, `components/`, `lib/`, `hooks/` (`.ts`, `.tsx`, `.css`, `.mjs`). They count files unless stated otherwise.
- Files outside the slice were opened only to explain a route: `components/admin/AdminGate.tsx`, `components/auth/AuthShell.tsx`, `components/landing/LandingPageView.tsx`, `components/landing/LandingVideo.tsx`, `lib/landingMedia.ts`, and parts of `components/dashboard/DashboardApp.tsx` (lines 40–164, 725–754).

---

## 1. Route map

There are 30 URLs. There is **no** `middleware.ts`, `loading.tsx`, `error.tsx`, `global-error.tsx`, `not-found.tsx`, `template.tsx`, `route.ts`, `robots`, `sitemap`, `manifest` or Open Graph image anywhere in `app/`. Every guard is client-side, in a `useEffect`, after first paint.

"S" = server component page file, "C" = client (`'use client'`). Note that most S pages only render a client component.

### Public and marketing

| URL | Page file | Layouts | Renders | Guard | S/C | Metadata |
|---|---|---|---|---|---|---|
| `/` | `app/page.tsx:1-5` | root | `LandingPageView` (client, 96 lines) | None. CTA goes to `/dashboard` if signed in, else opens `SignInModal` (`components/landing/LandingPageView.tsx:48-51`) | S → C | Root default only |
| `/editor` | `app/editor/page.tsx:1-11` | root | `EditorLanding` (client, 214 lines) | None. "Start" pushes `/dashboard/editor?brief=…` if signed in, else sign-in modal (`components/editor-landing/EditorLanding.tsx:62-70`) | S → C | Own title + description (`app/editor/page.tsx:4-7`) |
| `/login` | `app/login/page.tsx:1-10` | root | `AuthShell mode="login"` + `GoogleSignIn` | None; a signed-in user is not redirected away | S → C | Root default |
| `/signup` | `app/signup/page.tsx:1-10` | root | `AuthShell mode="register"` + `GoogleSignIn mode="register"` | None | S → C | Root default |
| `/login/google` | `app/login/google/page.tsx:1-68` | root | Inline card: spinner, or error + "Back to sign in" | OAuth callback. Reads `code`/`state`, strips them from the URL, checks state, exchanges, then `replace('/dashboard')` (`:22-43`) | C | None (client page) |

### Legal

| URL | Page file | Renders | S/C | Metadata |
|---|---|---|---|---|
| `/privacy` | `app/privacy/page.tsx` (159 lines) | `LegalPage` | S | `Privacy Policy · Clipnera` (`:4`) |
| `/terms` | `app/terms/page.tsx` (108) | `LegalPage` | S | `Terms of Service · Clipnera` (`:4`) |
| `/refunds` | `app/refunds/page.tsx` (50) | `LegalPage` | S | `Refund Policy · Clipnera` (`:4`) |
| `/cookies` | `app/cookies/page.tsx` (64) | `LegalPage` + storage table | S | `Cookie Policy · Clipnera` (`:4`) |
| `/data-deletion` | `app/data-deletion/page.tsx` (48) | `LegalPage`; with `?code=` shows a Meta deletion status box (`:13-17`, `:37-45`) | C | None |
| `/unsubscribe` | `app/unsubscribe/page.tsx` (65) | `LegalPage` + one-click confirm button; needs `?token=` (`:17-21`) | C | None |

All legal pages are wrapped by the root layout only. None has a guard.

### Dashboard (signed-in app)

All 13 URLs below share `app/dashboard/(shell)/layout.tsx:9-11`, which renders `<DashboardApp />` and **does not accept or render `children`**. Each `page.tsx` is `return null` and exists only to register the URL. `DashboardApp` (client, 1,021 lines) picks the view from the pathname (`components/dashboard/DashboardApp.tsx:52-69`).

| URL | Page file (under `app/dashboard/(shell)/`) | Tab chosen by `getTabFromPathname` |
|---|---|---|
| `/dashboard` | `page.tsx` | `dashboard` (home) |
| `/dashboard/folders` | `folders/page.tsx` | `folders` |
| `/dashboard/projects/[projectId]` | `projects/[projectId]/page.tsx` | `generator` (clip list) |
| `/dashboard/projects/[projectId]/edit/[clipId]` | `projects/[projectId]/edit/[clipId]/page.tsx` | `editor` (full-screen `VideoEditorStudio`, `DashboardApp.tsx:745-754`) |
| `/dashboard/scheduler` | `scheduler/page.tsx` | `scheduler` |
| `/dashboard/analytics` | `analytics/page.tsx` | `analytics` |
| `/dashboard/brand-kit` | `brand-kit/page.tsx` | `brand_kit` |
| `/dashboard/reels` | `reels/page.tsx` | `reels` |
| `/dashboard/reels/[reelId]` | `reels/[reelId]/page.tsx` | `reels` |
| `/dashboard/reels/footage/[editId]` | `reels/footage/[editId]/page.tsx` | `reels` |
| `/dashboard/editor` | `editor/page.tsx` | `video_editor` (the new Editor) |
| `/dashboard/editor/[editorProjectId]` | `editor/[editorProjectId]/page.tsx` | `video_editor` |
| `/dashboard/settings` | `settings/page.tsx` | `settings`; `?tab=billing|social|team` deep-links a sub-tab (`DashboardApp.tsx:134-137`) |

- **Guard:** `isAuthenticated()` (token in `localStorage`) checked in an effect; signed-out users go to `/`, not `/login` (`DashboardApp.tsx:118-124`). A 401 from the API also sends the user to `/` (`:371-373`).
- **Loading:** `DashboardSkeleton` until auth and profile resolve (`DashboardApp.tsx:733-735`). No route-level `loading.tsx`.
- **Error / not-found:** none. An unknown `/dashboard/xyz` falls to Next's built-in 404.
- **Metadata:** none. Every dashboard URL has the root title "Clipnera — AI Video Editing & Shorts Creator".

One dashboard URL sits outside the shell:

| URL | Page file | Layouts | Renders | Guard | S/C |
|---|---|---|---|---|---|
| `/dashboard/connect/[platform]` | `app/dashboard/connect/[platform]/page.tsx:1-70` | root only | Inline card: spinner or error + "Back to settings" | No auth check in the page; the API call fails if signed out and the message is shown. Accepts `youtube`, `tiktok`, `instagram`, `x` (`:9`) | C |

### Admin

`app/admin/layout.tsx:3-5` wraps everything in `AdminGate` only. It does not render the admin sidebar; each view wraps itself in `AdminLayout` (10 files import it).

| URL | Page file | Renders |
|---|---|---|
| `/admin` | `app/admin/page.tsx:3-5` | Server `redirect('/admin/overview')` |
| `/admin/overview` | `app/admin/overview/page.tsx` | `AdminOverviewView` |
| `/admin/users` | `app/admin/users/page.tsx` | `AdminUsersView` |
| `/admin/users/[id]` | `app/admin/users/[id]/page.tsx` | `AdminUserDetailView` |
| `/admin/payments` | `app/admin/payments/page.tsx` | `AdminPaymentsView` (lives in `components/payments/`, not `components/admin/`) |
| `/admin/credits` | `app/admin/credits/page.tsx` | `AdminCreditsView` |
| `/admin/social` | `app/admin/social/page.tsx` | `AdminSocialView` |
| `/admin/usage` | `app/admin/usage/page.tsx` | `AdminUsageView` |
| `/admin/broll` | `app/admin/broll/page.tsx` | `AdminBrollView` |
| `/admin/features` | `app/admin/features/page.tsx` | `AdminFeaturesView` |

- **Guard:** `AdminGate` (`components/admin/AdminGate.tsx:9-41`): no token → `/login`; not admin → `/dashboard`; profile fetch fails → `/login`. Shows a centred spinner meanwhile. The API enforces admin separately.
- **Metadata, loading, error:** none.

### Redirects, duplicates and legacy

- **Only one server redirect exists:** `/admin` → `/admin/overview`. `next.config.mjs` defines no redirects or rewrites.
- **`/editor` vs `/dashboard/editor`:** not duplicates. `/editor` is a public marketing page for the Editor; `/dashboard/editor` is the tool. The names collide and will confuse anyone sharing links.
- **Two things called "editor" inside the dashboard:** `/dashboard/projects/[projectId]/edit/[clipId]` is tab `editor` (the clip studio); `/dashboard/editor` is tab `video_editor` (the new timeline Editor) (`DashboardApp.tsx:58`, `:65`).
- **`/login` and `/signup`** are the same page with one prop changed.
- **Signed-out destinations are inconsistent:** dashboard sends to `/`, admin to `/login`, Google callback error to `/login`.
- `public/landing/` is an empty directory; nothing references it.

---

## 2. Layouts and providers

### Root layout — `app/layout.tsx`

| What | Detail | Line |
|---|---|---|
| Global CSS | `./globals.css` | `:2` |
| Fonts | 16 `@fontsource` CSS imports: Plus Jakarta Sans 400/500/600/700/800, Syne 700/800, JetBrains Mono 500/700, and seven caption faces (Anton, Archivo Black, Bangers, Bebas Neue, DM Serif Display, Luckiest Guy, Permanent Marker) | `:6-22` |
| Metadata | `title` and `description` only. No `metadataBase`, Open Graph, Twitter card, `viewport`, `themeColor`, or title template | `:24-27` |
| `<html>` | `lang="en"`, hard-coded `className="dark"`, `suppressHydrationWarning` | `:31` |
| Script 1 | React Grab from `unpkg.com`, development only, `beforeInteractive` | `:34-40` |
| Script 2 | Inline "hydration-fix": a `MutationObserver` on the whole document that strips two Grammarly attributes for the life of the page | `:41-68` |
| `<body>` | `bg-neutral-950 text-neutral-100`, Plus Jakarta Sans as an arbitrary-value class, amber selection colour, `overflow-x-hidden`, `antialiased`, `suppressHydrationWarning` | `:70` |
| Cookie notice | `<CookieNotice />` after `children`, so it shows on every route including the dashboard and editor | `:72` |
| Favicon | `app/icon.svg` (amber tile with Sparkles) picked up by convention | `app/icon.svg:1-11` |

**Not present:** any React context provider, theme provider, analytics, error boundary, toast host, or `Suspense`. The root layout itself is a server component.

### Nested layouts

| Layout | Does | Does not |
|---|---|---|
| `app/dashboard/(shell)/layout.tsx:9-11` | Mounts `DashboardApp` once so the sidebar, header and loaded data survive tab changes | Render `children`; so no page-level code, `loading.tsx` or `error.tsx` can ever show inside the shell |
| `app/admin/layout.tsx:3-5` | Gates on admin role | Provide the admin chrome; that is repeated inside each view |

Providers live inside `DashboardApp` (`EntitlementsProvider`, `DashboardApp.tsx:738-742`), outside this slice.

---

## 3. Styling and design tokens

### Actual palette in use

The app is **dark only**, built on Tailwind's default `neutral` and `amber` scales. Counts are class occurrences across the frontend.

| Role | Colour | Occurrences / files |
|---|---|---|
| Surfaces, text, borders | `neutral-*` (page `neutral-950`, cards `neutral-900`, borders `neutral-800`) | 2,139 / 132 |
| Brand, primary action, focus | `amber-*` (button `amber-500`, hover `amber-400`, link `amber-300`) | 752 / 95 |
| Error / destructive | `rose-*` **and** `red-*` | 171 / 46 and 51 / 19 |
| Success | `emerald-*` | 102 / 41 |
| Scheduled / info | `sky-*` | 37 / 14 |
| "AI" accent and decoration | `violet-*`, `fuchsia-*`, `purple-*`, `pink-*`, `indigo-*` | 35 / 15, 26 / 3, 6 / 6, 7 / 4, 2 / 2 |
| Stray one-offs | orange 3, teal 2, blue 2, yellow 1, cyan 1, green 1, lime 1 | — |

`zinc`, `gray`, `slate`, `stone` are not used at all. The blueprint's "amber/neutral only" palette is therefore mostly true already; the exceptions are the violet family (21 files, listed in section 6) and the red/rose split.

Hard-coded brand hexes: `#f59e0b` (logo tile, `app/icon.svg:3`, `components/ui/LogoMark.tsx:15`), `#0a0a0a` (logo stroke), `#fbbf24` (focus ring, `app/globals.css:8`).

### `globals.css` — everything in it

| Lines | What | Status |
|---|---|---|
| `1-3` | Tailwind layers | In use |
| `6-11` | `:focus-visible` 2px amber-400 outline, 2px offset | In use, global. Good |
| `13-24` | CSS variables: `--background` 0 0% 4%, `--foreground` 0 0% 100%, `--primary` 262 83% 58% (violet), `--primary-hover`, `--muted`, `--muted-foreground`, `--border` 0 0% 18%, `--ring` (violet) | **Legacy.** See below |
| `26-33` | `* { border-border }`, `body { bg-background text-foreground }` | Half live. See below |
| `36-38` | `.glass` | **Unused** (0) |
| `39-41` | `.glow` (violet shadow) | **Unused** (the 30 grep hits for "glow" are a caption animation name, not this class) |
| `42-44` | `.gradient-text` (violet → fuchsia) | **Unused** |
| `45-47` | `.input-glow:focus` | **Unused** |
| `48-53` | `.btn-glow` + hover | **Unused** |
| `56-59`, `72-74` | `@keyframes float`, `.animate-float` | **Unused** |
| `61-65`, `76-78` | `@keyframes pulse-ring`, `.animate-pulse-ring` | **Unused** |
| `67-70`, `80-90` | `@keyframes skeleton-shimmer`, `.skeleton` | In use: `Skeleton.tsx:11`, and the keyframe again by name in `components/dashboard/ClipPoster.tsx:60` |
| `98-136` | `caption-word-cycle`, `.caption-preview-word` + reduced-motion rule | In use (2 files) |
| `140-161` | `.caption-preset-scroll` thin scrollbar | In use (1 file) |
| `164-177` | `landing-playhead` + reduced-motion rule | In use (1 file) |
| `181-210` | Caption entrances: `caption-rise`, `-fade`, `-land`, `-bounce`, `-grow`, `-blur` | In use, by name from `components/dashboard/studio/studioUtils.ts`. Mirror `backend/subtitle_styling/ass_generator.py`; must survive the revamp |
| `214-251` | Spoken-word motion: `word-grow`, `-breathe`, `-bounce`, `-shake`, `-glitch`, `-blur` | In use, same file. Same constraint |
| `253-257` | `.caption-motion` reduced-motion kill switch | In use |
| `260-273` | `title-card-in`, `.title-card` | In use (1 file) |
| `278-335` | Eight `@font-face` rules for TTFs in `public/fonts/` | In use by caption presets (`lib/utils/captionStyles.generated.ts`) |

**CSS variables, precisely:**
- `--primary`, `--primary-hover`, `--ring`, `--muted`, `--muted-foreground`: no `var(--…)` reference outside `tailwind.config.ts`, and the Tailwind colours built from them (`bg-primary`, `text-muted`, …) have **zero** uses. Dead, and violet.
- `--background` / `--foreground`: applied to `body` at `globals.css:31`, then overridden by `bg-neutral-950 text-neutral-100` on the same element (`app/layout.tsx:70`). `bg-background` / `text-foreground` have zero uses elsewhere. Effectively dead.
- `--border`: **live and invisible.** `* { @apply border-border }` (`globals.css:28`) makes `hsl(0 0% 18%)` (#2e2e2e) the default colour of every `border` class written without a colour. Removing it changes borders across the app. Keep the behaviour, rename the token.
- `--primary-hover` is not even mapped in Tailwind.

### Tailwind theme — `tailwind.config.ts`

| Setting | Value | Note |
|---|---|---|
| `darkMode` | `["class"]` (`:5`) | `<html class="dark">` is hard-coded and there are **zero** `dark:` variants in the codebase. There is no light theme and no toggle |
| `content` | `app/`, `components/`, `lib/` (`:6-10`) | `hooks/` is not scanned. Harmless today (no classes there) |
| `colors.neutral.500` | `#8c8c8c` instead of Tailwind's `#737373` (`:16-18`) | Deliberate, for WCAG AA on dark surfaces. Used 244 times in 62 files. Keep |
| `colors.border/background/foreground/primary/muted` | Mapped to the CSS variables (`:19-29`) | Only `border` is effectively used (see above) |
| `backdropBlur.xl` | `24px` (`:31-33`) | Identical to Tailwind's default; and `backdrop-blur-xl` is only used by the unused `.glass`. Redundant |
| `fontFamily` | `jakarta`, `syne`, `jetbrains` (`:34-38`) | See fonts below |
| Radii, shadows, spacing, animations | Not extended | Tailwind defaults only |
| Plugins | `tailwindcss-animate` (`:41`) | In use: `animate-in` / `fade-in` / `slide-in` / `zoom-in` in 17 files |

Because nothing is tokenised, the scale is whatever each file chose:
- **Type sizes:** `text-xs` 427, `text-[11px]` 178, `text-sm` 165, `text-[10px]` 117, `text-[13px]` 81, `text-[11.5px]` 57, `text-[10.5px]` 24, `text-[9px]` 19, `text-[12.5px]` 10, `text-[9.5px]` 9. More than 400 uses are below 12px.
- **Radii:** `rounded-xl` 303, `rounded-lg` 218, `rounded-full` 150, `rounded-2xl` 132, `rounded-md` 43, plus arbitrary `[9px]` 17, `[10px]` 16, `[5px]`, `[18px]`, `[7px]`, `[14px]`.
- **z-index:** `z-10/20/30/40/50` plus `z-[2]`, `z-[8]`, `z-[25]`, `z-[60]` (cookie notice), `z-[70]` (skip link), `z-[1000]` (Select menu). No documented layer order.

### Fonts loaded

| Family | Source | Weights | How it is applied | Note |
|---|---|---|---|---|
| Plus Jakarta Sans | `@fontsource` | 400–800 | Body via `font-['Plus_Jakarta_Sans',sans-serif]` (`app/layout.tsx:70`), repeated in 8 more files; the `font-jakarta` utility is used once | UI face |
| Syne | `@fontsource` | 700, 800 | `font-syne` in 10 files, `font-['Syne',…]` in 3 | Display face |
| JetBrains Mono | `@fontsource` | 500, 700 | `font-jetbrains` 42 uses / 14 files | But `font-mono` (system mono stack, **not** JetBrains) is used 68 times / 35 files |
| Anton, DM Serif Display, Luckiest Guy | `@fontsource` | 400 | Caption presets | Referenced in the frontend |
| Archivo Black, Bangers, Bebas Neue, Permanent Marker | `@fontsource` | 400 | Named only by backend templates (`backend/subtitle_styling/templates.py`) | No string reference in the frontend; they arrive through API data. Do not delete without checking the caption catalogue |
| DejaVu Sans / Serif / Sans Mono, Poppins Black, Montserrat (Bold, ExtraBold), Courier Prime, Roboto | `@font-face` in `globals.css:278-335`, files in `public/fonts/` | Bold cuts | Caption preview parity with the export | Uncompressed TTF |

`next/font` is not used anywhere. All fonts are self-hosted, which matches the privacy claims.

### `public/` and `scripts/`

| Path | Size | Note |
|---|---|---|
| `public/fonts/DejaVuSans-Bold.ttf` | 704 KB | |
| `public/fonts/Montserrat-ExtraBold.ttf` | 455 KB | |
| `public/fonts/Montserrat-Bold.ttf` | 455 KB | |
| `public/fonts/DejaVuSerif-Bold.ttf` | 356 KB | |
| `public/fonts/DejaVuSansMono-Bold.ttf` | 332 KB | |
| `public/fonts/Poppins-Black.ttf` | 153 KB | |
| `public/fonts/Roboto-Bold.ttf` | 124 KB | |
| `public/fonts/CourierPrime-Bold.ttf` | 73 KB | |
| `public/fonts/LICENSE-*.txt` (5 files) | 4–9 KB each | courier-prime, dejavu, montserrat, poppins, roboto |
| `public/landing/` | empty | Unreferenced |
| `public/media/landing/` | **does not exist** | Where the landing videos are expected |

Fonts total about 2.65 MB, all TTF. There are no images, no logo files, no Open Graph image and no video in `public/`.

`scripts/fetch-landing-media.mjs` (46 lines) downloads the seven Pexels clips named in `lib/landingMedia.json` into `public/media/landing/<key>.mp4`, needs `PEXELS_API_KEY`, skips files that exist, and picks the smallest MP4 at least 540px on its short side (`:27-30`). Run with `npm run media:landing`. It has not been run in this checkout, and `*.mp4` is git-ignored (root `.gitignore:54`), so the videos are never in the repo.

---

## 4. Component inventory

### `components/ui/` (6 files)

| Component | Purpose | Props | States | Used in | A11y | Decision |
|---|---|---|---|---|---|---|
| `LogoMark` (`LogoMark.tsx:5`) | Brand mark as inline SVG | `size=32`, `className` | — | 5 files (landing `BrandMark`, `AuthShell`, `AdminLayout`, dashboard `Header`, `Sidebar`) | `aria-hidden`; callers must supply the name. Fine | **KEEP** — single source for the mark; must stay in sync with `app/icon.svg` by hand |
| `PageHeader` (`PageHeader.tsx:19`) | Title, description, actions, eyebrow, back link for signed-in pages | `title`, `description?`, `actions?`, `eyebrow?`, `back?` | — | 10 files | Real `<h1>`; back is a `<button>` with text. Good | **KEEP** — restyle to the new type scale; already the one consistent page pattern |
| `StatusPill` + `statusDotClass` + `projectStatus` (`StatusPill.tsx:31`, `:20`, `:46`) | One status language: dot + word | `tone` (`processing`/`ready`/`failed`/`scheduled`/`neutral`/`ai`), `children`, `dot=true`, `className`, `title` | Pulsing dot for `processing` | 10 files (pill), 2 (`statusDotClass`), 4 (`projectStatus`) | Colour plus text, so not colour-only. Pulse ignores reduced motion | **KEEP** — but the `ai` tone is violet (`:17`), outside the locked palette; and `projectStatus` is domain logic that belongs in `lib/` |
| `ScoreRing` + `scoreTone` (`ScoreRing.tsx:24`, `:7`) | Virality score dial | `score`, `className` | Amber ≥ 85, emerald ≥ 70, neutral below | 3 files (ring), 1 (`scoreTone`) | `role="img"` with a label. Label and number use the unclamped score while the arc is clamped (`:26-28`, `:44`) | **KEEP** — small, correct, accessible |
| `Select` (`Select.tsx:41`) | Custom dropdown that opens attached to the field | `value`, `options[]` (`value`, `label`, `disabled?`, `group?`, `title?`), `onChange`, `className`, `placeholder`, `aria-label` | Open/closed, active option, selected, disabled option, grouped, opens upward near the bottom | 7 files. 11 native `<select>` remain in 5 other files (`FootageReelBoard` 4, `FootageReelForm` 3, `ReelsView` 2, `AdminBrollView` 1, `AdminUsersView` 1) | Good base: `combobox`/`listbox`/`option` roles, `aria-activedescendant`, arrows, Home/End, Enter/Space, Escape, Tab. Gaps: no type-to-select, no `disabled` or error state for the whole field, no way to tie it to a visible `<label>` (only `aria-label`), no `name` for forms | **REBUILD** — keep the behaviour, add the missing states and labelling, then replace the 11 native selects |
| `NotWiredBadge` (`NotWiredBadge.tsx:16`) | Marks UI that is on screen but not connected to the backend | `label="Preview"`, `reason`, `className` | — | 6 files, 13 instances | Reason is in `title` and in `sr-only` text. Good | **KEEP until each feature is wired or removed** — the 13 instances are the revamp's list of fake features (section 6, P-21) |

**Missing from `ui/` entirely:** Button, Input, Textarea, Checkbox, Switch (one lives in `studio/panels`), Modal/Dialog, Drawer, Tooltip, Tabs, Toast, Card, Badge, Spinner, Avatar (one lives in `dashboard/`), EmptyState. Buttons are hand-written per call site; the amber primary button alone is spelled out separately in `app/unsubscribe/page.tsx:52`, `app/login/google/page.tsx:54`, `app/dashboard/connect/[platform]/page.tsx:56` and `components/legal/CookieNotice.tsx:48`, with three different radii and paddings.

### `components/skeletons/` (23 files, 25 exports)

`Skeleton` is the only primitive. The rest are fixed-layout compositions that copy the markup of a screen as it looked when they were written.

| Export | File | Props | Used outside `skeletons/` | Decision |
|---|---|---|---|---|
| `Skeleton` | `Skeleton.tsx:8` | `className`, `style` | 2 (`Header`, `Sidebar`) + internally | **REBUILD** — keep; fix a11y (below) |
| `DashboardSkeleton` | `DashboardSkeleton.tsx:8` | — | 1 (`DashboardApp.tsx:734`) | **REBUILD** — must mirror the new shell |
| `StatsSkeleton` | `StatsSkeleton.tsx:4` | — | 2 (+ `DashboardSkeleton`) | **REBUILD** with the new home |
| `AnalyticsSkeleton` | `AnalyticsSkeleton.tsx:4` | — | 1 | **REBUILD** with the page |
| `BrandKitSkeleton` | `BrandKitSkeleton.tsx:4` | — | 1 | **REBUILD** with the page |
| `TableSkeleton` | `TableSkeleton.tsx:18` | `rows=5` | 1 (`SettingsView`) | **KEEP** — generic |
| `ModalSkeleton` | `ModalSkeleton.tsx:4` | — | 1 (`PlanSelectionModal`) | **REBUILD** — renders its own full-screen backdrop |
| `SidebarSkeleton` | `SidebarSkeleton.tsx:4` | — | 0 (only inside `DashboardSkeleton`) | **REBUILD** with the shell |
| `HeaderSkeleton` | `HeaderSkeleton.tsx:4` | — | 0 (only inside `DashboardSkeleton`) | **REBUILD** with the shell |
| `ProjectCardGridSkeleton`, `ProjectCardSkeleton` | `ProjectCardSkeleton.tsx:24`, `:4` | `count=6` | 0 (only inside `DashboardSkeleton`) | **REBUILD** with the card |
| `TableRowSkeleton` | `TableSkeleton.tsx:4` | — | 0 (only inside `TableSkeleton`) | **KEEP** as a private part |
| `VideoCardSkeleton`, `VideoCardGridSkeleton` | `VideoCardSkeleton.tsx:4`, `:25` | `count=4` | **0** | **DELETE** — dead |
| `FormSkeleton` | `FormSkeleton.tsx:4` | — | **0** | **DELETE** — dead |
| `UploadSkeleton` | `UploadSkeleton.tsx:4` | — | **0** | **DELETE** — dead |
| `ProfileSkeleton` | `ProfileSkeleton.tsx:4` | — | **0** | **DELETE** — dead |
| `SettingsSkeleton` | `SettingsSkeleton.tsx:4` | — | **0** | **DELETE** — dead |
| `VideoPlayerSkeleton` | `VideoPlayerSkeleton.tsx:8` | `aspectRatio` | **0** | **DELETE** — dead |
| `ImageSkeleton` | `ImageSkeleton.tsx:9` | `className`, `aspectRatio` | **0** | **DELETE** — dead |
| `ClipListSkeleton` | `ClipListSkeleton.tsx:4` | — | **0** | **DELETE** — dead, and uses `w-13 h-13`, which is not a Tailwind class (`:11`) |
| `PipelineSkeleton` | `PipelineSkeleton.tsx:4` | — | **0** | **DELETE** — dead |
| `NotificationsSkeleton` | `NotificationsSkeleton.tsx:4` | — | **0** | **DELETE** — dead |
| `AuthSkeleton` | `AuthSkeleton.tsx:4` | — | **0** | **DELETE** — dead; shows email/password fields that no longer exist (login is Google-only) |
| `EmptyState` | `EmptyState.tsx:4` | `icon?`, `title`, `description` | **0** | **DELETE here, REBUILD in `ui/`** — not a skeleton, falls back to a shimmer block as its icon (`:11`), and no screen uses it |

Summary: **13 of 25 exports (12 of 23 files) are dead code.** Only 8 exports are imported from outside the folder.

A11y for the whole family: `Skeleton` puts `role="status"` and `aria-label="Loading"` on every block (`Skeleton.tsx:13-14`). `DashboardSkeleton` renders roughly 80 of them, so a screen reader meets about 80 live regions all named "Loading". The role belongs once, on the container. The shimmer animation has no reduced-motion rule (`globals.css:80-90`).

### `components/legal/` (2 files)

| Component | Purpose | Props | Used in | A11y | Decision |
|---|---|---|---|---|---|
| `LegalPage` (`LegalPage.tsx:31`) | Page frame for every policy: back link, `h1`, updated date, styled prose, legal nav | `title`, `children` | 6 pages | `<main>`, `<nav aria-label="Legal">`, one `h1`. Prose is styled by descendant selectors on `<main>` (`:34`). Body text is `text-sm` | **REBUILD** (visual only) — keep structure and every word of content; add the site header/footer and a readable measure |
| `BusinessDetails` (`:62`) | Operator, address, GSTIN, email, grievance officer | — | 4 pages | List | **KEEP** — legally required content |
| `ContactLine` (`:53`) | Contact email or a fallback phrase | — | 3 pages | — | **KEEP** |
| `BUSINESS`, `LEGAL_LINKS`, `COOKIE_NOTICE_KEY`, `LEGAL_UPDATED` (`:8-29`) | Constants from `NEXT_PUBLIC_*` | — | `BUSINESS` 2, `LEGAL_LINKS` 1 (landing `Footer`), `COOKIE_NOTICE_KEY` 1, `LEGAL_UPDATED` 0 outside the file | — | **KEEP** — move to `lib/`; a landing component importing constants from a legal component is backwards |
| `CookieNotice` (`CookieNotice.tsx:12`) | Storage notice with one "OK" button; remembers dismissal in `localStorage` | — | 1 (root layout) | `<section aria-label>`; real button; not a focus trap (correct for a notice). Appears after hydration, bottom-right, `z-[60]` | **KEEP** — restyle; decide whether it should cover the app shell (P-19) |

Per the project rule, none of the DELETE or REBUILD decisions above should be acted on without the owner's confirmation; the dead skeletons render nowhere, so removing them changes no screen.

---

## 5. Dependencies and config

### `package.json` — dependencies

| Package | Declared | Installed | For | Imported? | Weight note |
|---|---|---|---|---|---|
| `next` | `15.1.6` (pinned) | 15.1.6 | Framework | Yes | See P-01: old patch release |
| `react`, `react-dom` | `^19.0.0` | 19.2.8 | UI runtime | Yes | — |
| `lucide-react` | `^0.452.0` | 0.452.0 | Icons | 80 files | Tree-shaken per icon; fine |
| `recharts` | `^3.10.1` | 3.10.1 | Charts | 2 files (`admin/DailyBarChart`, `dashboard/ViralAnalyticsView`) | **Heavy.** Statically imported into the dashboard shell |
| `canvas-confetti` | `^1.9.4` | 1.9.4 | Celebration effect | 3 files | Small, but statically imported |
| `framer-motion` | `^11.11.9` | 11.18.2 | Animation | **0 files — unused** | 3.8 MB on disk; costs nothing in the bundle, but is dead weight |
| `@fontsource/plus-jakarta-sans`, `/syne`, `/jetbrains-mono` | `^5.3.0` | — | UI fonts | Root layout | 9 CSS files, several `@font-face` each (one per script subset) |
| `@fontsource/anton`, `/archivo-black`, `/bangers`, `/bebas-neue`, `/dm-serif-display`, `/luckiest-guy`, `/permanent-marker` | `^5.3.0` | — | Caption faces | Root layout | Font files download only when used; the `@font-face` CSS ships on every page |

### devDependencies

| Package | For | Note |
|---|---|---|
| `typescript ^5.6.3`, `@types/node`, `@types/react`, `@types/react-dom`, `@types/canvas-confetti` | Types | `strict: true` |
| `tailwindcss ^3.4.13` (3.4.19 installed), `postcss`, `autoprefixer` | Styling | `postcss.config.mjs:1-6` is the standard two plugins |
| `tailwindcss-animate ^1.0.7` | `animate-in` utilities | Used in 17 files |
| `eslint ^8.57.0`, `eslint-config-next ^15.1.6` | Lint | `.eslintrc.json:3-7` turns **off** `no-img-element`, `no-page-custom-font`, `no-unescaped-entities` |

Not present: any component library, class-merging helper (`clsx`, `tailwind-merge`), form or validation library, data-fetching library, state library, test runner, Storybook, Prettier config.

### Scripts

`dev`, `build`, `start`, `lint`, `media:landing`, and `test` = `node --test lib/` (`package.json:6-11`). The only test file is `lib/editor/timeline.test.mts`. Nothing tests components.

### `next.config.mjs`

| Setting | Value | Line |
|---|---|---|
| `reactStrictMode` | `true` | `:3` |
| `distDir` | `NEXT_DIST_DIR` or `.next` (so a check build does not break the running dev server) | `:8` |
| `headers()` | `Referrer-Policy: no-referrer` on `/dashboard/connect/:platform` and `/login/google` | `:9-21` |
| `images` | **not set** (`next/image` is used nowhere) | — |
| `redirects`, `rewrites`, `experimental` | **not set** | — |
| Security headers (CSP, `X-Frame-Options`, HSTS, `X-Content-Type-Options`), `poweredByHeader` | **not set** | — |

### `tsconfig.json`

`strict`, `target: ES2017`, `moduleResolution: bundler`, alias `@/*` → project root (`:24-28`), `allowJs: true`.

### `env.local.example`

`NEXT_PUBLIC_API_URL` (set to a plain-HTTP public IP, `:1`) and six business-detail variables (`:5-11`). **Missing:** `NEXT_PUBLIC_GOOGLE_CLIENT_ID`, which `lib/googleAuth.ts:18` reads. Both `env.local.example` and `.env.example` are git-ignored (root `.gitignore:30`, `:32`), so the template the project instructions point to is not in the repository.

---

## 6. Problems

Severity: **high** = blocks or undermines the revamp, or is a live defect users or the business can hit; **med** = real cost, should be fixed during the revamp; **low** = tidy-up.

### High

| # | Problem | Where |
|---|---|---|
| P-01 | **Next.js is pinned to 15.1.6**, an early-2025 patch release. Several security advisories for the 15.x line were fixed in later 15.1.x patches, including a critical React Server Components one in December 2025. I did not run an audit tool; this needs checking against the Next.js advisories before launch, and almost certainly a patch bump. | `package.json:27` |
| P-02 | **The whole dashboard is one statically imported client bundle.** The shell layout mounts `DashboardApp` (1,021 lines) and ignores `children`; pages return `null`. There is no `next/dynamic`, `React.lazy` or `Suspense` anywhere in the frontend. Opening `/dashboard/settings` therefore loads the clip studio, the new Editor, recharts and confetti. | `app/dashboard/(shell)/layout.tsx:9-11`; `components/dashboard/DashboardApp.tsx:1-35` |
| P-03 | **No error handling at route level.** No `error.tsx`, `global-error.tsx` or `not-found.tsx`. A render error in any view blanks the whole app; a bad URL shows Next's unbranded 404. | `app/` (absent) |
| P-04 | **Landing videos are not in the build.** `LandingVideo` requests `/media/landing/<key>.mp4`; that folder does not exist, `*.mp4` is git-ignored, and nothing in `build` runs the download script. Each clip 404s and silently falls back to its poster. The landing page shows stills unless someone runs `npm run media:landing` with a Pexels key on the deploy machine. | `lib/landingMedia.ts:22`; `components/landing/LandingVideo.tsx:53-62`; `scripts/fetch-landing-media.mjs:12`; root `.gitignore:54` |
| P-05 | **The cookie policy says something the site does not do.** It states "Fonts and all other files are served by Clipnera itself", but every landing poster is loaded from `images.pexels.com`, which sends each visitor's IP address to a third party. Either self-host the posters or correct the sentence. | `app/cookies/page.tsx:51-52`; `lib/landingMedia.ts:21` |
| P-06 | **No design tokens.** Colours, type sizes, radii, shadows and layers are literal Tailwind classes in every file (2,139 neutral and 752 amber occurrences; 10+ type sizes; 10 radii; 11 z-index values). The only tokens that exist are a leftover violet theme that nothing uses. A re-skin today means editing about 130 files. | `tailwind.config.ts:11-40`; `app/globals.css:13-24` |
| P-07 | **No shared primitives.** `components/ui/` has no Button, Input, Modal, Tabs, Tooltip, Toast or Card. The primary button is re-typed at each call site with different radius and padding. | `app/unsubscribe/page.tsx:52`; `app/login/google/page.tsx:54`; `app/dashboard/connect/[platform]/page.tsx:56`; `components/legal/CookieNotice.tsx:48` |

### Medium

| # | Problem | Where |
|---|---|---|
| P-08 | **Legacy violet theme still shipped.** `--primary`, `--ring`, `--muted*`, `.glass`, `.glow`, `.gradient-text`, `.input-glow`, `.btn-glow`, `.animate-float`, `.animate-pulse-ring` and their keyframes have zero uses. Exception: `--border` is live through `* { border-border }` and must be kept. | `app/globals.css:15-24`, `:36-78`; `tailwind.config.ts:19-33` |
| P-09 | **13 dead skeleton exports** in 12 files, one of them describing a password form that no longer exists. | `components/skeletons/` (table in section 4) |
| P-10 | **Skeleton accessibility.** Every shimmer block is its own `role="status"` region named "Loading"; the dashboard skeleton has about 80. The shimmer ignores reduced motion. | `components/skeletons/Skeleton.tsx:13-14`; `app/globals.css:80-90` |
| P-11 | **Violet family used in 21 files** against a palette locked to amber/neutral: `ui/StatusPill` (`ai` tone, `:17`), `auth/AuthShell` (`:13`, `:32`), `admin/AdminLayout` (`:43`), `admin/AdminUsersView`, `landing/RoiCalculator`, `social/platforms.ts`, and 14 files under `components/dashboard/` (`Sidebar`, `DashboardHomeView`, `SettingsView`, `ProjectFoldersView`, `ReelsView`, `SocialSchedulerView`, `HookTransitionPanel`, `PlanBanner`, `Avatar`, `ClipBrollPanel`, `NotificationsDrawer`, `editor/EditorView`, `studio/TranscriptPanel`, `studio/Timeline`). Some are legitimate brand colours of social platforms; each needs a decision. | as listed |
| P-12 | **Two error colours.** `rose-*` (171) and `red-*` (51) are both used for failure. | 46 and 19 files |
| P-13 | **Two monospace faces.** `font-jetbrains` (42 uses) and `font-mono` (68 uses, which is the system stack, not JetBrains). Numbers and timecodes render in different faces from screen to screen. | 14 and 35 files |
| P-14 | **Font applied three ways.** The body sets Plus Jakarta Sans with an arbitrary-value class; eight more wrappers repeat it needlessly; the `font-jakarta` utility built for this is used once. Same split for Syne. | `app/layout.tsx:70`; `components/legal/LegalPage.tsx:33`, `:38`; `components/legal/CookieNotice.tsx:37`; `app/login/google/page.tsx:46`; `components/skeletons/DashboardSkeleton.tsx:10`; `components/skeletons/AuthSkeleton.tsx:6` |
| P-15 | **Very small text.** Over 400 uses of 9–11.5px sizes. Legal pages are `text-sm` with `text-xs` tables and nav. | e.g. `components/ui/StatusPill.tsx:34`, `components/ui/NotWiredBadge.tsx:19`, `app/cookies/page.tsx:22`, `components/legal/LegalPage.tsx:34`, `:41` |
| P-16 | **Metadata is thin.** No title template, Open Graph, Twitter card, `metadataBase`, `viewport`/`themeColor`, robots or sitemap. Every dashboard and admin URL, `/login`, `/signup`, `/data-deletion` and `/unsubscribe` share one title. Separators differ ("—" in root, "·" elsewhere). | `app/layout.tsx:24-27`; `app/editor/page.tsx:5`; `app/privacy/page.tsx:4` |
| P-17 | **Client-only auth, with flashes.** Guards run in effects after paint, so signed-out visitors see the dashboard skeleton before being sent away, and they land on three different places (`/`, `/login`). `/login` and `/signup` do not redirect a signed-in user. | `components/dashboard/DashboardApp.tsx:118-124`; `components/admin/AdminGate.tsx:13-25`; `app/login/page.tsx` |
| P-18 | **Admin chrome is not in the admin layout.** `app/admin/layout.tsx` only gates; each of nine views wraps itself in `AdminLayout`, so the sidebar remounts on every navigation, the opposite of what the dashboard shell was built to avoid. | `app/admin/layout.tsx:3-5` |
| P-19 | **Cookie notice covers the app.** It is rendered in the root layout for every route at `z-[60]`, above dashboard overlays (`z-50`), bottom-right where snackbars and editor controls sit. | `app/layout.tsx:72`; `components/legal/CookieNotice.tsx:37` |
| P-20 | **Images and video are unoptimised.** 33 `<img>` and 11 `<video>` tags, zero `next/image`, and the lint rule that would flag it is turned off. Caption fonts are uncompressed TTF up to 704 KB each (2.65 MB total); WOFF2 would be roughly a third. | `.eslintrc.json:5`; `app/globals.css:278-335`; `public/fonts/` |
| P-21 | **13 controls are marked as fake** by `NotWiredBadge`: analytics (all figures sample data; score "picked at random"), scheduler (best-time windows and hook refresh), folders (kept in the browser tab only; topic filters never match), upload options (filler/silence cut, sound effects, auto-zoom), studio auto-zoom (preview only). The revamp should decide wire, hide or cut for each. | `components/dashboard/ViralAnalyticsView.tsx:135`, `:345`; `SocialSchedulerView.tsx:198`, `:267`; `DashboardHomeView.tsx:709`; `ProjectFoldersView.tsx:599`, `:707`, `:781`; `UploadModal.tsx:848`, `:882`, `:925`; `studio/panels/FormatPanel.tsx:69` |
| P-22 | **Two dropdown implementations.** `ui/Select` in 7 files, native `<select>` 11 times in 5 files. | section 4 |
| P-23 | **Env template gaps.** `NEXT_PUBLIC_GOOGLE_CLIENT_ID` is not in `env.local.example`; the example API URL is plain HTTP on a raw IP, which a browser will block as mixed content from an HTTPS site; both example files are git-ignored. | `env.local.example:1`; `lib/googleAuth.ts:18`; root `.gitignore:30-32` |
| P-24 | **No security headers.** No CSP, frame, HSTS or content-type headers; `X-Powered-By` left on. | `next.config.mjs:9-21` |
| P-25 | **Platform list may not match the product decision.** The connect callback accepts TikTok and X, and the privacy policy, terms, cookie policy and sign-in showcase all describe TikTok and X publishing. If the product is YouTube + Instagram only, public legal text overstates what is collected. Needs the owner's confirmation; I did not verify the backend. | `app/dashboard/connect/[platform]/page.tsx:9`; `app/privacy/page.tsx:11`, `:51-64`; `app/terms/page.tsx:43-44`; `app/cookies/page.tsx:51`; `components/auth/AuthShell.tsx:21` |

### Low

| # | Problem | Where |
|---|---|---|
| P-26 | `framer-motion` is installed and never imported. | `package.json:25` |
| P-27 | The landing and editor-landing pages are client components from the top, so static copy (FAQ text, sections) is hydrated for no reason. | `components/landing/LandingPageView.tsx:1`, `:26-43` |
| P-28 | `/data-deletion` and `/unsubscribe` are fully client pages only to read one query parameter; the static policy text could be server-rendered with metadata. | `app/data-deletion/page.tsx:1`; `app/unsubscribe/page.tsx:1` |
| P-29 | The inline "hydration-fix" script observes the whole document forever to strip Grammarly attributes, while `suppressHydrationWarning` on `<html>` and `<body>` already covers the case. | `app/layout.tsx:31`, `:41-68`, `:70` |
| P-30 | Development loads a script from `unpkg.com` (React Grab) before hydration. Dev only, but it is a third-party script in a project whose policy says there are none. | `app/layout.tsx:34-40` |
| P-31 | `darkMode: ["class"]` and a hard-coded `class="dark"` with zero `dark:` variants: the setting does nothing. Decide dark-only (remove it) or real theming (build it on tokens). | `tailwind.config.ts:5`; `app/layout.tsx:31` |
| P-32 | `backdropBlur.xl: "24px"` repeats Tailwind's default. | `tailwind.config.ts:31-33` |
| P-33 | `w-13 h-13` is not a Tailwind class; the element has no size. (In a dead component.) | `components/skeletons/ClipListSkeleton.tsx:11` |
| P-34 | Logo drawn twice by hand (`icon.svg` and `LogoMark`), kept in sync by a comment. | `app/icon.svg:2`; `components/ui/LogoMark.tsx:1-4` |
| P-35 | `ScoreRing` clamps the arc but not the number or the label. | `components/ui/ScoreRing.tsx:26-28`, `:44` |
| P-36 | `StatusPill`'s pulsing dot and all `animate-spin` / `animate-pulse` uses (58) ignore reduced motion; only the caption and landing animations respect it. | `components/ui/StatusPill.tsx:38`; `app/globals.css:132`, `:173`, `:253`, `:269` |
| P-37 | Legal pages use plain `<a>` for internal links (full page reload) and external links have no "opens elsewhere" cue. | `app/terms/page.tsx:12`; `app/privacy/page.tsx:36`, `:121`; `app/data-deletion/page.tsx:23`, `:34` |
| P-38 | DejaVu faces declare `font-weight: 100 900` over a single bold file, so "regular" text in those faces renders bold. Intentional for export parity, worth knowing. | `app/globals.css:278-283`, `:323-335` |
| P-39 | `EmptyState` lives in `skeletons/`, shows a shimmer block as its default icon, and is unused; real empty states are hand-built per view. | `components/skeletons/EmptyState.tsx:4-16` |
| P-40 | `public/landing/` is an empty, unreferenced folder. | `public/landing/` |
| P-41 | `LEGAL_UPDATED` is exported but only used inside its own file; `AdminPaymentsView` lives in `components/payments/` while its siblings are in `components/admin/`. | `components/legal/LegalPage.tsx:18`; `app/admin/payments/page.tsx:1` |
| P-42 | `overflow-x-hidden` on `<body>` hides horizontal overflow bugs instead of fixing them. | `app/layout.tsx:70` |

---

## What the revamp must not break

- The caption and word keyframes in `globals.css:98-273` and the eight `@font-face` rules at `:278-335`. They mirror the backend export; changing names or timings makes the preview lie about the output.
- The seven `@fontsource` caption faces, four of which are referenced only through backend data.
- The `neutral-500` override (`tailwind.config.ts:16-18`) and the global amber focus ring (`globals.css:6-11`).
- The default border colour supplied by `* { border-border }`.
- `Referrer-Policy: no-referrer` on the two OAuth callback routes, and the way both callbacks strip `code`/`state` from the URL.
- Every word of the legal pages, `BusinessDetails`, and the cookie-notice dismissal key listed in the cookie policy (`app/cookies/page.tsx:9`).
- The URL shapes in section 1: OAuth redirect URIs (`/login/google`, `/dashboard/connect/<platform>`), email links (`/unsubscribe?token=`), Meta's status link (`/data-deletion?code=`) and `/dashboard/settings?tab=` are registered with or sent to third parties.
