# OpenCut ↔ Timeline v1 bridge

The studio (OpenCut) edits a scene in the browser; Clipnera stores a **Timeline v1**
(`backend/editor/timeline.py`, mirrored by `frontend/lib/editor/timeline.ts`). The backend copy
is the source of truth: the AI agent, the renderer and the op log all read it. This file says
how one maps onto the other. Code: `src/clipnera/bridge.ts` (conversion), `diff.ts` (scene
change → ops), `backend-sync.ts` (saving), `backend-project.ts` (loading).

## Time

| OpenCut | Timeline v1 |
|---|---|
| `MediaTime`, integer ticks (`TICKS_PER_SECOND`) | whole frames at `timeline.fps` (24/25/30/60) |
| project `settings.fps` | `timeline.fps`; locked for Clipnera projects (no ratchet on import) |

`frames = round(ticks × fps / TICKS_PER_SECOND)`; `ticks = round(frames × TICKS_PER_SECOND / fps)`.
Loading a project snaps every element to a frame.

## Tracks

| OpenCut | Timeline v1 `kind` | Notes |
|---|---|---|
| `tracks.main` (video) | `video` | `extra.role = "main"`; the first `video` track if none is marked |
| overlay `video` track | `overlay` | |
| overlay `text` track | `text` | |
| overlay `graphic` / `effect` track | `graphic` | `extra.type` keeps which |
| `audio` track | `audio` | |
| `name` | `extra.name` | |
| `muted`, `hidden` | `muted`, `hidden` | |

Track order on the backend: overlay tracks in OpenCut order, then main, then audio.

## Elements → items

Fields the bridge **owns** are compared and sent as ops. Everything else an element has goes into the
item's `extra` untouched (`extra.element`), and fields the backend has that OpenCut doesn't
(keyframes, transitions, a caption style) are kept from the stored item.

| OpenCut element | Item | Owned fields |
|---|---|---|
| `video` / `image` (media) | `clip` | `startTime→at`, `mediaId→asset`, `trimStart→src_in`, `src_in + duration×rate → src_out`, `retime.rate→speed`, `volume` dB → linear 0–2, `transform.position{X,Y}` px → `0.5 + px/canvas`, `transform.scaleX→scale`, `transform.rotate→rotation` |
| upload `audio` | `clip` on an audio track | as above, no transform |
| `text` | `text` | `at`, `duration→dur`, `params.content→text` (first 200 chars; the rest in `extra.content`), transform; `style = "studio"` for new text |
| `sticker` / `graphic` / `effect` | `graphic` | `at`, `duration→dur` |
| library `audio` | `sfx` | `at`, `dur`, `name`, `volume→gain_db` |

An `image` asset is 1 frame long and its clip plays `src_out − src_in` frames.

## Not shown in the studio (kept on the backend as they are)

`music` items, `sfx` items without studio data, `captions`, `markers`, `look`. The diff never
removes or changes these, and never removes a track that holds one.

## Media

Each OpenCut media id **is** the backend asset id. On import the file is PUT to
`editor/{user}/{project}/…` in S3 (`POST /editor/projects/{id}/assets/init`), then an
`add_asset` op adds it; elements that use it are sent once that is done. On load, media comes from
the browser's own cache when it has the file, else from the signed URL in `asset_urls`.

## Known gaps

- A reel's clip `transform.x/y` means "point of the source kept centred" (a crop); the studio
  shows it as an offset from centre, so imported reels can look shifted in the studio preview.
- Keyframes and transitions from a reel are kept but not shown or editable in the studio.
- Changing the frame rate of a Clipnera project isn't possible from the studio.
