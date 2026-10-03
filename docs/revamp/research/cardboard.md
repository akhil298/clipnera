# Cardboard — reference study

Competitive Analyst, UI revamp wave. Researched 3 Oct 2026 from public material only (no sign-in, no hands-on use).

## How to read this

- **Observed** — stated in a public source; the source key in brackets points to the list at the end.
- **Inferred** — my reading of the evidence; the basis is stated.
- **Not found** — I looked and found nothing public. Nothing is filled in by guesswork.

Three limits on the evidence, which apply to the whole document:

1. **No pixels were seen.** Pages were read as text through a fetch tool. I could not watch the demo videos or look at screenshots, so nothing here describes actual on-screen motion, colours, or exact panel positions.
2. **Quotes are near-verbatim, not guaranteed verbatim.** The fetch tool returns text through a summarising model. Quoted wording should be re-checked against the live page before it is reused anywhere public.
3. **Almost all detail comes from Cardboard's own changelog.** It is the vendor describing itself. The third-party "reviews" found (OutlierKit, ToolWorthy, runany.dev, everydev, chatgate) are rewrites of vendor copy; none shows first-hand use, and OutlierKit says so itself [R1]. The only independent first-hand evidence is a handful of Hacker News comments [HN].

Two changelog items came back under different entry numbers on different reads (the stop button: #30 or #34; "pick which version to keep": #34 or #38). The features are Observed; the exact entry is uncertain and is marked where it matters.

---

## 1. What it is, who it is for, layout

**What it is**

- Observed: "an agentic video editor" — you describe the edit in plain language and it "proposes a first draft on the timeline that you can refine further" [HN]. Product Hunt tagline: "the Cursor for video editing" [PH].
- Observed: the agent produces timeline operations on real footage, with a full manual editor underneath: multi-track timeline, keyframes, shot detection, beat sync, voiceover, voice cloning, background removal, captions, XML export to Premiere/DaVinci/FCP [HN].
- Observed: it has since added generation (video, images, music, sound effects, motion graphics from a prompt) and sourcing B-roll from the internet [HOME].
- Observed: runs in Chrome (and Edge for export); a Mac app for Apple Silicon launched 28 Sep 2026; phones and tablets are not supported; Firefox is not supported [HOME][CL #17, #44][HN].
- Observed: the chat agent is called **Director** [CL #3].
- Observed: YC W26, founders Saksham Aggarwal and Ishan Sharma, team of 8 [YC].

**Who it is for**

- Observed: YC profile says "growth and marketing teams" [YC]. Launch copy also names creators and media agencies [YCL]. Current home page is broader: "Make any video you can think of" [HOME].
- Inferred (from the pricing ladder of $8–$175/month and the shift in home-page copy): it began team/marketing-first and is widening to individual creators.

**Layout**

- Observed: three-stage flow on the home page — "Describe it", "Direct it", "Share it" [HOME].
- Observed: the home screen is "agent-forward" and starts a project from a prompt [CL #10]. Since Aug 2026 it is footage-first: you drop clips, and "the prompt appears once they're in, so you're not staring at an empty box working out what to say" [CL #38].
- Observed: a persistent, collapsible left sidebar holds Home, Projects and the Asset library [CL #37].
- Observed: inside the editor there are resizable panels [CL #1], a multi-track timeline with waveforms [CL #2], a canvas/preview you can edit directly on (drag, scale, crop, guides, snapping) [CL #4, #5, #7], a properties sidebar (position, scale, rotation, opacity, blend mode, audio) [CL #2], a chat panel (Director) [CL #3], and side panels for captions, effects and speed [CL #21, #40, #41].
- Observed: the chat is a side panel — the Mac page tells users to "open chat panel → choose agent → sign in" [MAC].
- **Not found:** which side the chat sits on, where the media library sits relative to the preview, the timeline's position, default panel proportions. (A timeline along the bottom is the convention, but I have no source for Cardboard's arrangement.)

---

## 2. Prompt-to-result sequence, moment by moment

What is public is a set of separate statements, not a recorded sequence. Laid out in order:

| Moment | What is known | Status |
|---|---|---|
| Before sending | If clips still need preparing, chat lists exactly which files are "uploading, preparing, analyzing, or transcribing" | Observed [CL #26] |
| Press Enter | Agent "always works from your current timeline" and checks its state before editing | Observed [CL #19] |
| First response | Prompts "start sooner", especially on large projects | Observed [CL #26] — no timings given |
| Plan | Mac page: "See the plan before it edits." | Observed [MAC] |
| Clarification | Agent "asks better questions when uncertain"; multi-part prompts are grouped; when several music tracks fit it shows an interactive picker; layouts, music and voices are chosen inside the chat | Observed [CL #13, #27] |
| After you choose | "Pick a track or a voice when it asks, and your original request carries on with that choice" | Observed [CL #40] |
| While working | "A long agent turn no longer reads like a wall of steps. It folds into one line while it works" | Observed [CL #35] |
| Thinking | "the agent's thinking folded right into the rest of what it's doing" | Observed [CL #36, #41] |
| Self-check | After a change it "looks at the actual frames", catches "a caption sliding off screen, a cut landing a beat early" and fixes it; it listens to the finished mix before calling an audio edit done; it holds "your timeline up against what you actually asked for" | Observed [CL #34, #39, #40] |
| Finish | Wraps up with a summary; says explicitly what it could not do | Observed [CL #39, #40, #41] |
| After | Clickable suggestions for the next step; thumbs up/down on replies | Observed [CL #8, #41] |

**What stays interactive while the AI works**

- Observed: you can keep typing. A prompt sent mid-run goes into a numbered, visible queue in the composer and fires when the previous run finishes [CL #30]. Queued prompts sit in a draggable row [CL #35].
- Observed: a dedicated stop button, separate from send, so stopping does not lose what you have typed [CL #30 or #34].
- Observed: "Take over on the timeline anytime" [MAC].
- **Not found:** whether the timeline is locked or editable *during* a run, and what happens if the user and agent edit the same clip.

**Not found in this section**

- Whether reply text streams token by token.
- Whether the plan is a separate approve/reject step or simply shown as the agent starts. "See the plan before it edits" is the only statement, and only on the Mac page.
- Whether edits appear on the timeline one by one as each tool call lands, or all at once at the end.
- Any latency figures for agent edits.
- What the "one line" contains (step name, counter, timer).

---

## 3. Prompt input details

- Observed — **attachments/references:** attach a reference video or image; the agent "studies its color, pacing, and fonts, then edits to match"; it can also lift audio from a reference [CL #35]. Home page: "Use reference links to videos you like" [HOME].
- Observed — **empty prompt allowed:** "Send just the clips if you like, with nothing written" [CL #38].
- Observed — **model picker** in the chat, "so you can choose the model that fits the job" [CL #4]; founders confirm a dropdown for the orchestration model [HN]. On Mac you can switch from Director to your own Claude or Codex subscription, "No API keys. No terminal." [MAC][CL #44].
- Observed — **suggestions:** clickable next-step suggestions appear mid-conversation [CL #8].
- Observed — **multi-turn:** conversations persist, you can switch between them [CL #3]; multiple chat tabs and one-click history clear [CL #2]; history is account-level and survives refresh and device change [CL #20].
- Observed — **queue:** numbered, reorderable (draggable row) [CL #30, #35].
- Observed — **pointing at a moment:** "point it at any moment and ask what it sees" [CL #34].
- Observed — **precision by wording:** "exposure +0.8, temperature -20, every clip" is honoured exactly [CL #36].
- Observed — a third-party listing calls the input a "natural language command bar" [R4]; this is not first-hand and may be the listing's own wording.
- **Not found:** slash commands; @-mentions; context chips for selected clip, time range or asset; how "point it at any moment" works mechanically (playhead position, selection, or typed timecode); prompt templates or an example gallery inside the app; voice input.

---

## 4. How edits land on the timeline; inspect, tweak, reject

- Observed: the agent writes to the same timeline the user edits; the result is a "first draft on the timeline that you can refine further" [HN]. Founders describe the approach as giving the agent tools and letting it choose its course, not a fixed workflow [HN].
- Observed — **one prompt, one undo:** a multi-clip reframe "applies to all of them in a single pass and a single undo" [CL #29]; retakes, filler and gaps are removed under a single undo [CL #39]; typing in a motion-graphic property collapses to one undo [CL #42].
- Observed — **preview before commit** for some operations: transcript cleanup offers Light / Balanced / Tight with a preview before you commit [CL #21]; layout presets show a live arrangement preview [CL #13]; highlights can be played in a flyout before they go to the timeline [CL #24]; voices can be previewed before generating [CL #15].
- Observed — **tweak by hand:** captions have an on-video toolbar with word-level locking and "Apply to all" [CL #40]; text has a floating toolbar next to the words [CL #41]; motion graphics have an editable properties panel where "the canvas updates as you type" [CL #42]; transitions have controls "right there at the seam" [CL #12]; keyframes are diamond markers you drag [CL #33].
- Observed — **reject:** undo button "on the bottom right of each user message in the chat" [HN]; roll back to any message [CL #14].
- Observed — **honest refusal:** if there is too little material, "it comes back to you" instead of padding [CL #39].
- Observed: reversed clips are marked "REV" on the timeline [CL #40].
- **Not found:** any visual marking of which clips the AI just changed (highlight, badge, diff view); per-change accept/reject; whether clips are labelled as AI-placed.
- Inferred (from a third-party article that describes the agent's output as "a diff to the timeline" [R5]): the internal model is operation-based. That article mixes reported facts with the author's own speculation, so treat it as weak.

---

## 5. Undo, version history, compare

- Observed — **chat checkpoints:** "Every message in your AI chat is now a save point. Roll back to any earlier moment and your timeline returns exactly as it was" [CL #14].
- Observed — **per-message undo button** at the bottom right of each user message [HN]. Before a founder pointed it out, a user could not find it: "I wanted to undo one AI edit but couldn't find if there is undo button" [HN].
- Observed — **autosave:** projects back up to the cloud while you edit, "so nothing waits on a save button" [CL #11].
- Observed — **recovered versions:** shown side by side with the current one, with "time, clip count and length for both"; "Nothing reaches your editor until you say so" [CL #34 or #38].
- Observed — **published vs draft:** the share page tells viewers whether they are watching the latest edits or an unpublished version [CL #32].
- Observed: git-like version control is listed by Cardboard as an unsolved "hard problem" [HP], and "video git" was named as a roadmap item at launch [HN].
- **Not found:** a browsable version-history list; named versions; branching; a visual before/after compare (split view, toggle, wipe); redo after rollback; whether rolling back discards later messages.
- Inferred (from version control being on the hard-problems list): full version history is not shipped; checkpoints plus recovery are the current substitute.

---

## 6. Errors and long jobs

- Observed — **agent failure:** "stops when it's stuck rather than going round again, and wraps up with a summary" [CL #40]; "closes out and tells you what it could not do" [CL #41]; reports requests it only partly completed [CL #39]; "says so plainly when it can't" [CL #37].
- Observed — **file errors:** "If a file truly can't be read, we'll tell you exactly what to convert it to" [CL #15/#36]; friendly nudges on unsupported browsers and missing graphics support [CL #17, #20].
- Observed — **background work:** uploads, analysis and transcription continue when the tab is in the background and re-sync when you return [CL #34]; large media is prepared in the background so playback stays smooth [CL #19].
- Observed — **export failure:** every export is checked; if picture or sound is missing "we finish it in the cloud or tell you what's missing" [CL #43]; render recovers mid-failure [CL #16]; "honest" progress percentage, no frozen indicator [CL #14].
- Observed — **stalled graphics:** automatic retry, plus a retry button [CL #43].
- Observed — **project load:** project name and thumbnails appear first, a detailed progress view shows what is loading, with a clear "preparing" phase and resume after import snags [CL #19, #22].
- Observed: a public status page exists [HOME → status.cardboard.ai].
- **Not found:** notifications of any kind (in-app toast, browser notification, email) when a long job finishes; whether an agent run survives closing the tab; a jobs/activity panel; credit-exhausted or rate-limit states; the wording or visual treatment of error messages.

---

## 7. Media and assets

- Observed — **upload:** drag in video, audio, images; HEIC/HEIF, ProRes, Dolby audio supported [CL #9, #36]. Per-file limit was 5 GB, then 10 GB on Pro [HN][CL #13].
- Observed — **local-first in the browser:** editing uses the File System Access API so full footage is not uploaded; this is why Firefox is unsupported [HN]. On Mac, "Footage stays on your Mac… nothing to upload before you start editing" [MAC].
- Observed — **asset library:** all uploads across projects, with search, type filter and length filter [CL #37]; "Add to project" beside Download; copies are independent per project [CL #38].
- Observed — **semantic search:** find moments "by what's said, what's on screen, the objects in frame, filenames, and scene details"; results are timestamped thumbnails you can preview and trim onto the timeline [CL #3, #24].
- Observed — **media insights:** preview shows visual and speech context so you can judge a clip without watching it all [CL #24].
- Observed — **stock/B-roll:** "Ask for a shot and Cardboard goes and finds it. It searches stock libraries and public archives, picks the clips that actually match", places them and handles credits [CL #31]; selection is made by watching the clip, avoids letterboxed clips and title-card openings [CL #41, #42]. Web-sourced B-roll and clips from social platforms are Creator-tier [PRICE].
- Observed — **music and SFX library:** browse by genre and mood, drop onto the timeline, tracks preload on hover [CL #5, #10].
- Observed — **voices:** 100+ voices filterable by gender, age, accent, language; clone from a short sample [CL #8].
- **Not found:** which stock providers; whether the user can browse stock manually or only through the agent; folders/tags in the asset library; storage quotas.

---

## 8. Export and sharing

- Observed — **formats:** MP4; GIF with loop options; current frame as image; ProRes; XML for Premiere Pro, DaVinci Resolve and FCP with bundled assets, relinking and timecode [CL #4, #9, #15, #20, #36][HN].
- Observed — **resolution/limits:** 1080p on Lite and Starter, 4K on Creator and Pro; Lite has a 3-export limit; NLE export starts at Starter [PRICE].
- Observed — **speed:** rendered client-side with WebCodecs/WebGL2 [HN]; "an hour of footage in about five minutes" [HOME]; a straight-cut benchmark went from 35.4 s to 11.6 s [CL #38].
- Observed — **partial download:** right-click a clip to download just its trimmed range at original quality [CL #34].
- Observed — **share link:** project becomes a link; viewers need no login; "clean watch page"; link is available before publishing [CL #32].
- Observed — **comments:** pinned to the frame; commenter gives only name and email; each note jumps to its timecode; owner can resolve or delete, and edit the project straight from a comment [CL #32].
- Observed: the vendor blog claims "live co-editing" [B1][B2]; collaboration is also on the "hard problems" list [HP].
- Inferred (from that contradiction): real-time co-editing is partial or aspirational; share-link review with comments is the shipped part.
- **Not found:** direct publishing to YouTube/Instagram/TikTok; scheduling; the export dialog's options; batch export of several aspect ratios at once.

---

## 9. Motion and feel

I could not view any video or screenshot, so this section is limited to what the text says. It is thin, and should be treated as a gap to fill by watching the demo.

- Observed — **no dead waiting, by design:**
  - voiceover starts playing while still generating [CL #12];
  - music and effect previews preload on hover [CL #5, #10];
  - effects and colour looks preview live on hover, rendered on the user's own footage, and animation tiles play the user's own title [CL #5, #31, #41];
  - what is near the playhead loads first, "the rest of your library follows quietly behind it" [CL #42];
  - scrubbing: "frames arrive as fast as you move" [CL #42];
  - project name and thumbnails show before the project finishes loading [CL #22];
  - the user can queue prompts instead of waiting [CL #30].
- Observed — **calm over busy:** a long agent turn folds into one line; thinking is folded into the activity stream; the release is titled "A calmer chat" [CL #35, #41].
- Observed — **direct manipulation follows the hand:** preview follows keyframe drags in real time; canvas updates as you type; captions panel follows the playhead [CL #9, #33, #42].
- Observed: the sign-in page is described as a "cinematic split-screen with smooth transitions" [CL #14].
- **Not found:** how an AI edit animates onto the timeline (clips sliding, fading, highlighting); any working/thinking animation; durations, easing, or motion language; skeleton or shimmer states; sound; whether the playhead moves to the changed region; completion feedback.

---

## 10. Takeaways for Clipnera

### Ten things to adopt (the idea, in Clipnera's own form)

1. **Every prompt is a checkpoint.** One prompt equals one undo step, and the timeline can return to the state at any message [CL #14, #29, #39].
2. **Make undo impossible to miss.** Cardboard hid it at the bottom right of the message and a user could not find it [HN]. Clipnera should put it where the result is announced.
3. **Let people keep typing.** A visible, numbered, reorderable queue, and a stop button that is separate from send [CL #30, #35].
4. **Collapse the work, keep the outcome.** One calm status line while working, expandable for detail, then a short summary [CL #35, #40].
5. **Verify before reporting done.** The agent looks at rendered frames and listens to the mix, then states plainly what it could not do [CL #34, #39, #40, #41]. This is the strongest trust feature in the product.
6. **Ask with pickers, not paragraphs.** When a choice is needed (music, voice, layout), show the options in the chat and continue the original request after the pick [CL #13, #27, #40].
7. **Footage first, prompt second.** Do not open on an empty box; show the prompt once there is material to talk about [CL #38].
8. **Tell the user exactly what is not ready.** Per-file status (uploading / preparing / analysing / transcribing) in the conversation, and keep it running in the background [CL #26, #34].
9. **Preview on the user's own footage.** Looks, effects and caption styles shown on their clip, on hover, before committing [CL #31, #41].
10. **Check exports before handing them over,** and offer a no-login share link with frame-pinned comments [CL #32, #43].

Also worth noting: offering a cleanup strength (Light / Balanced / Tight) with a preview is a good pattern for any destructive AI edit [CL #21].

### Five things NOT to copy

1. **A full professional NLE.** Keyframes, blend modes, Premiere shortcut presets and ProRes are Cardboard's bet on editors and marketing teams. Clipnera's users want clips out of long videos; that surface would bury the prompt.
2. **A model picker and bring-your-own-agent.** It pushes an engineering decision onto the user. Clipnera has already decided models are set per plan.
3. **The "Director" persona and the Cursor-for-video framing.** Clipnera needs its own name, voice and look; the amber/neutral palette is already locked.
4. **Desktop-only, Chrome-only, local-file architecture.** No phone or tablet support and no Firefox [HOME][HN]. Clipnera's clips are destined for phones; review and approval should work on one.
5. **Multi-tier usage multipliers plus generative credits** ("2.5x usage, 400 credits") — hard to reason about, and the founders themselves reversed their launch stance against credits [HN][PRICE]. Clipnera's credit packs should stay simple.

---

## What could not be found (summary)

- Exact panel positions and proportions.
- Whether reply text streams; whether the plan needs approval; whether edits land one by one or together.
- Slash commands, @-mentions, context chips.
- Any visual marking of AI-made changes on the timeline; before/after compare.
- Notifications for finished jobs; whether a run survives closing the tab.
- Direct publishing to social platforms.
- All actual motion: animation of edits arriving, working indicators, timings.
- Demo video content (YouTube page and share page could not be read as text); founders' X/LinkedIn posts (not retrievable).
- Home-page and Mac-page FAQ answers (collapsed; only the questions were readable).

**Recommended follow-up:** someone should watch the launch demo (https://youtu.be/xLBxatFM7uk) and take the 3-day trial to fill sections 2 and 9 with frame-level observation.

---

## Sources

Vendor (primary)

- [HOME] Cardboard home page — https://www.cardboard.ai/ (usecardboard.com redirects here)
- [CL #n] Cardboard changelog, entry number n, Nov 2025 – Sep 2026 — https://www.cardboard.ai/changelog
- [MAC] Cardboard for Mac — https://www.cardboard.ai/desktop
- [PRICE] Pricing — https://www.cardboard.ai/pricing
- [HP] Hard problems — https://www.cardboard.ai/hard-problems
- [B1] Blog, "How to Make a Promo Video for Your Business" — https://www.cardboard.ai/blog/how-to-make-a-promo-video
- [B2] Blog, "6 Best AI Video Editors in September 2026" — https://www.cardboard.ai/blog/best-ai-video-editors
- Blog index — https://www.cardboard.ai/blog

Launch posts and founder statements

- [HN] Launch HN: Cardboard (YC W26), post and founder replies — https://news.ycombinator.com/item?id=47170174
- [YCL] Launch YC: Cardboard – Agentic Video Editor — https://www.ycombinator.com/launches/PM3-cardboard-agentic-video-editor
- [YC] YC company profile — https://www.ycombinator.com/companies/cardboard
- [PH] Product Hunt — https://www.producthunt.com/products/cardboard-3
- Fondo launch write-up — https://fondo.com/blog/cardboard-launches

Third-party (none shows first-hand use)

- [R1] OutlierKit review — https://outlierkit.com/resources/cardboard-review/
- [R2] ToolWorthy review — https://www.toolworthy.ai/tool/usecardboard
- [R3] runany.dev — https://runany.dev/blog/cardboard-video-editor/
- [R4] everydev.ai listing — https://www.everydev.ai/tools/cardboard
- [R5] StartupHub "Claude's Corner" — https://www.startuphub.ai/ai-news/claude's-corner/2026/claudes-corner-cardboard-yc-w2026
- chatgate.ai — https://chatgate.ai/post/cardboard

Found by search but not read, or unreadable

- Launch demo video — https://youtu.be/xLBxatFM7uk (page returned no content)
- Demo share page — https://www.usecardboard.com/share/fUN2i9ft8B46 (not fetched)
- Demo site — https://demo.usecardboard.com (now redirects to the home page)
- YC post on X — https://x.com/ycombinator/status/2018799155871903814 (not fetched)
- Extruct funding page — https://www.extruct.ai/hub/usecardboard-com/ (not fetched)
- Hacker News item 42100391 — a different product (Frame AI), excluded
