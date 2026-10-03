# Lovable reference study

Prepared for the Clipnera UI revamp, 3 October 2026. Subject: Lovable (lovable.dev), studied as the reference for how prompting should feel.

## How to read this

- **Observed** means the claim is stated in a public source, which is linked. **Inferred** means I reasoned it from something observed, and I say from what. **Not found** means I looked and found nothing; I have not filled the gap.
- I could not sign in or use the product. Nothing here comes from first-hand use.
- `lovable.dev/` itself returned HTTP 403 to my fetcher, and the Wayback Machine was unreachable. So the signed-out home page is covered only through Lovable's own docs and third-party write-ups. This is the weakest section.
- Pages were read through a fetch tool that summarises. Text in quotation marks is what that tool returned as a quotation; treat UI strings as very likely correct but confirm them on screen before copying any wording.
- I saw no video or screen recording. Section 9 (motion) is therefore thin, and I have marked it so rather than describe motion I did not see.
- Lovable's docs are current to September 2026. Third-party reviews are older and describe earlier versions of the UI; where they disagree with the docs, the docs win, and I flag it.

## 1. Home page prompt hero

**The input**

- Observed: a prompt box sits at the centre of the dashboard. "Type a description of what you want to build and click send to create a new project." ([Dashboard overview](https://docs.lovable.dev/introduction/dashboard-overview))
- Observed: the box is labelled "Ask Lovable to create…" with Build mode selected by default. ([Quick start](https://docs.lovable.dev/introduction/getting-started))
- Observed (third party): reviewers quote the placeholder as "Ask Lovable to create a landing page for my…". (search result excerpts for [Quick start](https://docs.lovable.dev/introduction/getting-started) and the [HubSpot guide](https://offers.hubspot.com/view/lovable-marketers-guide))
- Observed (third party, older): one guide gives the label as "What do you want to build?". This is probably an earlier version. ([Sidetool](https://www.sidetool.co/post/getting-started-with-lovable-ai-build-full-stack-web-apps-with-just-prompts))
- Observed (third party): "The home pages was clean and simple. It just asked for a simple prompt to get started." ([EntreResource](https://entreresource.com/loveable-ai/))

**Placeholder behaviour**

- Inferred: the placeholder animates, typing out and cycling through example endings. Basis: the placeholder ends in an open "for my…", and a Bubble forum thread titled "Animated input placeholder like Lovable?" exists in which users rebuild the effect. The thread's original post only shows screenshots; it does not describe Lovable's behaviour in words. ([Bubble forum](https://forum.bubble.io/t/animated-input-placeholder-like-lovable-solved/380562))
- Not found: Lovable's actual phrases, typing speed, or pause timing. The 60 ms per character figure in that thread is a community member's own rebuild, not a measurement of Lovable.

**Controls in and around the input**

- Observed: a microphone button for dictation. ([Dashboard overview](https://docs.lovable.dev/introduction/dashboard-overview))
- Observed: a mode picker with three options. Build (default): "Create a new project and have Lovable build it". Chat: start a chat outside projects. Plan: create a project and start in Plan mode so Lovable "investigates and writes a plan without changing code". ([Dashboard overview](https://docs.lovable.dev/introduction/dashboard-overview))
- Observed: a `+` button to the left opens Attach (images, files, screenshots), Design (templates or design systems), Connectors, and Databases. ([Dashboard overview](https://docs.lovable.dev/introduction/dashboard-overview))
- Observed: a template is picked by `+` → Design → Use a template; "The selected template is applied as the project foundation. Your prompt still controls what gets generated." ([Design templates](https://docs.lovable.dev/features/business/design-templates))

**Suggestion chips on the home page**

- Not found. I found no source describing chips beneath the home prompt box. (Chips do exist inside a project; see section 4.)

**What is below the input**

- Observed: the signed-in dashboard has a sidebar with Projects, Starred, Recents, folders, search and connectors. ([Dashboard overview](https://docs.lovable.dev/introduction/dashboard-overview), [Editor](https://docs.lovable.dev/features/projects/editor))
- Observed: the dashboard has a templates tab. ([Remix](https://docs.lovable.dev/features/projects/remix))
- Observed (third party, undated): "community projects filled the page below, everything from dashboards to SaaS templates". (search result excerpt, source review not retrievable)
- Observed: the public templates gallery at `/templates` shows 207 results, filters for All / Websites / Apps, subcategories and personas, and cards with thumbnail, title, one-line description and category. ([Templates](https://lovable.dev/templates))
- Not found: the current layout of the area below the hero on the signed-out home page. The docs do not describe a community or discover section on the dashboard.

**Submit: signed out versus signed in**

- Observed: signed out, the prompt is kept. Users can "type your prompt on the homepage first, and Lovable asks you to sign up when you submit, keeping your prompt through sign-up." ([Quick start](https://docs.lovable.dev/introduction/getting-started))
- Observed: the same holds for prefilled links (`lovable.dev/#prompt=…&images=…&html=…`). The prompt prefills immediately, login is requested on send, and "Lovable preserves the prompt and references, and the build starts only when they click send". The old `autosubmit=true` parameter is now ignored. ([Build with URL](https://docs.lovable.dev/integrations/build-with-url))
- Observed: sign-up options are email, Google, GitHub or Apple. ([Quick start](https://docs.lovable.dev/introduction/getting-started))
- Observed: signed in, submitting creates a project and opens the editor. "The first version takes a few minutes, and you can watch it take shape as Lovable works." ([Quick start](https://docs.lovable.dev/introduction/getting-started))
- Observed (third party, older): "Within seconds, you'll see the interface switch to the project editor view". ([Sidetool](https://www.sidetool.co/post/getting-started-with-lovable-ai-build-full-stack-web-apps-with-just-prompts))
- Not found: the visual transition from home page to editor.

## 2. Workspace layout

All Observed from [Find your way around the Lovable editor](https://docs.lovable.dev/features/projects/editor) unless stated.

**Two panels**

- Chat panel on the left: "Where you tell Lovable what to build and follow its progress".
- Preview on the right: "A live, interactive version of your app that updates as Lovable works."
- Everything else lives in the top bar.

**Top bar, left to right**

- Menu icon opening the sidebar (hover to peek, click to pin, `[` to toggle). The sidebar holds the workspace switcher with credit balance, dashboard link, chats, search, connectors, projects, starred, recents and the user menu.
- Project name, which shows whether you are on the main version or a draft. Clicking it opens the draft switcher.
- History toggle (version history and bookmarks).
- Hide chat panel / Show chat panel (`Cmd/Ctrl+B`), which gives a full-window preview.
- Toolbar tabs: Preview, Files, Code, More. More holds Analytics, Cloud, AI, Payments, Connectors, Security, SEO, Settings and others.
- Top right: preview toolbar button, comments, collaborator avatars with invite, Share, Publish.

**Mode switches**

- Observed: the mode picker sits in the chat input and offers Build, Chat and Plan; `Option/Alt+P` cycles them. ([Project chat](https://docs.lovable.dev/features/projects/chat))
- Observed: Build changes code and is usage-priced. Chat "discuss[es] your project without changing its code" and draws on a daily allowance. Plan investigates and writes a plan, and "never modifies your code". ([Chat mode](https://docs.lovable.dev/features/chat-mode), [Plan mode](https://docs.lovable.dev/features/plan-mode))
- Observed: Chat hands over to Build through a "Start building" card with a Build button marked "Uses credits". ([Chat mode](https://docs.lovable.dev/features/chat-mode))
- Observed: a plan opens in a dedicated Plan view as a structured document. Users can edit it directly, or select any passage and use a Comment button to request a change to just that part. Approving switches to Build and "Implementation begins immediately from the approved plan." ([Plan mode](https://docs.lovable.dev/features/plan-mode))
- Observed: the Code tab shows a file tree and tabbed files. It is read-only on the Free plan and editable on paid plans; each manual save becomes a version. ([Code mode](https://docs.lovable.dev/features/code-mode))
- Observed: visual editing is now a preview toolbar with modes: Select elements, Edit text inline, Draw annotation, and comments. It "replaces the prior Visual edits experience". ([Preview toolbar](https://docs.lovable.dev/features/preview-toolbar))
- Note: older reviews describe a "Visual Edits" toggle that opens a property panel for colour, type and spacing ([Mantlr](https://mantlr.com/blog/how-to-use-lovable-2026)). The current docs describe the toolbar instead. Whether a property panel still exists: Not found.

**Preview controls**

- Observed: device toggle (Desktop, Tablet, Mobile), a page selector with a "Find page or enter path" field, Refresh (Shift+click also restarts the environment), and open in new tab. ([Preview](https://docs.lovable.dev/features/projects/preview))

**Resizing**

- Observed: the chat panel can be hidden and shown. On small windows controls collapse into overflow menus; the mobile app swaps the split for swipeable chat and preview views. ([Editor](https://docs.lovable.dev/features/projects/editor), [Mobile app](https://docs.lovable.dev/integrations/lovable-mobile-app))
- Not found: a draggable divider between chat and preview, or minimum and default widths.

## 3. Prompt to result, moment by moment

1. **Send.** Enter or the send button. ([Project chat](https://docs.lovable.dev/features/projects/chat))
2. **Acknowledgement.** Not found. No source describes the first thing shown after sending (indicator, status word, timing).
3. **Narrated progress.** Observed: "While it works, you can see progress through visible tasks". Tasks show the "Current step being executed", "Files being modified", "Tools being used (search, web fetch, image generation)" and "Progress through multi-step implementations". ([Build mode](https://docs.lovable.dev/features/agent-mode)) Observed (third party): "The progress shows in real-time — Agent Mode narrates what it's doing." ([Mantlr](https://mantlr.com/blog/how-to-use-lovable-2026))
4. **Activity cards.** Observed: cards "track its individual actions: file edits, commands, web searches, browser tests, and the subagents it delegates research to". Clicking a card while work is running, or Details on a finished change, opens a Details view with two tabs: Timeline ("every step Lovable took, including tool calls") and Changes (the resulting file changes). ([Project chat](https://docs.lovable.dev/features/projects/chat), [Build mode](https://docs.lovable.dev/features/agent-mode))
5. **Questions.** Observed: when it needs direction, Lovable shows question cards with "up to four questions, each with answer options". Users can skip one or all; skipped questions get reasonable defaults and skipping does not approve extra suggested work. ([Project chat](https://docs.lovable.dev/features/projects/chat))
6. **Preview refresh.** Observed: the preview "updates as Lovable builds, so you can watch changes appear". Since 28 August 2026, "The preview now keeps what you have on screen in place while Lovable works, instead of reloading after each change." With Live preview turned off in settings, the preview "updates when Lovable finishes a change rather than while it works". ([Preview](https://docs.lovable.dev/features/projects/preview), [Changelog](https://docs.lovable.dev/changelog))
7. **What stays interactive.** Observed: the chat input stays usable (follow-ups, below). Inferred: the preview stays clickable during a build, from "updates as Lovable builds… click through your app" and from the August change that preserves on-screen state. No source states it outright.
8. **Steering mid-run.** Observed: "You don't have to wait for Lovable to finish before sending your next message." Lovable picks a follow-up up at its "next natural stopping point without losing completed work", typically within seconds. Follow-ups replaced the earlier message queue on 8 September 2026. Some actions are labelled "Runs after the current task" and always wait: Try to fix, inline text edits from the preview, suggested SEO questions. ([Project chat](https://docs.lovable.dev/features/projects/chat), [Changelog](https://docs.lovable.dev/changelog))
9. **Stop.** Observed: a stop button halts work at once. Completed work is kept and only finished work is charged. ([Project chat](https://docs.lovable.dev/features/projects/chat))
10. **Running cost.** Observed: the More options menu shows "Working for" and "Credits used" during the run, then "Worked for" and "Credits used" afterwards. ([Project chat](https://docs.lovable.dev/features/projects/chat))
11. **Finish.** Observed: response actions are "Undo latest edit", "Revert to this version", Copy, Helpful / Not helpful. More options adds copy message link, preview that version, and the time and credit summary. Lovable "may suggest features to build next as clickable chips near the chat input". ([Project chat](https://docs.lovable.dev/features/projects/chat)) Observed (third party): the end state includes "A summary of what was built". ([Mantlr](https://mantlr.com/blog/how-to-use-lovable-2026))

**Timing.** Observed: first build "takes a few minutes" (Lovable); "1-3 minutes for a moderate-complexity app" ([Mantlr](https://mantlr.com/blog/how-to-use-lovable-2026)); "Within a minute" ([EntreResource](https://entreresource.com/loveable-ai/)).

**Not found:** whether reasoning text streams word by word, whether it collapses when done, and what a task list looks like on screen.

## 4. Prompt input details

- **Dictation.** Observed: microphone, `Option/Alt+V`, with transcript clean-up that removes filler words (19 September 2026). A spoken "Start voice conversation" mode exists. The mobile app shows "a live waveform while you speak". ([Project chat](https://docs.lovable.dev/features/projects/chat), [Changelog](https://docs.lovable.dev/changelog), [Mobile app](https://docs.lovable.dev/integrations/lovable-mobile-app))
- **Attachments.** Observed: attach via the menu, drag and drop, or paste. Up to 10 files per message; 20 MB per file on Free, 256 MB on paid, 1 GB on Enterprise; images 15 MB in total. Types include images, PDF, Office files, audio, CSV, ZIP, Markdown and Figma files. Clicking an attached file opens a readable preview, and ZIP contents can be inspected before use. ([Project chat](https://docs.lovable.dev/features/projects/chat), [Changelog](https://docs.lovable.dev/changelog))
- **The + menu.** Observed: three groups. Project (History, Knowledge, Design system, Settings, GitHub, GitLab), Add context (Skills, Projects, Connectors, Code, Figma designs, Screenshots, Attachments), Help & support. "Take a screenshot" opens the browser's screen capture. ([Project chat](https://docs.lovable.dev/features/projects/chat))
- **Scoping to a selected element.** Observed: in Select elements mode, "Click the element you want to change"; hold Cmd/Ctrl to add more. "Each selected element attaches to the project chat input as a reference, and your prompt applies to all of them." ([Preview toolbar](https://docs.lovable.dev/features/preview-toolbar))
- **Direct edits without a prompt.** Observed: Edit text inline lets you "Click into any text on the page" and edit in place; 100 inline text edits are free. ([Preview toolbar](https://docs.lovable.dev/features/preview-toolbar))
- **Draw to explain.** Observed: Draw annotation lets you "sketch on top of your app preview and send the sketch as an image alongside a message"; simple shapes are recognised and tidied. ([Preview toolbar](https://docs.lovable.dev/features/preview-toolbar))
- **Comments.** Observed: comments pin to elements, teammates reply, commenting is free, and sending a thread to Lovable is charged as build usage. ([Preview toolbar](https://docs.lovable.dev/features/preview-toolbar))
- **Code references.** Observed: type `@` or use line-number chips to reference code. ([Code mode](https://docs.lovable.dev/features/code-mode))
- **Suggestions.** Observed: next-step chips appear near the input after a response; clicking fills the prompt. ([Project chat](https://docs.lovable.dev/features/projects/chat))
- **Knowledge.** Observed: workspace knowledge (rules for all projects) and project knowledge (one project), each up to 10,000 characters, set in settings under Knowledge. Both are included as context with every response; project knowledge wins on conflict; edits apply to the next message. ([Knowledge](https://docs.lovable.dev/features/knowledge))
- **Credit display.** Observed: a credit bar in the workspace menu at the top of the sidebar. "The filled part of the bar is what you have left, so the bar gets shorter as you use credits." Per-message cost is under More options. A "Free" badge replaces the amount when the daily chat allowance covered a message. ([Credits and usage](https://docs.lovable.dev/introduction/credits-and-usage))
- **Not found:** whether a balance or cost estimate is shown in the input before sending, and what an element reference chip looks like.

## 5. Undo, history, restore

All Observed from [Version history](https://docs.lovable.dev/features/projects/history) unless stated.

- **Automatic versions.** "Lovable saves every change as a version automatically." There is no save button.
- **Entry points.** History toggle in the top bar, or + menu → Project → History. Two tabs: all versions and bookmarked versions.
- **Look without changing.** Clicking a version opens "a snapshot view, where you can look around that state of your app without changing anything". "Back to latest" exits.
- **Per-version actions.** Revert, a Bookmark toggle, and More actions: "Open preview in new tab", "View code changes" (a diff), "Go to message in chat".
- **Revert is not destructive to the chat.** "the conversation continues from where you are."
- **Limits stated plainly.** Revert restores "code only". "It does not restore or roll back your database data." Very old versions can be opened but no longer restored.
- **Quick undo.** "Undo latest edit" and "Revert to this version" under each response. ([Project chat](https://docs.lovable.dev/features/projects/chat))
- **Edit and resend.** Hover your own message, Edit message, then "Revert and resend": the project returns to the state before that message and runs the revised instruction.
- **Bookmarks.** "Bookmark a known-good version before starting a big change".
- **Compare.** For code, the diff per version. For plans, undo and redo arrows step through revisions with a banner such as "Viewing version 2 of 3". ([Plan mode](https://docs.lovable.dev/features/plan-mode)) Not found: a side-by-side visual compare of two app versions.
- **Drafts.** A draft is a copy of the project with its own chat, preview and edits. "nothing you build in a draft reaches your project until you accept it." Accept merges; Delete discards. A draft auto-names itself from the first prompt. ([Drafts](https://docs.lovable.dev/features/drafts))
- **Cost.** "messages you later revert still count."

## 6. Error handling

- Observed: "When a build error appears while Lovable works, a Try to fix button appears on the activity card." ([Project chat](https://docs.lovable.dev/features/projects/chat))
- Observed: "When a build error appears, select Try to fix. Lovable finds the issue and attempts a fix." ([FAQ](https://docs.lovable.dev/introduction/faq))
- Observed: 10 free fixes per account, each returning 24 hours after use, shared with security-scan fixes; after that fixes cost build credits. ([Changelog](https://docs.lovable.dev/changelog), [Debugging](https://docs.lovable.dev/prompting/prompting-debugging))
- Observed: Try to fix always runs after the current task, never mid-run. ([Project chat](https://docs.lovable.dev/features/projects/chat))
- Observed: the same recovery appears at publish. A failed build turns the button into "Build errors need fixing" with a Try to fix option. ([Publish](https://docs.lovable.dev/features/publish))
- Observed: Lovable's advice when a fix does not hold: "Stop retrying blind fixes. Ask Lovable to find the root cause in Plan mode before changing more code." Then revert if needed. ([Debugging](https://docs.lovable.dev/prompting/prompting-debugging))
- Observed: preview failures have their own short, plain messages: "Starting live preview…", "Still building?" (environment paused after inactivity), "Live preview couldn't start", "Live preview lost connection", "Live preview stopped responding". Each has a "Try again" button. Previews also retry by themselves if the connection drops during start-up. ([Preview](https://docs.lovable.dev/features/projects/preview), [Changelog](https://docs.lovable.dev/changelog))
- Observed (third party): a known failure pattern is the "fix loop", where Try to fix introduces new errors. One guide estimates the button handles about 60% of simple issues. ([AppStuck](https://www.appstuck.com/blog/lovable-troubleshooting-guide-fix-the-10-most-common-errors-2026), search excerpts for [Shipper](https://shipper.now/lovable-errors/))
- Inferred: build errors are shown largely as raw technical text (for example "Cannot find module './Button'"), with the button as the plain-language route out. Basis: third-party lists of error strings users meet. ([AppStuck](https://www.appstuck.com/blog/lovable-troubleshooting-guide-fix-the-10-most-common-errors-2026))
- Not found: the exact wording of the build-error card in chat, and whether failed work is refunded.

## 7. Long jobs, background work, notifications

- Observed: one Build message can run "up to 10 hours". In the last thirty minutes it "finishes what is in progress instead of starting new work, and summarizes what is done and what remains". ([Build mode](https://docs.lovable.dev/features/agent-mode))
- Observed: typing `/goal` makes Lovable work one message until the goal is met. A banner warns: "Lovable will work until your goal is achieved. This might take hours and use a large number of credits." Such messages are marked Goal in the chat. ([Goal runs](https://docs.lovable.dev/features/goal-runs))
- Observed: credit check-ins. When a message crosses the check-in level (20 credits by default) "The run pauses with a card showing what the message has cost so far", with Continue or Finish up. ([Credits and usage](https://docs.lovable.dev/introduction/credits-and-usage), [Changelog](https://docs.lovable.dev/changelog))
- Observed: running out of credits pauses rather than ends the work. "A card in the project chat lets you add credits and resume where Lovable left off, or have Lovable wrap up what's in progress." ([Build mode](https://docs.lovable.dev/features/agent-mode))
- Observed: mobile push notifications. "Opt in from your device settings to be notified when a build is ready or needs your input. Tapping a notification opens the relevant screen." ([Mobile app](https://docs.lovable.dev/integrations/lovable-mobile-app))
- Observed: the desktop app has multi-project tabs. ([Desktop app](https://docs.lovable.dev/integrations/desktop-app))
- Inferred: work continues server-side when the tab is closed. Basis: 10-hour runs and "build is ready" push notifications make little sense otherwise. The docs do not say it.
- Not found: web or desktop notifications, sounds, email on completion, and any indicator on the dashboard or sidebar for a project that is still working.

## 8. Publish and share

**Publish.** All Observed from [Publish](https://docs.lovable.dev/features/publish).

- Publish button, top right. One dialog, one view (simplified 19 August 2026).
- Opening it starts a quick security scan automatically, about 10 seconds. Status line reads "Running quick security scan", then "No security issues found" or, for example, "2 critical security issues found".
- A suggested `lovable.app` address is prefilled and editable.
- Visibility: anyone with the link on Free and Pro; Public, Workspace or Custom on Business and Enterprise.
- Success reads "Your website is live", with copy link and visit.
- The live site is a snapshot. Later edits show in the preview straight away but go live only via "Publish changes". A small dot on the Publish button signals unpublished changes.
- Unpublish from settings, the dialog's menu, or the dashboard.
- Publishing can also be asked for in chat: "publish, deploy, ship, or go live". ([Project chat](https://docs.lovable.dev/features/projects/chat))

**Share.** All Observed from [Share a project](https://docs.lovable.dev/features/share-project).

- Share button in the top bar. Invite people by email as Admin, Editor or Viewer.
- Invite links add anyone who opens them as a collaborator; they expire after 5 days.
- Shared preview links give "view-only access to the latest in-progress version" with no account needed. Password and expiry on higher plans. With Allow comments on, guests can comment on the preview without an account.
- Remix makes an independent copy; public remixing is off by default. ([Remix](https://docs.lovable.dev/features/projects/remix))

## 9. Motion and feel

This section is short because public text rarely describes motion and I saw no recordings.

- Observed: the preview is the main "alive" signal. Changes appear in it during the build, and since August it holds its on-screen state instead of reloading after each change. ([Preview](https://docs.lovable.dev/features/projects/preview), [Changelog](https://docs.lovable.dev/changelog))
- Observed (third party, older): the preview may "first [show] a loading indicator or a basic layout and then components start appearing". ([Sidetool](https://www.sidetool.co/post/getting-started-with-lovable-ai-build-full-stack-web-apps-with-just-prompts))
- Observed: waiting is filled with named activity (current step, files, tools) and a running clock and cost ("Working for", "Credits used"), not a bare spinner. ([Build mode](https://docs.lovable.dev/features/agent-mode), [Project chat](https://docs.lovable.dev/features/projects/chat))
- Observed: loading copy is specific and present-tense: "Starting live preview…", "Running quick security scan". ([Preview](https://docs.lovable.dev/features/projects/preview), [Publish](https://docs.lovable.dev/features/publish))
- Observed: live waveform while dictating on mobile. ([Mobile app](https://docs.lovable.dev/integrations/lovable-mobile-app))
- Observed: sidebar peeks on hover and pins on click. ([Editor](https://docs.lovable.dev/features/projects/editor))
- Observed: Lovable's own stated principle, written about apps built with it: showing the model's thinking means "people see progress instead of waiting at a blank screen". ([Changelog](https://docs.lovable.dev/changelog), 6 August 2026)
- Inferred: the home placeholder types and cycles (see section 1).
- Not found: durations, easing, page transitions, the home-to-editor transition, skeletons or shimmer, how activity cards enter, any completion animation, sounds.

A Motion Designer should record a live session before specifying any timing from Lovable.

## 10. Takeaways for Clipnera

**Adopt**

1. **Keep the prompt through sign-up.** A signed-out visitor types, hits send, signs up, and the prompt is still there. For Clipnera, keep the pasted video link or chosen file reference as well.
2. **One box, with a mode picker inside it.** Build / Chat / Plan maps to Edit / Ask / Plan. "Ask" answers questions about the video without touching it, and a "Start editing" card moves to a real edit.
3. **Preview updates in place.** Hold the playhead position, zoom and selected clip when an edit lands. Never reset the player after each change.
4. **Activity cards with a Details view.** Show each step as a card (transcribing, finding moments, reframing, captioning, rendering). Details has a Timeline tab and a Changes tab listing what changed on the video's timeline.
5. **Follow-ups instead of a queue.** Let users type while the AI works; apply the message at the next safe point. Label anything that must wait "Runs after the current task".
6. **Point, then prompt.** Selecting something attaches it to the input as a reference. In video, that is a clip, a time range, a caption line or a region of the frame. Add inline caption text editing that needs no prompt, and drawing on the frame to explain a change.
7. **A version per edit, with a look-only snapshot.** Open any version to watch it without changing anything, then Revert. Add bookmarks, "Undo latest edit" under each response, and "Revert and resend" on the user's own messages.
8. **Say what undo will not undo.** Lovable states that revert restores code, not data. Clipnera should state its own limits in the same plain way, for example that a clip already posted to YouTube stays posted and spent credits are not returned.
9. **Cost and time in view, with check-ins.** Show a running timer and credits used during work. Pause with a Continue / Finish up card at a set threshold, and pause rather than fail when credits run out. This suits renders well.
10. **One-click recovery where the failure shows.** A "Try to fix" button on the failed card, and the same button in the export dialog when an export cannot proceed. Add question cards (up to four, skippable, with sensible defaults) and next-step chips after each response.

**Do not copy**

1. **A code view and developer chrome.** Files, Code, Cloud, Security and SEO tabs serve app builders. Clipnera's equivalent is the timeline; do not import a crowded More menu.
2. **Raw technical error text.** Lovable passes compiler and database errors through. Clipnera's users are creators; write every error in plain words with one next action.
3. **Retry as the only answer.** The fix loop is Lovable's most reported pain. Cap automatic retries and offer revert alongside the fix.
4. **The "watch it build from nothing" model.** A web app can appear piece by piece in seconds. Video renders cannot. Show fast proxies first (transcript, chosen moments, thumbnails, low-resolution preview) and do not promise a live frame-accurate result mid-render.
5. **Snapshot publishing with a "changes pending" dot, and a public remix gallery.** A website has one live copy to update; a posted video does not. Export is a new file each time. User footage is personal, so no community feed of other people's projects by default.

## Could not find

- The signed-out home page as it looks today: headline, chips under the input, sections below. `lovable.dev/` blocked my fetcher.
- The first on-screen response after sending a prompt, and whether reasoning text streams.
- Whether the chat and preview panels can be dragged to resize.
- Exact wording of the build-error card.
- Web or desktop notifications, sounds, and whether work continues with the tab closed (inferred only).
- Almost all motion detail: timings, easing, transitions.

## Sources

Lovable documentation and site

- https://docs.lovable.dev/llms.txt
- https://docs.lovable.dev/introduction/getting-started
- https://docs.lovable.dev/introduction/dashboard-overview
- https://docs.lovable.dev/introduction/credits-and-usage
- https://docs.lovable.dev/introduction/faq
- https://docs.lovable.dev/features/projects/editor
- https://docs.lovable.dev/features/projects/chat
- https://docs.lovable.dev/features/projects/preview
- https://docs.lovable.dev/features/projects/history
- https://docs.lovable.dev/features/projects/remix
- https://docs.lovable.dev/features/preview-toolbar
- https://docs.lovable.dev/features/agent-mode
- https://docs.lovable.dev/features/plan-mode
- https://docs.lovable.dev/features/chat-mode
- https://docs.lovable.dev/features/goal-runs
- https://docs.lovable.dev/features/drafts
- https://docs.lovable.dev/features/code-mode
- https://docs.lovable.dev/features/knowledge
- https://docs.lovable.dev/features/publish
- https://docs.lovable.dev/features/share-project
- https://docs.lovable.dev/features/business/design-templates
- https://docs.lovable.dev/features/testing
- https://docs.lovable.dev/integrations/build-with-url
- https://docs.lovable.dev/integrations/lovable-mobile-app
- https://docs.lovable.dev/integrations/desktop-app
- https://docs.lovable.dev/prompting/prompting-debugging
- https://docs.lovable.dev/changelog
- https://lovable.dev/templates
- https://lovable.dev/community
- https://lovable.dev/use-cases/websites

Third party

- https://entreresource.com/loveable-ai/
- https://mantlr.com/blog/how-to-use-lovable-2026
- https://www.sidetool.co/post/getting-started-with-lovable-ai-build-full-stack-web-apps-with-just-prompts
- https://www.appstuck.com/blog/lovable-troubleshooting-guide-fix-the-10-most-common-errors-2026
- https://forum.bubble.io/t/animated-input-placeholder-like-lovable-solved/380562
- https://offers.hubspot.com/view/lovable-marketers-guide (search excerpt only)
- https://shipper.now/lovable-errors/ (search excerpt only)

Tried and unreachable

- https://lovable.dev/ and https://www.lovable.dev/ (HTTP 403)
- https://web.archive.org/ copy of the home page (fetcher cannot reach the archive)
- https://hostadvice.com/ai-app-builders/lovable-review/ (HTTP 403)
- https://feedback.lovable.dev/ (did not resolve)
