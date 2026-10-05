# Perplexity — reference study

Prepared for the Clipnera UI revamp (Wave 6), 4 October 2026. Subject: Perplexity (perplexity.ai) and its surfaces: home, sessions (formerly threads), Library, Projects (formerly Spaces), Discover, Pages, Research, Labs/Computer and the Comet browser. Studied as the reference for answer-engine calm: one prompt that does everything, visible work, sources, follow-ups.

## How to read this

- **Evidenced** means a public source states it; the URL is given. **Inferred** means I reasoned it from something evidenced, or from prior familiarity with the product that I could not re-verify today; I say which.
- I could not sign in or use the product. Nothing here is first-hand use.
- `perplexity.ai` (help centre, changelog, blog) returned HTTP 403 to my fetcher. Perplexity's own pages are therefore cited from search-engine excerpts of those pages, not from full reads. Treat their UI strings as very likely correct, but check on screen before copying wording.
- Third-party "design system" extractions (designmd, oh-my-design, shadcn.io) are reverse-engineered by people outside Perplexity. Their numbers (font sizes, radii, widths) are plausible but unofficial. I flag them as **evidenced (third party, unofficial)**.
- Perplexity renames things often. In 2026: Spaces became **Projects** (30 July 2026), threads became **sessions** (help page title changed; last modified 29 September 2026), Deep Research became **Research**, and Labs, scheduled tasks and Research were folded into **Computer**. Older third-party sources use the old names. I use the current name and give the old one in brackets.
- I saw no video. Motion and timings are not covered; any timing Clipnera uses is its own decision.
- Colours are noted only to say what **not** to take. Clipnera stays amber on neutral.

## 1. The home prompt box

**Placement and size**

- Evidenced: on mobile, "a single search bar that dominates the home screen", with optional focus modes. ([Perplexity mobile guide, perplexityaimagazine](https://perplexityaimagazine.com/perplexity-hub/how-to-use-perplexity-ai-2/), search excerpt)
- Evidenced: the web layout is three parts: a top-left navigation (Home, Discover, Spaces, Library, New Thread), a central workspace holding the "Search input box for queries, File attachment capabilities, Focus mode toggle, Pro search status indicator", and account controls bottom-left. ([Learn Prompting guide](https://learnprompting.org/blog/guide-perplexity))
- Evidenced (third party, unofficial): primary inputs are 44 px tall, ghost inputs 36 px; the composer has a 16 px radius, larger than buttons (10 px) and cards (12 px). ([oh-my-design](https://oh-my-design.kr/design-systems/perplexity))
- Inferred (prior familiarity): the home input sits at the optical centre of an otherwise empty page, under a wordmark; it is a multi-line textarea that grows with content, not a one-line search field.

**Attach, mode and model controls**

- Evidenced: an "Attach" button adds files as reference material. ([Learn Prompting](https://learnprompting.org/blog/guide-perplexity))
- Evidenced: Pro users pick a mode — Search, Research, Labs — from a mode selector "in the input bar" on web, iOS and Android. ([What is Research mode?](https://www.perplexity.ai/help-center/en/articles/10738684-what-is-research-mode), [Introducing Labs](https://www.perplexity.ai/hub/blog/introducing-perplexity-labs), search excerpts)
- Evidenced: the model selector lives "in the bottom right corner of the prompt input box" with reasoning and speed options. (search-engine summary of 2026 how-to guides; the exact page was not identified, so treat as weak evidence)
- Evidenced (older): focus modes Web, Academic, Social, Video, Writing, Math narrow sources; Writing and Math disable follow-up suggestions. ([Learn Prompting](https://learnprompting.org/blog/guide-perplexity), [wisechecker](https://wisechecker.com/disable-auto-suggested-follow-up-questions-perplexity/))
- Evidenced: a tooltip on the mode toggle shows **usage remaining and a keyboard shortcut**. ([Nicely Done component catalogue](https://nicelydone.club/apps/perplexity/components): "Copilot mode toggle accompanied by a tooltip showing usage limits and a keyboard shortcut")
- Evidenced: voice — hold the microphone in the search bar; a spoken query is handled "identically to a typed query". ([Perplexity mobile guide](https://perplexityaimagazine.com/perplexity-hub/how-to-use-perplexity-ai-2/), search excerpt)
- Inferred: controls are grouped inside the box's bottom edge (left: mode/attach; right: model, mic, send), so the box reads as one object. This matches the "bottom right corner" placement above.

**Suggestions and empty state**

- Evidenced: the home page gained widgets (top Discover stories, weather, stocks) below the input, acting "as shortcuts to related pages"; watchlist topics become widgets. ([TestingCatalog on X](https://x.com/testingcatalog/status/1874875485471338713), [Kol Tregaskes on X](https://x.com/koltregaskes/status/1874707949718790591))
- Evidenced: Projects (Spaces) offer ~50 templates, e.g. "Brainstorm Buddy", each a preset of instructions. ([XDA](https://www.xda-developers.com/perplexity-habits-i-should-have-started-doing-sooner/))
- Evidenced: Comet's new tab is "a clean prompt bar, recent tabs, and the ability to initiate agentic tasks"; prompts can start from home, sidebar or URL bar. ([TestingCatalog Comet review](https://www.testingcatalog.com/exclusive-comrehansive-review-comet/))
- Inferred: the empty state is the page. There is no onboarding wall, no dashboard grid above the fold; content (widgets, recents) sits below and never competes with the input.

**What to note for Clipnera:** one box, controls inside its frame, mode as a compact pill not a tab bar, usage shown where the choice is made, and the area below the box used for *shortcuts back into work*, not marketing.

## 2. How answers stream

**Steps while it works**

- Evidenced: Pro Search shows "the plan being executed step-by-step"; users can "click on individual steps to see more details". Rationale: "users were more willing to wait for results if the product would display the intermediate progress." ([LangChain Breakout Agents: Perplexity](https://www.langchain.com/breakoutagents/perplexity))
- Evidenced: the principle behind it: "You don't want to overload the user with too much information until they are actually curious. Then, you feed their curiosity." ([LangChain](https://www.langchain.com/breakoutagents/perplexity))
- Evidenced: above the answer, a collapsible "Completed 2 steps" with "plain-language step names (Searching the web)". ([AI UX Playground teardown](https://aiuxplayground.com/teardowns/perplexity/output/))
- Evidenced: Research shows "which sources are being read, what's being learned, and how the report is coming together"; **key findings appear as research progresses**, before the final report. ([What's New in Advanced Deep Research](https://www.perplexity.ai/help-center/en/articles/13600190-what-s-new-in-advanced-deep-research), search excerpt)
- Evidenced: Research **asks clarifying questions before starting** on broad queries, and users **can add follow-ups while it is still running**. (same source)
- Evidenced: Research takes most tasks under 3 minutes; Labs runs "10 minutes or more of self-supervised work". ([What is Research mode?](https://www.perplexity.ai/help-center/en/articles/10738684-what-is-research-mode), [Introducing Labs](https://www.perplexity.ai/hub/blog/introducing-perplexity-labs))
- Evidenced: Computer runs long tasks asynchronously in the background, and sessions can be started and continued from email. ([Semafor](https://www.semafor.com/article/02/25/2026/perplexity-launches-computer-super-agent), [Releasebot](https://releasebot.io/updates/perplexity-ai))
- Evidenced: Comet's agent "disables manual interaction on the page, overlays an animation, and walks through the actions step-by-step… You can pause or cancel at any time". ([TestingCatalog Comet review](https://www.testingcatalog.com/exclusive-comrehansive-review-comet/))

**Sources**

- Evidenced: numbered citations sit inline; hovering shows a snippet; clicking opens the source in a new window. ([LangChain](https://www.langchain.com/breakoutagents/perplexity))
- Evidenced: the brand asterisk itself stands for "citing sources for each sentence". ([Ebaq Design on the Smith & Diction rebrand](https://www.ebaqdesign.com/news/perplexity-rebrand))
- Evidenced: highlighting text in an answer offers two paths: "Add to follow-up" and "Check sources", "splitting iterate from verify". ([AI UX Playground](https://aiuxplayground.com/teardowns/perplexity/output/))
- Evidenced: result views — Links, Images, Videos, Shopping, Places — are tabs "from the top of each thread", so users pivot without re-asking. ([Dec 5 changelog, search excerpt](https://www.perplexity.ai/changelog/what-we-shipped---december-5th); [AI UX Playground](https://aiuxplayground.com/teardowns/perplexity/output/))
- Evidenced (third party, unofficial): on small screens, sources move from a right rail into a horizontal scroll strip above the answer. ([oh-my-design](https://oh-my-design.kr/design-systems/perplexity))
- Inferred (prior familiarity): a row of 3–4 compact source cards (favicon, domain, title) precedes the prose, with a "+N" card that opens the full list.

**The answer itself**

- Evidenced: the answer is "a small report, not a chat bubble": headings, bullets, inline source chips. ([AI UX Playground](https://aiuxplayground.com/teardowns/perplexity/output/))
- Evidenced: Labs puts every generated file in an **Assets** tab under the query, for viewing and download. ([Introducing Labs](https://www.perplexity.ai/hub/blog/introducing-perplexity-labs), search excerpt)
- Evidenced: per-answer actions: share, export (PDF, Markdown, DOCX), rewrite (with a different mode/model, the current one checkmarked "so users know what produced this answer"), copy, bookmark, add to project. ([AI UX Playground](https://aiuxplayground.com/teardowns/perplexity/output/), [XDA](https://www.xda-developers.com/perplexity-habits-i-should-have-started-doing-sooner/))
- Evidenced: feedback chips are domain-specific: "Good sources" as praise, "Wrong sources" as a first-class complaint. ([AI UX Playground](https://aiuxplayground.com/teardowns/perplexity/output/))

**Follow-ups and related**

- Evidenced: 3–5 suggested follow-ups appear below the answer, generated from the answer itself. ([TrustRadius](https://solutions.trustradius.com/buyer-blog/how-does-perplexity-ai-work/), search excerpt)
- Evidenced: they are contextual ("squad leaders, France form, betting odds"), not generic; "each chip is one tap into the composer". ([AI UX Playground](https://aiuxplayground.com/teardowns/perplexity/output/))
- Evidenced: related questions render as an accordion list. ([Nicely Done](https://nicelydone.club/apps/perplexity/components))
- Inferred (prior familiarity): a follow-up composer is pinned to the bottom of the session ("Ask a follow-up"), so the next prompt is always one keystroke away, and the page scrolls to the newest answer.

## 3. Sessions, Library and Projects

**Sessions (threads)**

- Evidenced: "a conversation that keeps context across follow-up questions, saves sources, and builds on earlier answers." ([What is a Session?](https://www.perplexity.ai/help-center/en/articles/10354769-what-is-a-thread), search excerpt)
- Evidenced: rename from the session's ⋯ menu, by clicking the title in the session, or from the ⋯ beside each recent item in the sidebar. ([llmnesia](https://www.llmnesia.com/blog/how-to-organize-perplexity-conversation-history), [Guideflow](https://www.guideflow.com/tutorial/how-to-rename-your-thread-in-perplexity))
- Evidenced: delete is per session (hover → ⋯ → Delete) or "Delete all" in Settings; there is no trash or recovery. ([llmnesia](https://www.llmnesia.com/blog/how-to-organize-perplexity-conversation-history), [perplexityaimagazine](https://perplexityaimagazine.com/perplexity-hub/how-to-delete-perplexity-ai-history-privacy-guide/))
- Evidenced: sharing is Private (author only) or anyone-with-the-link. ([Guideflow share tutorial](https://www.guideflow.com/tutorial/how-to-share-a-thread-in-perplexity), search excerpt)
- Evidenced: lifetimes are explicit and labelled: logged-out sessions expire after 14 days, incognito after 24 hours; sessions with attached files or connectors are marked **"Temporary"** in history. ([Where did my sessions go?](https://www.perplexity.ai/help-center/en/articles/12637451-where-did-my-threads-go), search excerpt)
- Inferred: a session is titled automatically from the first prompt; renaming is an override, not a step.

**Library**

- Evidenced: Library moved to the top of the sidebar; click opens it, **hover reveals bookmarks and an expanded list of recents**. ([Dec 5 changelog](https://www.perplexity.ai/changelog/what-we-shipped---december-5th), search excerpt)
- Evidenced: a later redesign gives "fast access to your library and spaces on hover", and lets users **pin** their favourite view among Threads, Discover and Spaces. ([May 2 changelog: redesigned sidebar](https://www.perplexity.ai/changelog/what-we-shipped-may-2nd), search excerpt)
- Inferred: Library is a single searchable list ordered by recency; it is a place to *return* to work, not to manage it.

**Projects (Spaces)**

- Evidenced: "Think of threads as files, and Spaces as folders that hold those files"; each has custom instructions (its own system prompt) and can prioritise given links. ([XDA](https://www.xda-developers.com/perplexity-habits-i-should-have-started-doing-sooner/))
- Evidenced: limits: title 50 characters, description 1,000, instructions 8,000; up to 50 files on Pro. Created with "+ New project" in the left panel, **or by converting an existing session**, in which case Perplexity suggests "a title, a description and a set of instructions based on what you were doing". ([Fello AI](https://felloai.com/perplexity-spaces/))
- Evidenced: Projects are invite-only by default, max 5 contributors on standard plans; a memory layer ("Brain") builds project context over time. ([Fello AI](https://felloai.com/perplexity-spaces/))
- Evidenced: files are added from local disk, connectors or links via Files → add. ([Business Library FAQ](https://answers.businesslibrary.uflib.ufl.edu/genai/faq/427782), search excerpt)

**Discover and Pages**

- Evidenced: Discover is a curated feed of trending topics, personalised by chosen interests; creators can now contribute as curators. ([Perplexity curators](https://www.perplexity.ai/curators), [Apr 18 changelog](https://www.perplexity.ai/changelog/what-we-shipped-april-18th))
- Evidenced (third party, unofficial): Discover is a responsive 1–3 column masonry. ([oh-my-design](https://oh-my-design.kr/design-systems/perplexity))
- Evidenced: Pages turned a session into an editable article (edit text, add sections and headers, add images or YouTube), then **Publish** gives a link; unpublish/delete hides behind an ellipsis next to "Edit Page", and published Pages were publicly searchable. ([How-To Geek](https://www.howtogeek.com/perplexity-ais-pages-lets-you-polish-and-publish-your-queries-but-who-is-it-for/))
- Evidenced: "Create page" is temporarily retired in 2026; publishing moved to Computer websites on `pplx.app` or a custom domain. ([Perplexity Pages help](https://www.perplexity.ai/help-center/en/articles/10352968-perplexity-pages), [Publishing your website](https://www.perplexity.ai/help-center/en/articles/20260711-publishing-your-website-to-the-web), search excerpts)

## 4. Sidebar, navigation, type and density

**Sidebar**

- Evidenced: the sidebar is logo, "New Thread" button, main links, Library section, an upgrade section, and user settings at the bottom. ([Nicely Done](https://nicelydone.club/apps/perplexity/components))
- Evidenced (third party, unofficial): the left rail collapses to icons, then to a hamburger drawer on mobile; the shell is "collapsible left rail, centered column, optional right rail". ([oh-my-design](https://oh-my-design.kr/design-systems/perplexity))
- Evidenced: Comet's assistant is a collapsible side panel that leaves most of the screen to the page and offers page-specific suggestions. ([XDA on Comet](https://www.xda-developers.com/comet-browser-features-switch-chrome/), [TestingCatalog](https://www.testingcatalog.com/exclusive-comrehansive-review-comet/))
- Inferred: five or fewer top-level destinations; everything else is either inside the box (modes) or behind the avatar (settings).

**Typography and measure**

- Evidenced: brand by Smith & Diction; wordmark in FK Display, UI in FK Grotesk; brief was a "Scandinavian subway system. Clean and considered but in an invisible sort of way." ([Ebaq Design](https://www.ebaqdesign.com/news/perplexity-rebrand), [Smith & Diction on Medium](https://medium.com/smith-diction/branding-perplexity-ai-70eb2cb2ef48), search excerpt)
- Evidenced (third party, unofficial): answer body 16 px at ~1.63 line height; three weights only (400 body, 500 labels, 600 headings); slight negative tracking on headings; answer column ≈68 characters / ~768 px max, "like magazine columns rather than dense UI"; display face has a serif (Georgia) fallback. ([oh-my-design](https://oh-my-design.kr/design-systems/perplexity))
- Note on the brief's "serif/sans mix": I found no evidence that the product UI uses a serif for answers. The serif impression comes from marketing and display type. **Inferred:** the reading feel comes from the measure and leading, not from a serif.

**Spacing, density, dark mode**

- Evidenced (third party, unofficial): 4 px base; 24–32 px between answer blocks; separation mostly by borders, not shadows ("paper-flat"). ([oh-my-design](https://oh-my-design.kr/design-systems/perplexity))
- Evidenced: Light, Dark or System theme in settings. ([Account & Settings help](https://www.perplexity.ai/help-center/en/articles/10352990-account-settings), search excerpt)
- Evidenced: the design stance is "get out of the way of the answer… a place to read rather than a console to operate". ([designmd.co summary](https://www.designmd.co/d/perplexity), search excerpt)
- Not taken: their teal accent and cream canvas. Clipnera keeps amber on neutral near-black.

## 5. Mobile

- Evidenced: mobile mirrors web and adds voice input, share-sheet integration and Discover. ([datastudios](https://www.datastudios.org/post/perplexity-mobile-app-vs-desktop-interface-features-integrations-and-usability), search excerpt)
- Evidenced: the September iOS redesign brought "faster query input, gesture navigation, smooth transitions". ([Sep 5 changelog](https://www.perplexity.ai/changelog/what-we-shipped-september-5th), search excerpt)
- Evidenced (third party, unofficial): 44 px primary touch targets; sources become a horizontal strip above the answer. ([oh-my-design](https://oh-my-design.kr/design-systems/perplexity))
- Inferred (prior familiarity): the composer is pinned to the bottom within thumb reach; history opens as a drawer; one column, no side rails.

## 6. Errors, limits and upgrade prompts

- Evidenced: error copy is generic — "Something went wrong. Please try again", "Internal error", "Unable to complete request" — or a blank answer pane / endless spinner; users complain they can't tell causes apart. ([perplexityaimagazine](https://perplexityaimagazine.com/perplexity-hub/how-to-fix-perplexity-error-message/), [gptprompts](https://gptprompts.ai/ai-errors-and-fixes/perplexity-error))
- Evidenced: follow-ups can fail while the first answer worked. ([perplexityaimagazine](https://perplexityaimagazine.com/perplexity-hub/how-to-fix-perplexity-error-message/))
- Evidenced: when the Pro allowance runs out, queries **downgrade to standard search** rather than stop; premium choices show "Limit reached" / "Upgrade required" in the selector while quick search keeps working. ([fast.io](https://fast.io/resources/perplexity-message-limit/), [aifixhub](https://www.aifixhub123.com/issues/perplexity-pro-limits))
- Evidenced: typical prompts: "Upgrade to Pro to continue using Pro Search", "You've reached your daily limit for Deep Research". (same sources)
- Evidenced: a silent downgrade is also reported as a failure mode — "a feature silently refuses to run" or "downgrades to a simpler mode". ([perplexityaimagazine](https://perplexityaimagazine.com/perplexity-hub/how-to-fix-perplexity-error-message/))
- Evidenced: a persistent upgrade block sits in the sidebar. ([Nicely Done](https://nicelydone.club/apps/perplexity/components))
- Evidenced: Comet: "if a task fails, you see why, and can adjust your prompt"; calendar actions appear as approve/reject widgets with a "request clarification" path. ([TestingCatalog](https://www.testingcatalog.com/exclusive-comrehansive-review-comet/))
- Evidenced: Projects bill memory to the creator — a cost rule users must discover. ([Fello AI](https://felloai.com/perplexity-spaces/))

**Lesson:** the *degrade-don't-block* behaviour is good; the *silent* degrade and the generic copy are not. Clipnera's principles 10 and 11 already require visible cost and one next action per error.

## 7. What not to copy

1. **The model picker and rewrite-with-model.** Clipnera principle 12 says no model names. Keep the *idea* (try again a different way) as "Try another take".
2. **Silent downgrades.** Always say when a cheaper path was used.
3. **Generic errors.** Every Clipnera error names the cause and one action.
4. **Delete with no recovery.** Clipnera projects hold expensive renders; keep a short undo/trash.
5. **Public-by-default publishing** (old Pages). Share links stay private until the user flips them.
6. **Constant renaming** (Spaces→Projects, threads→sessions). Pick nouns once.
7. **Teal/cream palette and the asterisk mark.** Layout and behaviour only.
8. **Discover as a news feed.** Clipnera has no reason to show trending content; use the slot for the user's own work.

## What Clipnera should take

1. **Home — one centred composer as the whole above-the-fold.** Multi-line, grows to ~6 lines, 16 px radius token, controls inside its bottom edge: attach/link on the left, mic and send on the right. Nothing above it but a one-line greeting. (§1)
2. **Home — a compact intent pill inside the box, not a model picker.** e.g. "Clips · Reel · Edit" as a single pill menu; default chosen from what was attached. Show remaining credits for the chosen intent in its tooltip, as Perplexity does with usage. (§1)
3. **Home — below the composer, shortcuts back into work:** "Continue" cards for the last 3 projects and 3–4 contextual suggestion chips that fill the box (never auto-submit). No marketing, no feed. (§1, §7.8)
4. **Home — clarify before spending.** For vague prompts on long footage, ask one choice-based clarifying question before a credit-spending run (Research does this). (§2)
5. **Editor conversation — a collapsible step list above each result.** Running: one live line ("Reading transcript… 14 of 52 min"). Done: collapses to "Completed 4 steps"; each step expands for detail. Plain-language step names only. (§2)
6. **Editor conversation — stream partial findings.** Show candidate moments/hooks as they are found (like Research's key findings) so the user can start reviewing before the full cut is ready. (§2)
7. **Editor conversation — accept prompts while a run is going.** A follow-up typed mid-run queues or steers the run; never disable the composer. (§2)
8. **Editor conversation — "sources" become timestamps.** Every claim or cut in a reply carries an inline numbered chip that points at a transcript span; hover previews the line and thumbnail, click seeks the player. This is Clipnera's citation. (§2)
9. **Editor conversation — a source strip above the reply.** A horizontal row of 3–4 clip/segment cards (thumbnail, timecode, score) plus "+N", before the prose. On mobile it stays a scroll strip. (§2, §5)
10. **Editor conversation — replies are small reports, not bubbles.** Short heading, bullets, chips; the AI's text sits on the page canvas, the user's prompt is the visual heading of each turn. (§2)
11. **Editor conversation — select-to-act.** Selecting transcript or reply text offers "Add to prompt" and "Show in video" — iterate versus verify, as Perplexity splits them. (§2)
12. **Editor conversation — 3–4 contextual follow-up chips under each result,** generated from that result ("Tighten the hook", "Make a 9:16 version", "Add captions in Hindi"); one tap fills the composer. (§2)
13. **Editor conversation — an Outputs tab per turn.** Rendered clips, captions files and thumbnails from a run gather in one place under the turn (Labs' Assets), each downloadable. (§2)
14. **Editor conversation — pinned bottom composer** with the current selection as a chip; `⌘K`/`/` focus it. On mobile it is thumb-reachable at the bottom. (§2, §5)
15. **Project — a project is the container, a conversation is the file.** Each project has its footage, brand kit, standing instructions ("always 9:16, bold captions, no swearing") and many conversations. (§3)
16. **Project — "Make this a project" from any loose conversation,** with AI-suggested name, description and instructions the user can edit. (§3)
17. **Library — one recency list, auto-titled, inline rename and ⋯ menu,** searchable, with a filter for project; hover on the sidebar's Library item reveals the five most recent. (§3)
18. **Library — explicit lifetimes and temporary labels.** Show "Expires in N days" on unsaved/guest work and on renders that will be purged; never let work vanish silently. (§3)
19. **Library — soft delete.** Delete moves to a 30-day trash with restore; "Delete all" lives in Settings, not here. (§3, §7.4)
20. **Settings — theme Light / Dark / System, and a privacy/data-use toggle** placed under the avatar menu, as Perplexity does; no settings in the main nav. (§4)
21. **Global — sidebar with at most five items:** New, Library, Projects, Brand, and the avatar at the bottom; collapses to icons at tablet, a drawer at 360 px. Let users pin their preferred landing view. (§4)
22. **Global — reading measure for AI text.** Conversation column max ~68 characters (≈ 720–768 px), 16 px body at ~1.6 leading, three weights, 24–32 px between turns, borders not shadows. The video preview gets the remaining width. (§4)
23. **Global — degrade, don't block, and say so.** When credits run low, offer the cheaper path ("Run as a draft at 720p — 2 credits") inline in the conversation with the exact cost, plus an Upgrade link; never silently downgrade. (§6)
24. **Global — errors name the cause and one action,** inline in the turn that failed, with "Retry" that keeps the prompt and attachments. A failed follow-up never destroys earlier results. (§6)
25. **Landing — the composer is the hero.** Signed-out visitors can paste a link and type a prompt; sign-in is asked on send and the prompt survives it (matches Lovable). Below: three real before/after examples, not a feature grid. (§1)

## What could not be found

- Exact home-page composer dimensions, placeholder text and suggestion chips in the 2026 web UI (Perplexity pages were blocked; no screenshots read).
- Streaming cadence: how fast tokens arrive, whether source cards animate in, how steps transition from running to done.
- Whether the follow-up composer is sticky on web (believed so from prior familiarity; not re-verified).
- The current sidebar contents after the Projects and Computer changes (2026); only the 2025 redesigns are evidenced.
- Any serif use inside the product UI.
- Exact wording and placement of the limit/upgrade banner inside a session, beyond the strings quoted in §6.
- Before Wave 6 visual sign-off, someone with an account should capture: home (signed out and in), a running Research session, a finished answer, Library, a Project, and the limit state, at desktop and 360 px.

## Sources

All URLs are cited inline. Perplexity-owned pages (`perplexity.ai/help-center`, `/changelog`, `/hub`) were read through search excerpts only because direct fetches returned HTTP 403.
