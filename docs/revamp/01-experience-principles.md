# Clipnera UI revamp — Wave 1: experience principles

Date: 3 October 2026. Builds on [00-audit.md](00-audit.md) and the two reference studies: [research/cardboard.md](research/cardboard.md) and [research/lovable.md](research/lovable.md).

This document defines how prompting should feel in Clipnera. Wave 2 designs screens against it, Wave 3 turns its events into contracts, and Wave 7 tests against its numbers.

## 1. What the evidence is, and is not

Both studies come from public material only: docs, changelogs, launch threads. Nobody on this project has used either product or watched a recording.

- **Well evidenced:** what each product does — checkpoints, queues, activity cards, version history, recovery buttons, prompt kept through sign-up.
- **Not evidenced:** how either product moves. No timings, easing, transitions or streaming behaviour could be confirmed. Cardboard's panel positions, context chips and slash commands were also not found.

So the behaviours in this document are borrowed with a source, and **every timing and motion value is Clipnera's own decision**, not a measurement of a reference. Before Wave 2 motion work is signed off, someone should record a live session of each product (Cardboard has a 3-day trial and a launch demo at `youtu.be/xLBxatFM7uk`).

## 2. Where Clipnera starts

From the audit ([00 §6.1](00-audit.md)):

- No prompt box in the clip studio or the Editor. The footage reel board has a message box that drops the user's message and never shows a reply.
- No streaming, no plan, no step list beyond a four-step checklist during footage analysis.
- Undo is in-memory and lost on reload. The Editor's Timeline model has server versions with no UI.
- Pipeline start depends on the browser tab staying open.
- Three things already point the right way: `lib/editor/timeline.ts` (13 validated operations, server versions), `ReelPreviewPlayer` (plays low-res proxies from a plan without a render), and the notification inbox.

## 3. Principles

1. **Never a dead second.** From Enter to result, something true is always changing on screen: an acknowledgement, a plan line, a step, a preview. A bare spinner is a defect.
2. **Footage first, prompt second.** The prompt is most useful when there is something to talk about. Home asks for a video or link and a prompt together; the editor prompt always knows what is selected. (Cardboard moved to this in August 2026.)
3. **One prompt, one version.** Every AI edit is a single named version and a single undo, however many operations it took. (Cardboard, Lovable.)
4. **Undo is where the result is.** The undo control sits on the result message and in the top bar, not hidden. (A Cardboard user could not find theirs.)
5. **Calm while working, short when done.** Steps collapse to one line while running and to a short summary after. Detail is one click away, never forced. (Cardboard's "calmer chat"; Lovable's Details view.)
6. **Say what was not done.** The assistant checks its result before reporting, and states plainly what it could not do. No padding, no silent partial work. (Cardboard.)
7. **The user is never blocked.** They can type, queue, stop, scrub and hand-edit while the assistant works. Long jobs run on the server and outlive the tab.
8. **Point, then prompt.** Whatever is selected — clip, time range, caption line, asset — attaches to the prompt as a chip. (Lovable's element references.)
9. **Ask with choices, not paragraphs.** When the assistant needs a decision, it shows options in the conversation and carries on after the pick. (Both.)
10. **Cost is visible before it is spent.** Anything that uses credits shows the amount first, and a run pauses rather than fails when credits run out. (Lovable; the audit found unconfirmed credit spend today.)
11. **Plain words.** No model names, no technical errors, no jargon. Every error has one next action.
12. **Clipnera's own product.** Its own layout, name and voice on the amber and neutral palette. No "Director" persona, no model picker, no developer chrome.

## 4. The prompt bar

**Where it lives**
- **Home:** the hero. A single input that takes a prompt and a video (paste a link, drop or pick a file). Below it: suggestion chips, then recent projects.
- **Editor and clip studio:** docked in the conversation panel, always visible. `⌘K` focuses it from anywhere in the app; `/` focuses it when no field has focus.
- **Mobile:** a bottom sheet over the preview.

The existing command palette also uses `⌘K`. Decision: the palette's navigation commands move into the prompt bar's slash menu, so there is one entry point. This changes an existing shortcut's behaviour and needs the owner's confirmation in Wave 2.

**Parts**
- Text area, grows to six lines, then scrolls.
- Attach button: video, image, audio, or a reference link.
- Context chips row, above the text.
- Mode switch: **Edit** (default; changes the project, uses credits), **Ask** (answers questions about the video, changes nothing), **Plan** (writes a plan to approve, changes nothing until approved).
- Send button, which becomes a separate **Stop** button beside it while a run is active. Stop never clears typed text.
- Credit hint: shown only when the action has a known cost.

**Context chips**
| Chip | Added when | Shows |
|---|---|---|
| Clip | a clip is selected | title, duration |
| Range | a range is selected on the timeline or transcript | `0:12 – 0:31` |
| Caption line | a transcript line is selected | first words |
| Asset | a library item is selected or dropped on the bar | thumbnail, name |
| Moment | the user clicks "Ask about this frame" | timecode |

Chips are removable. With no chip, the prompt applies to the whole project and the bar says so in its placeholder.

**Slash commands**

Typing `/` opens a filterable menu. Each command fills a prompt template the user can edit before sending; none runs on selection.

| Command | Does |
|---|---|
| `/clips` | find the best moments |
| `/captions` | add or restyle captions |
| `/trim` | remove silences, fillers, retakes |
| `/reframe` | change aspect ratio and tracking |
| `/broll` | add B-roll, from either library |
| `/hook` | write or change the opening hook |
| `/audio` | clean up or level audio |
| `/music` | add or change music |
| `/export` | export with given settings |
| `/undo` | undo the last AI edit |
| `/go` | navigate: projects, settings, library |

**Suggestions**
- Home: four to six starter chips, written for the user's situation (no video yet; a video in progress; clips ready).
- After each result: up to three next-step chips based on what just happened. Clicking fills the bar; it does not send.

**Sign-in.** A signed-out visitor's prompt, link and file choice are kept through sign-in and restored in the bar. Nothing runs until they press send. (The audit found this input is discarded today.)

## 5. From Enter to result

Budgets are targets for Wave 3 to design for and Wave 7 to measure.

| # | Moment | What the user sees | Budget |
|---|---|---|---|
| 1 | Send | Their message appears in the conversation; the bar clears and stays usable; a working line appears under the message | under 100 ms, done locally before any network reply |
| 2 | Understanding | Working line reads "Reading your request" with the chips it is using | until first server event |
| 3 | Plan | A short plan streams in as plain sentences: what it will do, to which clips, and the credit cost if any | first text under 1.5 s (p50), under 3 s (p95) |
| 4 | Question (only if needed) | A choice card with up to four options and "Skip, use your best guess" | — |
| 5 | Steps | The plan becomes a step list. One step is active at a time, with a verb and an object: "Finding cut points", "Trimming 14 silences", "Adding captions" | a visible change at least every 5 s; if a step runs longer, it shows a count or percentage |
| 6 | Timeline updates | Each operation appears on the timeline as it is applied, briefly highlighted | within 250 ms of the server event |
| 7 | Proxy preview | The preview plays the edited result from low-res proxies | under 2 s after the last operation |
| 8 | Check | Step "Checking the result" — the assistant reviews frames and audio | — |
| 9 | Result | Steps fold into one summary line. The message shows what changed, anything it could not do, a version name, **Undo** and **Compare** buttons, and next-step chips | — |
| 10 | Full quality | The preview swaps to full quality when ready, with no jump in playhead position | background |

**Plan approval**
- In **Edit** mode the plan is shown and the run continues without waiting. Exception: if the run will spend credits beyond a threshold, or will remove more than a set share of the timeline, it pauses on a "Go ahead" card. Thresholds are remote config.
- In **Plan** mode the plan is a document the user can edit, then approve.

**While it works**
- The user can keep typing. New messages go into a visible, numbered queue above the bar; items can be reordered, edited or removed. Each runs when the previous one finishes.
- Stop halts at the next safe point. Completed operations stay as a version; the message says what was and was not done.
- The user can scrub, play and select freely. Hand edits to clips the run is not touching are allowed. A clip the run is working on shows a lock and is released when its step ends.

**Collapsed and expanded**
- Running: one line, "Trimming silences · step 2 of 4 · 0:18".
- Expanded: the step list, each with its state and, when done, what it changed.
- After: a **Details** view with two tabs — **Steps** (what the assistant did) and **Changes** (the timeline operations, in plain words).

## 6. Preview

- **Proxy first.** Every source gets a low-res proxy at upload. The editor preview composes proxies in the browser from the Timeline, as `ReelPreviewPlayer` already does for reels. No render is needed to see an edit.
- **Hold position.** When an edit lands, the playhead, zoom and selection stay put. If the edit is elsewhere, a "Jump to change" chip appears instead of moving the playhead.
- **Quality badge.** A small "Preview quality" label while proxies are playing; it disappears when full quality is in.
- **Before commit.** Destructive or stylistic edits with a strength (cleanup, caption style, colour) offer a hover preview on the user's own footage and, where it applies, Light / Balanced / Tight.

## 7. Versions

- **Every AI edit is a version.** Named from the prompt ("Trimmed silences, added captions"), editable. Hand edits group into a version after a pause or on leaving the editor.
- **History panel.** A list with name, time, author (you or assistant), and a thumbnail. Opened from the top bar.
- **Look without changing.** Clicking a version opens it read-only in the preview with a "Viewing an earlier version" bar and **Back to latest**.
- **Restore.** Makes that state the newest version. Nothing is deleted; later versions stay in the list.
- **Undo.** On the result message, in the top bar, `⌘Z`. One press undoes the whole AI edit.
- **Compare.** Before and after, as a toggle (hold to see before) and as a side-by-side at the changed range.
- **Edit and resend.** On the user's own message: returns to the state before it and runs the revised prompt.
- **Bookmarks.** Pin a version to keep it easy to find.
- **Limits, stated in the UI.** Restoring a version does not unpublish a clip already posted, and does not return credits.

The Timeline model's operations and server versions ([audit 05](audit/05-clips-studio-editor.md)) are the base for all of this.

## 8. When things go wrong

Every error message has three parts: what happened, what is still safe, and one next action.

| Situation | What the user sees | Action offered |
|---|---|---|
| Request not understood | "I'm not sure which clip you mean." | Choice card, or a rewritten prompt to send |
| Could only do part | Summary lists what was done and what was not, and why | "Try the rest" with a suggested prompt |
| Not enough material | "There isn't enough footage of X to do this." | Suggested alternatives |
| A step failed | The step turns to failed; completed steps stay as a version | **Try again** on the step; **Undo** beside it |
| Second failure | No automatic third try | Suggested different prompt; contact link |
| Out of credits | The run pauses, it does not fail | Add credits and resume, or finish with what is done |
| File cannot be read | Names the file and what to convert it to | Replace file |
| Connection lost | "Reconnecting — your edit is still running." | None needed; state resyncs on return |
| Export failed check | Export is verified before it is handed over | Retry, or what is missing |

Automatic retries are capped at one. The audit found that validation failures currently show as "Something went wrong"; that message is retired.

## 9. Long jobs

- **Server-owned.** Uploads, analysis, AI edits, renders and exports run on the server. Closing the tab changes nothing. (Today the browser starts the pipeline.)
- **Activity.** A header indicator shows running jobs across projects, each with its current step. Project cards show the live step, not a frozen percentage.
- **Done.** In-app notification and toast always. Browser notification if the user has allowed it. Email for jobs longer than a threshold, on by default and switchable in settings.
- **Return.** Opening a project with a finished run shows the result message and its version, unread.
- **Check-ins.** A run that crosses a credit threshold pauses on a card: cost so far, **Continue** or **Finish up**.

## 10. Feel

All values are Clipnera's own; none is measured from a reference.

| Motion | Spec |
|---|---|
| Streaming text | Appears in word groups with a soft fade of about 120 ms; no blinking cursor block |
| Working line | A slow shimmer across the active step's text; no spinner |
| Step change | Finished step ticks and dims over 150 ms; next step rises 4 px and fades in over 200 ms |
| Steps folding to a summary | Height collapse, 200 ms |
| Operation landing on the timeline | The clip gets an amber outline that fades over 600 ms |
| Version added | The history count in the top bar pulses once |
| Panel open and close | 200 ms, ease-out |
| Page transition | 150 ms cross-fade; the shell never re-mounts |
| Media hover | Preview starts after 150 ms of hover; preloaded on pointer approach |
| Proxy to full quality | Cross-fade 200 ms, same frame |

- Range: 150–250 ms for interface motion; the 600 ms highlight is the one deliberate exception, because it carries meaning.
- `prefers-reduced-motion`: movement and shimmer are replaced by instant state changes and a static "Working" label. Streaming text appears in sentence-sized steps.
- No sound.

## 11. Voice

- The assistant has no persona name. The UI says "Clipnera" or nothing.
- First person, present tense, short: "Trimming 14 silences." "Done — 3 clips, captions added."
- Steps are verb plus object. No "processing", "executing", "pipeline", "tokens", "model".
- Numbers over adjectives: "Removed 42 seconds", not "Tightened it up a lot".
- Never claims more than was checked. The landing page's "real footage, real output" over stock clips is the kind of line this rules out.

## 12. What Clipnera deliberately does differently

| Reference does | Clipnera does | Why |
|---|---|---|
| Cardboard: full professional editor with keyframes and blend modes | A focused timeline; the prompt is the main tool | Users want clips from long videos |
| Cardboard: model picker, bring your own agent | No model choice; models are set per plan | Already decided |
| Cardboard: desktop and Chrome only | Review, approve and prompt on a phone | Clips are made for phones |
| Lovable: message queue replaced by mid-run follow-ups | A visible queue | Timeline edits are not safely interruptible mid-operation; revisit once the runtime supports it |
| Lovable: raw technical errors with a fix button | Plain-language errors, one retry, then a different suggestion | Avoid the fix loop |
| Lovable: watch it build live | Proxies first, labelled as preview quality | Video cannot render frame-accurately mid-run |
| Lovable: public community gallery | None | Footage is personal |

## 13. What this needs from later waves

- **Wave 2:** prompt bar, chip, choice card, step list, result message, queue, history panel, compare, activity indicator and quality badge as components, in every state.
- **Wave 3:** an event stream per run (acknowledged, plan text, question, step started, step progress, operation applied, check, result, failed, paused), resumable after reconnect; server-owned jobs; proxy generation at upload.
- **Wave 4:** `/broll`, the Asset chip, and the "chose this clip because…" line with one-click swap.
- **Wave 5:** `prompt_streaming_v2`; remote config for the approval and check-in thresholds, retry cap and email threshold.
- **Wave 7:** measure the budgets in section 5.

## 14. Open questions

| # | Question | Default if unanswered |
|---|---|---|
| 1 | `⌘K` moves from the command palette to the prompt bar | Yes, with palette commands under `/go` |
| 2 | Is "Ask" mode free, or does it use credits? | Free within a daily allowance |
| 3 | Credit threshold for pausing a run | Set in remote config; start at the cost of a 30-minute source video |
| 4 | Email on completion, on by default? | On for jobs over 5 minutes |
| 5 | Who records live sessions of Cardboard and Lovable to fill the motion gap? | Owner, or approve a trial account |
