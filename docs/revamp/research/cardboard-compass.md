# Cardboard "Compass" and the current editor UI — follow-up study

Product-design research, wave 6. Researched 4 Oct 2026 from public material only (no sign-in, no hands-on use). This is a follow-up to `docs/revamp/research/cardboard.md` (3 Oct). It doesn't repeat that study. It adds what was new and closes the gaps that study listed (layout, motion, export dialog, onboarding).

## How to read this

- **Evidenced**: stated or shown in a public source. The URL is given inline or as a key to the source list at the end.
- **Inferred**: my reading of the evidence, with the basis stated.
- **NEW**: not in `cardboard.md`. Items without this tag confirm or sharpen the earlier study.

Limits on the evidence:

1. **No pixels were seen.** I read pages as text: the fetch tool, raw HTML and the site's CSS bundle. Videos were read through their transcripts. Positions come from what the narrators say, plus text inside the marketing mockups.
2. **The home-page mockups are vendor illustrations of the app, not screenshots.** I treat their text as evidence of the *intended* UI. Where a mock and the shipped product could differ, I say so.
3. **The CSS tokens come from the marketing site's bundle** (`cardboard.ai/_next/static/...css`). The site draws its editor mockups with these tokens, and some class names are clearly editor-specific (`bg-timeline-track-bg`, `bg-chat-panel`, `--timeline-color-*`, `agent-review`). Even so, it's **inferred** that the logged-in app uses the same values.
4. **One tutorial narrator** (HowToHarbor, [TUT]) twice says "Kapwing" when he means Cardboard. The screen he describes is plainly Cardboard (usecardboard.com, the Director chat, the track picker). The video dates from April 2026, before the June redesign [CL #28] and the August sidebar change [CL #37].

---

## 0. What is Compass? (the headline finding)

- **Evidenced: `compass.cardboard.ai` does not exist publicly.** On 4 Oct 2026 the hostname returns no DNS record (`getaddrinfo ENOTFOUND`; `dig` gives an empty answer). By contrast, `cardboard.ai` resolves to 216.150.x.193. `https://www.cardboard.ai/compass` returns 404. `app.`, `docs.` and `help.cardboard.ai` don't resolve either.
- **Evidenced: "Compass" appears nowhere** in the home page, `/desktop`, the changelog (#1–#44), the YC company and launch pages, Product Hunt, the three YouTube videos or web search (five query variants). The page HTML contains no "compass" string.
- **Evidenced: something unreleased is coming.** The 14 Sep changelog entry ends: "we're heads-down on something bigger behind the scenes, so keep an eye out :)" [CL #42]. Two weeks later the Mac app and "Bring your own Claude or Codex agent" shipped [CL #44].
- **Inferred:** Compass is most likely an unreleased or private product, possibly a codename for that "something bigger", or the link is mistyped. I found no evidence of what it does, so **this document describes nothing as "Compass".** Everything below is Cardboard's current public editor.
- **Owner action:** if you have access to Compass (an invite, a screenshot or a different URL), send it over and I'll redo §0 from that source.

---

## 1. Editor layout: chat, preview, timeline, assets, resizing

| Item | Finding | Status |
|---|---|---|
| Chat position | **Right-hand side.** "we're now in the screen over here on the right-hand side, you will see that we have a conversation"; later: "if you go over here to the right, you can … just type it in over here and click on send" | **Evidenced, NEW** [TUT 1:35, 3:13] |
| Tool rail | **Left-hand side**, a vertical list of tools: aspect ratio ("up at the top on the left-hand side"), Import media, Layout, Sounds, Captions, Voice-overs, Text styles, Transitions, Filters, Capture frame, Settings (playback/tool/timeline shortcuts) | **Evidenced, NEW** [TUT 2:24–2:58] (Apr 2026) |
| App navigation | Since Aug, a separate collapsible left rail holds Home, Projects and Asset library ("the rail folds away when you want the room") | Evidenced [CL #37] |
| Asset bin | The mock shows a **"Library" panel** with a search box ("Search project media…"), an **"Add"** button, and a list where **each row puts the duration before the filename** ("0:04 furnace-wide.mp4", "0:03 voiceover-bf8c0be5.mp3"). AI-made files keep machine names (`voiceover-66643085.mp3`, `stock-cnc.mp4`) | **Evidenced, NEW** [HOME mock] |
| Preview | Sits in the centre above the timeline. Shows "0:00/1:04" plus a millisecond timecode "00:00:00.000". Press F for fullscreen | Evidenced [HOME mock], F key [CL #9] |
| Timeline | **Along the bottom**, with tracks stacked: "this will be audio, this will be video … laid out track by track" [TUT 3:00]. The ruler counts in seconds (0s–70s). Each track has its own header: in the mock, **tracks are named by purpose, not by number**: "Captions", "Matched replacement edit", "Voiceover", "Score". Each header has an "M" (mute) button. Clips are labelled with a shot index and a subject: "14 \| original", "22 \| forge", "23 \| hands" | **Evidenced, NEW** [TUT][HOME mock] |
| Properties | A properties sidebar (position, scale, rotation, opacity, blend, audio). Text and caption controls have moved onto the canvas as floating toolbars | Evidenced [CL #2, #40, #41] |
| Export | A top-bar button labelled "Export ⌘E" | **Evidenced, NEW** [HOME mock][TUT 3:25 "export on the top"] |
| Resizing | "Resize panels to fit how you work" [CL #1]; the left rail folds away [CL #37]. Default proportions, minimum sizes and collapse behaviour for chat or timeline: **not found** | Evidenced / gap |
| Mac app | Opens in "its own window, right next to everything else you're working on" | Evidenced [CL #44] |

**Inferred overall arrangement** (tutorial plus mock): `[app rail] [tool rail / library] [preview, centre] [chat, right]`, with the multi-track timeline spanning the bottom under the preview. It's the classic NLE layout with the inspector swapped out for the agent.

---

## 2. Agent: plan, progress, questions, and how edits land

**Plan and restatement**

- **Evidenced, NEW:** after the prompt, the agent's first message restates the job as a measurable plan: "I'll match your reference cut for cut: 73 shots across 30 subjects, from forges and furnaces to the moon landing, then narrate it fresh." [HOME mock]. So the "plan" is one sentence with counts, not a checklist.
- Evidenced: Mac page: "See the plan before it edits", "it plans the edit and builds the cut" [MAC]. **Still not found:** whether you have to approve the plan or whether it's simply shown as work begins. **Inferred** from the mock, where the plan line runs straight into work: it is shown, not gated.

**Progress**

- **Evidenced, NEW:** work collapses into a counted disclosure, **"Ran 5 commands"**. Expanded, it lists past-tense, human-readable steps, each naming its object: "Transcribed makers-reference.mp4", "Found archival footage: 'American Maker' (1960)", "Generated a video: 'Molten steel pouring from a furnace'", "Found stock footage: 'CNC machine cutting metal'" [HOME mock]. This is the "folds into one line" behaviour from [CL #35] made concrete.
- **Evidenced, NEW:** between batches the agent posts a short narrative status: "Shots are in. Laying them on the reference's cuts, with archival film for the speeches and a narrator reading each line." Then comes a second batch, "Ran 4 commands" [HOME mock]. Long turns therefore alternate prose and command groups.
- **Evidenced, NEW:** the B-roll card shows a **funnel counter**: "Searching the web" → "0 clips found" → "Watching 132 clips for the best fit…" → "1 of 132 fits the line" → "Best match" → result card "Welder at work in a steel shop · Archival footage · 0:08 · Added at 0:14" [HOME mock]. Progress is shown as numbers the user can believe, and the result says *where* it landed.
- **Evidenced, NEW:** the moment finder shows "Finding moments…" → "3 moments found", with markers on a 0:00–50:10 source bar. Each moment is a quote card: "It found the leak faster than I did." [Story · 15:26 · 0:17], [Advice · 29:10 · 0:32], [Hot take · 43:50 · 0:13] [HOME mock]. **This is almost exactly Clipnera's core job.**
- **Evidenced, NEW (CSS):** a `composer-working` animation, a bar sweeping across the composer (1.6 s, ease-in-out, infinite). It suggests the "working" signal lives **on the composer**, not as a spinner in the thread. There is also `breathe` (opacity 0.7↔1, 2.5 s) and `pending-sheen` (a 3.6 s linear sheen on pending items) [CSS]. Mapping each animation to its element is **inferred** from its name.
- **Evidenced, NEW (CSS):** `.agent-review` is an absolutely positioned overlay with a radial dark scrim that fades in, holds and fades out over 2.6 s [CSS]. **Inferred:** this is the visual cue for the agent "looking at the actual frames" after an edit [CL #34], drawn over the preview.

**Asking questions**

- **Evidenced, NEW (first-hand):** the music question appears in the right-hand chat as a **track list with a play button per track and a "Confirm" button**: "click on the play button. This will allow you to listen to any one of these tracks … select the one … click on confirm" [TUT 1:40–1:55]. The run then continues: "it is still thinking, planning its next steps" [TUT 2:10].
- Evidenced: grouped multi-part questions [CL #13]; layouts, music and voices picked inline [CL #27]; the original request resumes after the pick [CL #40]; Light / Balanced / Tight cleanup picked in chat with a preview [CL #21].

**How edits land**

- **Evidenced, NEW (mock):** the "Direct it" card pairs the chat reply "Done. Intro trimmed and captions added." with an **on-timeline annotation "4s → 2s"** on the trimmed clip, plus "Caption" chips on the new caption clips [HOME mock]. This is the only public hint of a diff-style marker. **Inferred:** it's a marketing illustration, and whether the shipped timeline draws before→after labels is **not found**.
- **Evidenced, NEW (mock):** the final message reports counts and editability: "Your 65-second documentary is ready: 73 shots cut to the reference, 29 generated scenes alongside archival and stock footage, and 13 narrated lines with captions. **Every shot is its own clip, so you can swap any of them.**" It then hands back with the composer placeholder "What should we do next?" [HOME mock].
- **Evidenced, NEW (CSS):** the timeline has a dedicated `--timeline-color-collision` (amber #ffbf00) and an amber `fx-badge` [CSS]. **Inferred:** overlaps and conflicts are flagged in amber on the clip, and clips with effects carry a small badge.
- Already known: one prompt is one undo [CL #29, #39, #42]; every message is a checkpoint [CL #14]; recovered versions are compared side by side [CL #38]; "REV" badge [CL #40]. **Still not found:** per-clip "AI changed this" highlights, per-change accept/reject, a before/after compare.

---

## 3. Media, B-roll, captions, export

- **Upload (NEW, first-hand):** on the home screen you "click on this area, or … drag and drop our images, videos, or audio", and uploaded media appears as a row "just over here at the bottom" of the prompt card before you send [TUT 0:37–0:50]. Since Aug, clips come first and the prompt follows [CL #38]. Evidenced.
- **Asset library:** search, type and length filters, "Add to project" next to Download [CL #37, #38]. The mock adds per-project "Search project media…" and "Add" [HOME mock]. Evidenced.
- **B-roll:** searches the web and archives, "watching" candidates and placing the best one at a stated timestamp [HOME mock][CL #31]. Since Sep, the start point is chosen by watching the clip, and title cards are skipped [CL #42]. Web-sourced B-roll is a Creator-tier feature [HOME pricing]. Evidenced.
- **Generated media (NEW):** the "Build the story" mock offers a type switch, "Video | Image | Music | Sound effect", with a "Generating…" state. Graphics are made "from a single line, editable on your timeline" [HOME mock]. Evidenced.
- **Voice clone (NEW):** a guided recording flow: "Read this aloud", step "2 / 4", a script paragraph, a timer "0:27", "Keep reading · 3s to go", "Skip", "Clone voice ↵" [HOME mock]. Evidenced.
- **Transcript editing (NEW):** the transcript view shows timestamped lines with an inline **"Retake"** tag on the false start, plus a header total **"−6s of dead air"** [HOME mock]. Evidenced.
- **Captions:** 21 styles, 9 of them "Behind Subject" [CL #40]. The on-video caption toolbar offers word lock and Apply to all [CL #40]. The captions panel shows the full transcript as one paragraph [HOME mock]. Evidenced.
- **Export dialog (NEW, first-hand):** choose a **video file** or an **NLE package** (Final Cut, DaVinci, Premiere). Then pick a **resolution**. **Advanced settings** cover frame rate, quality, format and codec. The dialog shows the **total duration**, and the button reads **"Export video"** [TUT 3:25–3:50]. High quality has been the default since Aug [CL #38]. Every export is checked [CL #43]. Evidenced.
- **Render card (NEW):** "Conference keynote · 1:02:14 · 4K · MP4" → "Rendering…" → ✓ "Done", with "12× faster than real time" [HOME mock]. Evidenced.
- **Share (NEW detail):** "Copy link" → "Link copied", "3 comments", "Shared with team" with avatars, and presence chips "Maya · Viewing" / "Leo · Viewing" [HOME mock]. Evidenced.

---

## 4. Visual language

All rows are evidenced from the CSS bundle [CSS] unless marked otherwise. Use in the app is inferred (see limit 3).

| Aspect | Cardboard | Note |
|---|---|---|
| Type | **Geist** for UI, **Geist Mono** for numbers and timecode. Tailwind scale 12/14/16/18/20/24 px | NEW |
| Theme | Dark only, neutral greys. Page `#141414`, base `#1a1a1a`, surface `#202020`, raised `#262626`, elevated `#2e2e2e`, sunken `#161616`, chat panel `#1f1f1f` | NEW. Five surface steps, all neutral |
| Text | primary `#f5f5f5`, secondary `#c2c2c2`, tertiary `#999`, disabled `#737373` | NEW. Four tiers |
| Accent | **"primary" is near-white `#f4f4f4`** on dark text, not a hue. Colour is kept for meaning only | NEW. Matches our amber-as-signal rule |
| Borders vs fills | Hairlines: `border-subtle` = white at 6%, `border-strong` = white at 16%. The panel `border` is `#0a0a0a`, darker than the surface, so panels read as **separated by gutters**, not outlined. Depth comes from stepped fills | NEW. Fills first, hairlines second |
| Radius | Base 8 px (`--radius: .5rem`), md 6 px, UI-xl 12 px, 2xl 16 px, 3xl 24 px. 4 px is common on small chips and clips | NEW |
| Timeline colour | Every clip type gets a hue: video blue, audio green with bright waveform, caption and text purple, image violet, adjustment orange, code rose, collision amber, plus hover variants | NEW. **Don't copy.** Clipnera's palette forbids it |
| Destructive | text `#e37878`, fill `#933` | NEW |
| Motion | tokens: fast 120 ms, base 180 ms, slow 280 ms. **All set to 0 s under reduced motion.** Easing: standard `(.2,0,0,1)`, decelerate `(.16,1,.3,1)`, accelerate `(.4,0,1,1)`. Default transition 150 ms | NEW. Short and calm |
| Motion cues | `composer-working` sweep, `breathe`, `pending-sheen`, `shimmer` text for waiting, `enhance-word-in` (each word un-blurs over 0.4 s, used by "Improve prompt"), `agent-review` scrim, `text-frame-draw` (a stroke draws round text on hover), Sonner toasts | NEW |
| Iconography | Glyph keys inside labels ("Export ⌘E", "Clone voice ↵") and single-letter track toggles ("M") | NEW (mock). Icon family **not found** |
| Density | Compact: 12–14 px UI text, duration-first list rows, a seconds-based ruler | Inferred from the mock text and type scale |

---

## 5. Onboarding and the empty project

- **Evidenced, NEW:** the home screen is a greeting plus a drop zone: "What are we editing today, Ishan?", a model chip, then "Drag and drop or click here to add your media files". Below sits **"Recent"**, a row whose **first card is "New project · Start empty"**, followed by project cards showing "2 hours ago · 16:9 · 0:27" (age · aspect · length) [HOME mock, desktop].
- **Evidenced, NEW:** the marketing composer has an **"Auto" model dropdown**, an **"Improve prompt"** button that rewrites the prompt with a word-by-word reveal (CSS `enhance-word-in`), and **template chips**: Launch Video, UGC, Explainer, Montage, Product Demo, Podcast Clip, Product Ad, Keyframed Portal, Paper Collage, Talking Head, Invisible Glass [HOME].
- **Evidenced, NEW (first-hand, Apr 2026):** the home composer had a **canvas-size or aspect picker on the left** ("auto" or a fixed ratio) and the **model picker ("Auto") on the right** [TUT 0:08–0:35]. Choosing the aspect ratio up front was later partly automated: "Let Cardboard choose the right aspect ratio for you" [CL #27].
- Evidenced: footage first, so the prompt appears once clips are in, and you can send with no text [CL #38]. The prompt-first home dates from Jan [CL #10]. "Reimagined onboarding" arrived with the June redesign [CL #28]. Sample projects were removed from Recent in Aug [CL #37]. There's a 3-day trial with a card [CL #34]. The Mac Lite plan is free with no card [MAC].
- **Not found:** the first-run tour, the empty-timeline state inside the editor, and any coach marks.

---

## 6. What is new compared with `cardboard.md`

1. Compass doesn't resolve publicly (§0). The "something bigger" teaser is noted.
2. **Layout gaps closed:** chat on the right, tool rail on the left, tracks on the bottom, Export in the top bar (§1).
3. Library row anatomy (duration first), purpose-named tracks with mute toggles, shot-indexed clip labels (§1).
4. The **plan is a one-sentence restatement with counts.** Progress is **"Ran N commands"** with past-tense steps that name their objects, separated by short prose status lines (§2).
5. **Funnel counters** for B-roll ("Watching 132 clips… 1 of 132 fits") and moment-finding ("3 moments found", with typed quote cards) (§2–3).
6. The question UI is first-hand: a track list with play buttons and Confirm (§2).
7. The diff hint "4s → 2s" on the timeline, a closing summary with counts, and "Every shot is its own clip" (§2).
8. Full **export dialog** contents and the render card (§3).
9. A complete visual-token read: Geist, five neutral surfaces, near-white primary, 6% / 16% hairlines, 8 px radius, 120/180/280 ms motion zeroed under reduced motion, named working animations (§4).
10. Home anatomy: greeting, drop zone, Recent with "Start empty" first, template chips, Improve prompt (§5).

Still open: per-clip AI-change highlighting, plan approval gating, whether the timeline locks during a run, what happens when a run finishes in the background, and anything about Compass.

---

## What Clipnera should take

These copy workflows, not trade dress. Use the amber accent on neutral surfaces, with emerald, rose and sky for status only. Use Clipnera's own names, icons and type.

**Editor workspace**

1. **Use a fixed four-zone layout:** asset library (left, collapsible), preview (centre), conversation (right), timeline (bottom, spanning the preview). Put the panel splitters on `cn-*` spacing tokens and remember sizes per user. On mobile (360 px), stack preview, then conversation, then a compact timeline sheet. Basis: §1.
2. **Build depth from stepped neutral fills, not outlines.** Use three to five surface steps, hairline borders only where content touches content, and a gutter between panels. Basis: §4.
3. **Reserve amber for signals:** selection, the playhead, the AI-just-changed marker and the primary CTA. Keep Clipnera's primary button styling. Never colour clips by type, since that would break the palette. Mark track type with an icon and label instead. Basis: §4, where Cardboard's rainbow timeline is the thing to avoid.
4. **Add a frame-check moment.** After an agent edit, briefly lay a scrim over the preview with "Checking the result…", then post the outcome in the chat. It needs a reduced-motion variant: a static label, no fade. Basis: `agent-review` and [CL #34].

**Conversation panel**

5. **Open each run with a one-sentence plan that has counts.** For example: "I'll pull 6 clips of 30–60 s from this 52-min episode, reframe to 9:16 and caption them." Show it, don't gate it, but let Stop interrupt. Basis: §2.
6. **Collapse tool work into "Ran N steps".** Rows are past tense and name their object ("Transcribed episode-12.mp4", "Scored 214 moments", "Found B-roll: 'city skyline at dusk'"). Put short prose status lines between batches. Basis: §2.
7. **Use funnel counters for any search.** "Scoring 214 moments… 6 strong candidates", "Watching 40 B-roll clips… 3 fit". Show only real numbers from the backend, never invented ones. Basis: §2, plus the brief's no-fake-numbers rule.
8. **Ask with inline pickers that carry a preview.** For music, caption style and layout, show a row per option with play/hover-preview and one Confirm, then resume the original request. Basis: §2 [TUT][CL #40].
9. **Close every run with a counted summary and an editability line.** "6 clips ready · 4 captioned · 2 need a look. Each clip is separate, so you can trim or swap any of them." End with an inviting composer placeholder ("What next?"). Basis: §2.
10. **Show "working" on the composer.** Use a thin amber sweep along the composer edge (static under reduced motion) and keep the input usable for queueing. Don't put a spinner in the thread. Basis: `composer-working`, [CL #30].

**Timeline**

11. **Put the AI's changes on the clips.** Each clip changed by the last run gets an amber edge plus a small before→after chip ("4.0s → 2.1s", "+ captions") that clears after the next manual edit. This also fixes Cardboard's hidden-undo problem: put "Undo this run" beside the summary *and* on the chip. Basis: §2 "4s → 2s", plus the gap in cardboard.md.
12. **Name tracks by purpose** ("Captions", "Voice", "Music", "B-roll"), each with mute and lock. Label clips with an index and subject ("03 · Hot take"). Basis: §1.
13. **Flag conflicts in amber on the clip** (overlap, caption off-frame), with the reason on hover or focus, not just colour. Basis: the `collision` token, WCAG.

**Asset library**

14. **Make rows duration-first:** "0:12 · stock-skyline.mp4". Filter by type, length and source (uploaded / AI / stock), and give AI-made assets readable names, not hashes. Basis: §1, where Cardboard's `voiceover-bf8c0be5.mp3` is the anti-pattern.
15. **Render moment cards as quotes:** the line, then a typed tag (Story / Advice / Hot take, from Clipnera's format list) · source time · duration, with markers on a source-length bar. Clipnera's clip-candidates view should look like this. Basis: §2 moment finder.
16. **Make B-roll results say where they landed:** "Added at 0:14 · Archival · 0:08", with Swap and Remove right on the card. Basis: §3.

**Export**

17. **Make export a two-way choice first:** "Video file" vs "Edit in another app" (only if Clipnera ever ships XML). Then resolution, then a collapsed Advanced section (frame rate, quality, format, codec). Show total duration and estimated size above the button. Basis: §3 [TUT].
18. **Show the render as a card with honest progress:** title · length · resolution · format → "Rendering…" with a real percentage → emerald "Done". Check the output before declaring it done. Basis: §3, [CL #43].
19. **Share via a link with presence and comment count** ("2 viewing · 3 comments"), comments pinned to timecode. This is for later waves. Basis: §3.

**Project home**

20. **Greet, then drop zone, then composer.** "What are we clipping today, {name}?" over a large drop or paste-link zone. The prompt field fills in once a source exists, and sending with no text runs the default "find the best clips". Basis: §5, [CL #38].
21. **Put "Start empty" as the first card in the Recent row,** and show age · aspect · length on each project card. Basis: §5.
22. **Add starter chips below the composer**, tied to Clipnera's 11 content formats but phrased as intents ("Podcast highlights", "Talking-head shorts"). Add an "Improve prompt" action whose rewritten words fade in (static under reduced motion). Basis: §5, `enhance-word-in`. No model picker, since models are set per plan.

**Motion (all screens)**

23. **Adopt three motion durations** (about 120 / 180 / 280 ms, set to 0 under `prefers-reduced-motion`) and two easings, standard and decelerate. Map them to `cn-*` motion tokens in `07-visual-direction.md`. Basis: §4.

---

## Sources

- [HOME] Cardboard home page, including the editor, home and share mockups and the FAQ: https://www.cardboard.ai/
- [MAC] Cardboard for Mac: https://www.cardboard.ai/desktop
- [CL #n] Changelog, entry n: https://www.cardboard.ai/changelog (#42 = 14 Sep, #43 = 21 Sep, #44 = 28 Sep 2026)
- [CSS] Site CSS bundle, fetched 4 Oct 2026: https://www.cardboard.ai/_next/static/immutable/chunks/{1lg7-wa103i57, 089rhtiwjn7af, 3-zj0d0g6rl64, 44-5y30i79b0k}.css
- [TUT] HowToHarbor, "How to Use Cardboard", 29 Apr 2026, transcript: https://www.youtube.com/watch?v=SCTllWh3hNk
- [EXP] "Use AI with Tech Dad", "Cardboard: The AI Video Editor That Runs in Your Browser", 18 Jun 2026, transcript (pipeline overview; says captions "dodge the speaker's face"): https://www.youtube.com/watch?v=uCH2IPjq5wA
- [DEMO] Launch YC demo, 55 s, 3 Feb 2026, transcript: https://youtu.be/xLBxatFM7uk. The narration covers only search by description, "make a 60-second vlog" and generated soundtrack. It has no UI detail.
- [YCL] Launch YC: https://www.ycombinator.com/launches/PM3-cardboard-agentic-video-editor ("vibe editing"; no UI detail)
- [PH] Product Hunt: https://www.producthunt.com/products/cardboard-3 (no Compass; tagline and maker comment only)
- Compass checks: `compass.cardboard.ai` (NXDOMAIN), `https://www.cardboard.ai/compass` (404), web searches for "compass.cardboard.ai", "Cardboard Compass agentic video editor" and "Cardboard Compass October 2026" (no relevant hits)
- Not retrievable: X posts (https://x.com/davj/status/2088379566549352524 returned 402), LinkedIn, and the crt.sh subdomain listing (timed out)
