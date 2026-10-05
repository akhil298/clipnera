# Lovable visual and layout study (with v0 and Bolt)

Prepared for the Clipnera Wave 6 redesign, 4 October 2026. This is the companion to `research/lovable.md`, which covers behaviour. This document covers how things look and sit on the page.

## How to read this

- **Evidenced** means I saw it in a public source, which is linked. For CSS values, the source is Lovable's rendered page HTML and its public stylesheet (`lovable.dev/assets/globals-*.css`), which I read as text. **Inferred** means I reasoned it from something evidenced, and I say what from.
- I could not sign in, so the dashboard, editor and settings come from Lovable's docs, one official dashboard screenshot and the changelog. The signed-out landing, templates and pricing pages come from their live HTML. The dashboard screenshot is a bit older than the current product (it still shows the **Resources** item, which the changelog says was removed), so treat its details as close but not exact.
- Pixel values come from Tailwind classes. Lovable's spacing unit is `--spacing: .25rem`, and its radius utilities are multiples of that unit (`rounded-4` = 16 px, `rounded-7` = 28 px). Evidenced: [globals.css](https://lovable.dev/assets/globals-DmMfIiy2.css).
- Clipnera's palette rule still applies: amber on neutral, with emerald, rose and sky for status only. Where Lovable uses blue, pink or rainbow gradients, the recommendations translate them into amber or neutral.

## 1. Lovable's visual system ("Pulse")

**Type**
- Evidenced: one variable sans for everything, `"Camera Plain Variable"`, with a system fallback. Weights in between the usual steps: titles use **450**, headlines and leads use **480**, display uses **700**. ([globals.css](https://lovable.dev/assets/globals-DmMfIiy2.css), [fonts.css](https://lovable.dev/assets/fonts-yKhYizLu.css))
- Evidenced: the scale is plain Tailwind sizes: 12 / 14 / 16 / 18 / 20 / 24 / 30 / 36 / 48 px. Letter spacing tightens as size grows: normal up to 16 px, −0.01em at 20 px, −0.015em at 24 px, −0.025em at 36 px, and −0.05em at display sizes. Line height runs from 1.5 (small text) down to 1.0 (display).
- Evidenced: body text defaults to the *tertiary* foreground colour. Titles use the primary colour. So hierarchy comes from colour and weight more than from size.
- Evidenced: controls use their own "control" styles: 14 px, weight 400, line height 1.5, with a "strong" variant at 450.

**Colour and surfaces**
- Evidenced: the neutrals are oklch greys with almost no chroma (0.002) and a warm hue (107). In dark mode surfaces get *lighter* as they rise: base 23% L, primary 24.7%, secondary 27.2%, quaternary 32.8%. In light mode they go from 97% (base) up to pure white (secondary). The accent is blue. ([globals.css](https://lovable.dev/assets/globals-DmMfIiy2.css))
- Inferred: the elevation model is the same one Clipnera's design system already uses (raised means lighter in dark mode). Clipnera's model is sound and needs no change.

**Border versus shadow**
- Evidenced: Lovable draws edges with shadow rings, not CSS borders. Surface shadows (`--shadow-surface-sm/xl`) stack a 1 px highlight, a 1 px base ring and a soft drop. Landing cards use a five-layer shadow whose first layer is a 1 px ring at 10% alpha. ([homepage HTML](https://lovable.dev/))
- Evidenced: thumbnails get their hairline from an `::after` border drawn *over* the image (black at 16% in light mode, white at 24% in dark mode), so the edge reads cleanly on any picture. ([templates](https://lovable.dev/templates))
- Evidenced: the v0 composer is the opposite case: a plain 1 px border that darkens on focus, with no shadow. ([v0.app](https://v0.app/))

**Radius**
- Evidenced (Lovable): 4–8 px for small controls, 12 px for thumbnails, 16 px for cards, 24–32 px for big panels, 28 px for the composer, and fully round for icon buttons and pills. 16 px (`rounded-4`) is the most common value on the homepage.

**Interaction feedback**
- Evidenced: hover and press feedback is a separate overlay layer, at 8% opacity on hover and 12% on press, so one rule covers every surface colour. ([homepage HTML](https://lovable.dev/))
- Evidenced: hover turns on **instantly** and fades off over 150 ms. Footer links use `group-hover:duration-0`, and checkbox glows use `transition:none` on hover with `.15s` on exit. ([globals.css](https://lovable.dev/assets/globals-DmMfIiy2.css), [dashboard css](https://lovable.dev/assets/dashboard-shared-XaZ9w73w.css))
- Evidenced: image cards go to 95% brightness on hover and 90% on press. Their images drop to 80% opacity on hover. ([templates](https://lovable.dev/templates))
- Evidenced: there is a `prefers-reduced-motion` branch for checkboxes, loaders and the composer halo. ([dashboard css](https://lovable.dev/assets/dashboard-shared-XaZ9w73w.css))

## 2. Landing page (signed out)

All evidenced from the [homepage HTML](https://lovable.dev/) unless marked otherwise.

- **Hero:** a full-viewport section (`min-h-dvh`) with everything centred. Behind it is a canvas of animated colour (`background-ambient`, which fades in and drifts with scroll parallax). The H1 is "Build something Lovable", 32 px / 1.1 at −1.28 px tracking, growing to 48 px / 1.1 at −1.92 px (−0.04em) from `md` up. One subline in the tertiary colour, 16 → 18 px: "Bring a new product, internal tool, or entire company to life."
- **Short screens:** when the viewport is under 400 px tall, the hero aligns to the top instead of the centre (`@media(max-height:400px)`).
- **The composer is the hero.** It is 608 px wide (`max-w-[38rem]`) from `md` up and full width below that. Details are in §3.
- **Sections below:** "One platform. Endless possibilities." (36 px, a gradient sweep on the second phrase), then three feature cards in a `lg:grid-cols-3` grid with 12 px gaps. Each card is 425–480 px tall, has a 16 px radius, a white fill and the five-layer shadow. Its top half is a live mini-demo and its bottom half (padding 16 → 24 px) holds the text: a 16/24 semibold title and a 14/24 grey body.
- **The "Refine your design" card** animates a selection. A heading in a mock preview gets a selection outline, then a small accent pill tagged **"h1"** pops in beside it (`scale(0.7)` → 1), and a cursor glides in. This is the select-to-edit idea taught visually, with no copy.
- **Section rhythm:** 104 px vertical padding, 160 px from `md` up. Next come logos ("Trusted by top brands"), case-study cards with big stat numbers, a "Millions count on Lovable" stats band, and then **the composer again** under "Ready to bring your idea to life?", followed by a five-column footer.
- **Header:** logo, Solutions / Resources / Community / Enterprise / Pricing / Security, then **Log in** and **Get started**.

## 3. The prompt box (composer)

**Lovable, evidenced** ([homepage HTML](https://lovable.dev/), [dashboard screenshot](https://docs.lovable.dev/introduction/dashboard-overview))
- **Shell:** 28 px radius, 12 px padding, secondary-surface fill. It has a 1 px white border, a 1 px ring at black/8 and the large Tailwind `shadow-2xl`. On hover the ring goes to black/12, and on focus-within to black/16. In dark mode the border is white/8.
- **Glow halo:** a blurred (6 px) gradient bar sits under the bottom edge at `opacity-0` and fades in over 200 ms ease-out. *Inferred:* it shows on focus or typing. Reduced motion turns the transition off.
- **Editor:** a ProseMirror field with a 40 px minimum height that grows to `max(35svh, 5rem)` and then scrolls. Text is 16 px with 24 px line height. The placeholder sits at 50% opacity and fades out in 150 ms: "Ask Lovable to create a blog about..." on the landing page, "Ask Lovable to create a prototype..." on the dashboard.
- **Inline chips:** mention and context pills sit at the start of the first line, and the text indent animates over 150 ms to make room (`--composer-chip-indent`). When a pill is dismissed, the indent drops back to 0.
- **Button row, left:** a round **+** button (32 px, translucent fill). On the dashboard it is followed by a **"Restricted"** chip with a lock icon, which shows project access.
- **Button row, right:** a **Build ▾** mode pill (32 px tall, ghost style), a microphone ("Transcribe", 32 px, 36 px on mobile), and the send button: a round filled arrow-up.
- **Before hydration:** the server-rendered HTML ships every composer button as `disabled`. So before JavaScript loads the controls are visible but inert, rather than missing or clickable-but-dead.
- **The + menu:** a popover anchored under the + with a **Search…** field at the top. Rows have an icon, a label and a chevron (Attach ›, Design ›, Connectors ›). The highlighted row has a solid accent fill.
- **Send label:** in Chat mode the send button reads **"Chat for free"** while the daily allowance lasts. ([Dashboard overview](https://docs.lovable.dev/introduction/dashboard-overview))

**v0, evidenced** ([v0.app](https://v0.app/))
- H1 "What do you want to create?". The composer is 690 px wide, 12 px radius, 12 px padding, 107 px minimum height, with 14 px text and the placeholder "Ask v0 to build…". It has a 1 px border that darkens on focus over 200 ms, and no shadow.
- Left: a model picker ("v0 Max", 28 px tall, 13 px text). A "Drop to attach" overlay covers the box when you drag a file over it.
- Below the box: suggestion chips (32 px, pill-shaped, icon + label: Contact Form, Image Editor, Mini Game, Finance Calculator) with a **Refresh suggestions** button.
- Motion: the easing is `cubic-bezier(.31,.1,.08,.96)`. A panel above the composer rises from `translateY(34px)` and opacity 0 over 500 ms.

**Bolt, evidenced** ([bolt.new](https://bolt.new/))
- H1 "What will you build today?" with the subline "Create stunning apps & websites by chatting with AI." The composer is 672 px wide (`max-w-2xl`), 24 px radius, with a 1 px border plus a soft halo shadow `0 0 40px -12px rgba(0,0,0,.35)`. The placeholder "Let's build a prototype..." sits in a 84 px minimum-height area padded 20 px.
- The row holds a bordered round **+** whose icon morphs into a trash icon (blur and scale cross-fade over 300 ms), a **Plan** toggle (lightbulb icon, `aria-pressed`, its label hides when the container is under 330 px), a mic (a waveform track takes over the row while you record), and a labelled send pill **"Build now"**. The send pill is 36 px tall with an accent fill, goes to 105% brightness on hover and 95% on press, and drops to 50% opacity when disabled. An "or start from" import row sits under the box.

## 4. Dashboard (signed-in home)

Evidenced from the [dashboard screenshot and docs](https://docs.lovable.dev/introduction/dashboard-overview) unless marked otherwise.
- **Layout:** a light, collapsible left sidebar (*inferred* about 260 px wide from the screenshot) beside a canvas. The canvas has a full-bleed gradient backdrop, and users choose that backdrop under **Appearance → Dashboard background**.
- **Hero:** a centred greeting, "Ready to build, Ines?" (about 30 px, semibold), with the composer directly below it. The composer is the only thing in the top half of the page.
- **Project sheet:** a large panel with rounded top corners (*inferred* about 32 px radius) rises from the bottom over the backdrop. It has segmented tabs **My projects | Recently viewed | Templates** on the left and **Browse all →** on the right, with project cards below. The tabs bar also has a **Search** entry that turns the tabs into a search field. ([Project search](https://docs.lovable.dev/introduction/project-search-and-find))
- **Sidebar:** a workspace switcher (avatar initial + name + chevron), then Home, Search (with a `⌘K` badge), and Connectors. Next come the **Projects** group (All projects, Starred, Created by me, Shared with me), then **Recents** (plain text rows). The bottom holds a "Share Lovable · 100 credits per paid referral" card, then the avatar and an inbox icon with a red dot.
- **Hover peek:** hovering a sidebar project shows a preview card with its screenshot, name, Published badge, owner avatar and last-edited time. ([Changelog](https://docs.lovable.dev/changelog), 21 Aug 2026)
- **Empty groups:** groups with nothing in them are hidden instead of being shown empty. "Owned by me" and "Shared with me" appear only when they have items. ([Changelog](https://docs.lovable.dev/changelog))

## 5. Project cards, Projects page, templates

- **Project card (evidenced, redesigned Sept 2026):** shows the name and a preview, plus a **Published** badge when the project is live. The whole card is clickable. Hover reveals a star and a **⋯** menu, and right-click opens the same menu, grouped as Copy / Open / Move / Edit. The thumbnail can be changed (Edit → Thumbnail). ([Dashboard overview](https://docs.lovable.dev/introduction/dashboard-overview), [Changelog](https://docs.lovable.dev/changelog))
- **Template card (evidenced, [templates](https://lovable.dev/templates)):** this card has no chrome of its own. It is a 16:9 thumbnail (`aspect-video`, 12 px radius, inner hairline, top-anchored crop) with text *below* it: the title truncated to one line and a 14 px tertiary description. A small category pill sits on the right. The **⋯** button is 28 px, hidden on devices that can hover until the card is hovered or focused, and **always visible on touch**. The grid goes 1 → 2 → 3 columns with 32 px gaps, 48 px from `lg`. A left rail of checkbox filters takes 2 of 12 columns.
- **Projects page (evidenced, Sept 2026):** the title sits on top with a toolbar below it: search, **Filter** and **View**. Filter opens one searchable menu, and each filter you apply becomes a removable chip, with **+** to add more and **Clear filters**. View switches grid or list and sets the sort. ([Project search](https://docs.lovable.dev/introduction/project-search-and-find), [Changelog](https://docs.lovable.dev/changelog))
- **Bulk select (evidenced):** drag across empty space or press Cmd+A on desktop, long-press on touch. A floating toolbar appears with the bulk actions plus **Clear** and **Cancel (Esc)**.

## 6. Project workspace (editor)

Evidenced from the [Editor](https://docs.lovable.dev/features/projects/editor), [Preview](https://docs.lovable.dev/features/projects/preview), [Preview toolbar](https://docs.lovable.dev/features/preview-toolbar) and [History](https://docs.lovable.dev/features/projects/history) docs unless marked otherwise.
- **Two panes:** chat on the left, live preview on the right, with a resizable divider. *Inferred:* the chat is roughly a third of the width, but I found no exact number. Evidenced from CSS: the resize handle takes the accent colour while active, and its hit area is widened to at least 32 px on coarse pointers. **Cmd+B** hides the chat for a full-width preview.
- **Top bar, left to right:** menu icon (hover to peek at the sidebar, click to pin, `[` toggles), project name with a draft switcher, History toggle, hide chat, and the tabs **Preview / Files / Code / More**. On the right sit the preview-toolbar toggle, Comments, avatars, **Share** and **Publish**. On narrow windows, tabs collapse into an overflow menu at the end of the toolbar.
- **Preview bar:** a device toggle (**Desktop / Tablet / Mobile view**), a page selector with a "Find page or enter path" field (hovering a page's icon shows Social and Search cards), **Refresh** (Shift-click restarts the preview environment) and **Open in new tab**. The CSS has `--device-corner-radius` tokens. *Inferred:* the phone and tablet views are drawn as rounded device frames.
- **Floating preview toolbar:** four modes, Select (S), Edit text (T), Draw (D) and Comment (C). Users can drag it anywhere. It snaps to the corners or to its bottom-centre default, it can be minimised, and it remembers its position for each project. When you select something, the element is outlined, gets a small accent tag pill (seen in the homepage demo: "h1"), and attaches to the composer as a chip. Cmd-click adds more elements.
- **Preview continuity:** the preview "keeps what you have on screen in place while Lovable works, instead of reloading". ([Changelog](https://docs.lovable.dev/changelog), 28 Aug 2026)
- **Preview states:** "Starting live preview…", a paused state ("Still building?" with **Keep building**), and error states, each with a **Try again** button.
- **History panel:** opens as a side panel with **History** and **Bookmarks** tabs. Each row shows a timestamp and a Published badge where it applies, plus **Revert**, a bookmark toggle and a ⋯ menu (full-screen preview, diff, jump to message). Clicking a row opens a read-only snapshot with **Back to latest**.
- **Design directions:** for a first UI prompt, Lovable shows three rendered directions side by side, with full-screen and thumbnail switching. Each direction has a **Describe changes** input and three suggestion chips. ([Design guidance](https://docs.lovable.dev/features/design-guidance))
- **Code mode:** a file tree with tabbed files (covered in `lovable.md`). It is irrelevant to Clipnera beyond the general idea of tabs living in the top bar.

## 7. Loading, skeletons, motion, empty states

- **"Thinking" shimmer (evidenced):** `.thinking-text` sweeps a gradient across the label from the quaternary to the primary foreground colour every 1.8 s, with trail and duo variants and a paused state. ([dashboard css](https://lovable.dev/assets/dashboard-shared-XaZ9w73w.css))
- **Small loaders (evidenced):** a status dot "pings" (scales to 2.67× while fading), a `loader-sweep` glides a highlight along a bar, and menus show a loading sweep while a page of items loads. ([globals.css](https://lovable.dev/assets/globals-DmMfIiy2.css))
- **Skeletons (evidenced):** skeletons are composed from radial and linear gradients of one `--skeleton-fill`, which draws circle and line shapes in a single layer. *Inferred:* they mimic avatar-plus-text rows. The only pulse animation is Tailwind's 2 s opacity pulse, and there is no shimmer sweep on skeletons.
- **Highlight on jump (evidenced):** jumping to a chat message fades a muted background behind it over 1.6 s, after a 0.8 s delay.
- **Small celebrations (evidenced):** the checkbox tick draws its stroke in 150 ms. The CSS also has `star-pop`, `heartbeat` and `shine` keyframes. *Inferred:* these are used for starring and for badges.
- **Home → workspace:** I found no evidence of a shared-element or view transition (`view-transition` does not appear in the CSS). *Inferred:* sending navigates to the editor, where the chat shows your message at once and the preview shows a "starting" state. The continuity comes from your prompt appearing as the first message, not from animation.
- **Empty states:** Lovable mostly removes empty sections instead of illustrating them (hidden sidebar groups, chips that appear only after a response). The dashboard always has a prompt box, so it is never truly empty. *Inferred* for the first-run project grid: I found no evidence of what it shows.

## 8. Settings and pricing

- **Account settings (evidenced):** a **dialog over the current page** on desktop, opened from the avatar or with **Cmd+.**. It has five sections: Account, Preferences, Security, Devices & apps, and This device. On a phone or a narrow window the same sections become full-width pages. ([Account settings](https://docs.lovable.dev/introduction/lovable-account-settings))
- **Workspace settings (evidenced):** a full page with a left sidebar and a **Search settings** box at the top that understands synonyms ("env" finds build secrets). Groups: General, Billing and usage, Insights, Access, Customization, Build & deploy, Security, Connectors. ([Workspace admin settings](https://docs.lovable.dev/features/workspace-admin-settings))
- **Appearance (evidenced):** set from the user menu. Theme is System / Light / Dark, plus Dashboard background.
- **Pricing (evidenced, [pricing HTML](https://lovable.dev/pricing)):**
  - The page opens with the title "Pricing" and one line of subcopy.
  - A **segmented Monthly / Yearly** toggle (pill track, 32 px items, a sliding indicator) carries a coloured "2 months free" note on Yearly.
  - Four plan cards sit in a grid of 1 → 2 → 4 columns (4 from 72rem), 16 px apart. Each card is built as a **card within a card**: an outer 16 px-radius surface holds an inner raised header panel (20 px padding) with the name (20 px), a one-line pitch, the price (36 px, tabular numerals), "/ month", a **credits select** inside the card ("100 monthly credits", 32 px tall) and **Get started**. The feature checklist sits below the header panel.
  - Rows line up across cards using CSS subgrid.
  - I found **no "Most popular" badge** in the HTML.
  - Below the plans come a row of secondary offers (Students, Campus, Kids, Security), then an FAQ. The FAQ includes a table of example prompts with their credit cost ("Make the button gray" costs 0.50).

## 9. Mobile

- **Landing (evidenced):** the H1 is 32 px. On mobile the composer drops its ring and large shadow for an 80% translucent fill with a backdrop blur and a smaller shadow. The mic grows to 36 px. The editor text stays at 16 px. *Inferred:* the 16 px keeps iOS from zooming on focus.
- **App (evidenced, [Mobile app](https://docs.lovable.dev/integrations/lovable-mobile-app)):**
  - **Swipe** between chat and preview instead of seeing them side by side.
  - Tapping the project name opens one **Project menu** with credits, Share/Publish tiles, Drafts, Files, settings and History.
  - The preview toolbar is hidden on narrow screens, including narrow desktop windows.
  - The `@` picker is trimmed to fit.
  - Dictation shows a live waveform.
  - There is no command palette.
  - Card ⋯ menus are always visible on touch, and long-press selects.

## 10. v0 and Bolt in brief, and what is now the norm

| Pattern | Lovable | v0 | Bolt | Norm? |
|---|---|---|---|---|
| Centred question headline over one composer on home | Yes | Yes | Yes | **Norm** |
| Composer radius | 28 px | 12 px | 24 px | Large, soft (20–28 px) except v0 |
| Edge treatment | ring + big shadow | border only | border + soft halo | Hairline edge is universal; shadow optional |
| + menu for attachments and context | Yes (searchable) | Drop to attach | Yes (+ morphs) | **Norm** |
| Mode toggle in the box | Build / Chat / Plan | n/a | Plan toggle | **Norm** (a plan or ask mode) |
| Model picker in the box | No | Yes | No (auto-routes) | Split; Clipnera has ruled it out |
| Voice input in the box | Yes | n/a | Yes, with waveform | **Norm** |
| Send button | Round arrow | n/a | Labelled pill "Build now" | Round arrow most common |
| Suggestion chips under the home box | No | Yes, with refresh | "or start from" imports | Common |
| Template/project grid below | Tabs in a sheet | "Start with a template", 1/2/3 cols, 16:9 | Marketing below | **Norm**: 16:9 thumbnails, text below |
| Workspace | Chat left, preview right | Chat left, preview right (third party) | Chat + files + code + preview ([third party](https://www.nocode.mba/articles/bolt-ai-new-guide)) | **Norm**: chat left, preview right |
| Select-to-edit on the preview | Toolbar with 4 modes | Design Mode: layers, properties panel, Apply ([docs](https://v0.app/docs/design-mode)) | Visual Edits select tool, on all plans since 3 Sept 2026 ([blog](https://bolt.new/blog/visual-edits)) | **Norm** in 2026 |
| Versions | History panel and drafts | Every Apply makes a chat version | Version history | **Norm** |

v0 differs in two places. It is the plainest of the three (a 12 px bordered box and a 14 px label), and its Design Mode adds a direct-manipulation properties panel with **Before / after**, Undo/Redo, Reset and **Apply**, where Apply becomes one new version. Bolt differs in having the most expressive composer controls: icon morphs, a recording waveform that takes over the button row, and a send button that names the action ("Build now").

## What Clipnera should take

All of these use `cn-*` tokens, stay inside amber/neutral, and fit the motion budget in `02-design-system.md` (150–250 ms, plus one 600 ms highlight).

**Landing**
1. **Make the composer the hero.** Use a full-height (`min-h-dvh`) centred block: a question headline (32 → 48 px, semibold, about −0.04em tracking), one muted subline, then the composer at about 608 px max width. Top-align it on screens under 400 px tall. Repeat the same composer above the footer.
2. **Replace Lovable's rainbow backdrop with one slow amber "ember" glow.** It sits behind the composer as a radial gradient at low opacity on `cn-bg`. It fades in once and stays static under reduced motion. The composer's focus halo becomes a blurred amber bar under its bottom edge (200 ms fade).
3. **Show, don't list, on feature cards.** Use three cards in a 3-column grid (12 px gap, `rounded-cn-xl`), each with a looping mini-demo on top. One should repeat the "h1" trick: a caption line gets selected, an amber **Caption** tag pops in, and the cursor arrives. Sections get 104 px vertical padding, 160 px on desktop.

**Home**
4. **Build the composer like this.** Use `rounded-cn-2xl` (or 24 px if the visual direction allows), 12 px padding, and a hairline edge plus one soft shadow in light mode or a surface step in dark. The editor starts at 40 px and grows to 35svh before it scrolls, with 16 px text. The bottom row holds **+**, then inline context chips, a spacer, the **Edit / Ask / Plan** mode pill, the mic, and send. There is no model picker.
5. **Give the send button explicit states.** Empty: neutral muted circle. Ready: amber fill with an arrow. Working: neutral circle with a stop square. Offline or no credits: disabled with a tooltip. Server-render every control as disabled until hydration, so nothing is clickable-but-dead.
6. **Show attachments as inline chips at the start of the first line.** For a video, show a 16:9 mini thumbnail, the duration and an ×. The text indent animates over 150 ms. Dragging a file over the box shows a full-box "Drop video to start" overlay (as in v0).
7. **Make the + menu a popover with a search field on top** and grouped rows with chevrons: Upload video, Paste link, Brand kit, Format. Use the current-item highlight in `cn-surface-active`, not amber (amber marks the one primary action).
8. **Add a greeting headline, then a project sheet.** Use a greeting ("What are we cutting today, {name}?"). Below the composer, a large rounded-top sheet rises with tabs **Recent | Projects | Templates** and **Browse all →**. Put the search entry inside the tab bar.
9. **Add suggestion chips under the composer** (v0 style): 32 px pills with an icon, for example "Find 5 viral moments" or "Add captions", plus a refresh button. Hide them once the user starts typing.

**Projects**
10. **Make the card a thumbnail with no chrome.** Use a 16:9 (or 9:16 for reels) thumbnail at `rounded-cn-lg`, an inner hairline drawn over the image, the title plus a one-line meta row below, and the whole card clickable. Status badges (Rendering in sky, Ready in emerald, Failed in rose) sit top-left on the thumbnail. Hover takes brightness to 95%, press to 90%. The ⋯ button appears on hover or focus and is always shown on touch.
11. **Lay out the grid and toolbar this way.** Grid of 1 → 2 → 3 → 4 columns, 24 px gaps (32 px on wide screens). Below the page title, a toolbar with search, a **Filter** button (one searchable menu, applied filters as removable chips, Clear filters) and a **View** button (grid or list, plus sort).
12. **Support multi-select** with drag-select, Cmd+A or long-press. Bulk actions go in a floating bottom toolbar with Clear and Esc.
13. **Polish the sidebar.** Hovering a project in the sidebar shows a peek card (thumbnail, name, status, last edited). Hide empty groups instead of illustrating them. An empty Projects page is just the composer with the line "Your first project starts here."

**Editor workspace**
14. **Split the screen into chat left, preview right.** The chat defaults to about 400 px, is resizable (with a min and max), and the divider glows amber while dragging, with a 32 px touch hit area. **Cmd+B** hides the chat. The preview keeps the playhead, zoom and selection when an edit lands, so it never reloads.
15. **Lay out the top bar left to right:** menu (hover to peek at the sidebar), project name with a version/draft switcher, History, hide chat, and the tabs **Preview / Timeline / Captions / More**. Then the right side: Share and **Export** (the single amber button). Tabs collapse into More on narrow widths.
16. **Add a floating preview toolbar** with Select (S), Edit caption text (T), Draw (D) and Comment (C). Users can drag it, it snaps to the corners or bottom-centre, and it remembers its spot. A selected clip, caption or region gets a 2 px amber outline and an amber tag pill, and is attached to the composer as a chip.
17. **Swap the device toggle for an aspect toggle** (9:16 / 1:1 / 16:9) plus a "Safe zones" overlay switch. Draw the frame with rounded device corners only in the 9:16 phone view.
18. **Show working state calmly.** Shimmer the step label (neutral to `cn-fg`, 1.8 s, static under reduced motion) and pulse a small amber live dot. Put the timer and credits used in More, not in the chat stream.
19. **Build the history panel** with History and Bookmarks tabs. Rows show the time, an "Exported" badge, Revert and ⋯. Opening a row enters a read-only snapshot with a top banner and **Back to latest**. Jumping to a message flashes it for 600 ms (Lovable uses 1.6 s, which is over our budget).
20. **Design the preview's own states** as centred cards inside the frame: "Preparing preview…", paused ("Still editing?" with **Keep editing**), and failed, with **Try again**.

**Settings and billing**
21. **Account settings open as a dialog** over the current screen on desktop (Cmd+.), and as full pages under 640 px. Workspace and billing get a full page with a left sidebar and a **Search settings** box that knows synonyms ("card" finds Billing, "logo" finds Brand kit).
22. **Pricing uses a segmented Monthly / Yearly toggle** with a sliding pill and a savings note in `cn-accent-text`. Plan cards are built card within card, with rows aligned by subgrid, the price at 36 px in tabular numerals, and the credit-amount select inside the card. The grid runs 1 → 2 → 4 columns. Credit packs go in a secondary row underneath, and the FAQ ends with a "what an edit costs" table.
23. **Show plan and credits in the sidebar footer.** A compact credit meter and the current plan sit above the avatar (Lovable puts its referral and upgrade cards there). Theme (System/Light/Dark) goes in the user menu. Skip custom dashboard backgrounds to protect the palette.

**Global**
24. **Settle the interaction model.** Hover is an 8% neutral overlay and press is 12%. Hover turns on instantly and fades off in 150 ms. Controls are 32 px tall (36 px on touch). Radii go: 8 px controls, 12 px thumbnails and menus, 16 px cards and panels, 20–24 px composer, and fully round for pills and icon buttons. Edges are hairlines (shadow rings or inner `::after` lines over media), never heavy borders.
25. **Use weight and colour for hierarchy before size.** Body text goes in `cn-fg-secondary`, and titles go in `cn-fg` at a medium weight (450–500 if the chosen variable font supports it). Tighten tracking as size grows (normal at 16 px or below, −0.025em at 36 px, −0.04em at display sizes).

## Gaps

- The exact chat-panel width and its limits, the dashboard's empty first-run grid, and any home → editor animation were not found.
- v0's workspace layout and Bolt's four-panel workspace come from third-party descriptions only.
- Dark-mode screenshots of the dashboard and editor were not available. The dark values above come from CSS tokens.
