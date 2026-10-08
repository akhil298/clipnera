# Wave 6 — P1 playback engine: public API

Owner: P1 (`frontend/lib/media/**`, `frontend/lib/editor/playback/**`). For P2 (preview), T1 (timeline), X1 (transcript), R2 (reel boards), V1 (compare).
Import from `@/lib/media` (a barrel that also re-exports the clock and its hooks). Everything is UI-free. The only React code is the hooks.

## Engine

```ts
const engine = new PreviewEngine({
  timeline,                       // Timeline v1 (lib/editor/timeline.ts)
  resolveUrl: (ref, { refresh }) => Promise<string | { url, expiresAt? }>,  // you inject it; no endpoints inside
  words?,                         // CaptionWord[] in timeline seconds, for captions
  scheduler?, createElement?, document?, matchMedia?,   // injectable for tests
});
engine.mount(stageEl);            // picture layers (A/B <video> + <img> per visual track) go in, bottom track first
engine.play() / pause() / toggle() / seek(s) / seekFrame(f) / step(±frames) / setRate(0.25–4)
engine.setLoop({ start, end } | null)   engine.setSkips(ranges)   // skips = cut words in clip mode
engine.setMuted(bool)   engine.setExporting(bool)   engine.setTimeline(next)   engine.setWords(words)
engine.overlays(time?, wordsPerLine?) → OverlayFrame   // what to draw on top
engine.on(listener) → unsubscribe       engine.reducedMotion   engine.clock   engine.urls   engine.destroy()
```

- `MediaRef` is one of `{kind:'asset', asset}`, `{kind:'music', track}` or `{kind:'sfx', name}`. Give the proxy when there is one. `refresh: true` means the cached link failed or is about to expire, so skip any upstream cache. When the resolver gives no `expiresAt`, the expiry is read from the S3 SigV4/SigV2 or CloudFront query.
- Gapless cuts: the next clip is loaded and seeked into the hidden element 0.5 s ahead (`PRELOAD_SECONDS`). At the cut the elements swap, and the old one is hidden after `requestVideoFrameCallback` fires.
- The playhead never moves on `setTimeline`. It is only clamped to the new length.
- Sound: only audio tracks play (the picture is muted, as in the legacy reel preview). Music ducks by `DUCK_DB` (−10 dB) under speech. Sound effects play once from their URL.
- Placement: `placeSource` mirrors the Timeline transform semantics. Keyframes are applied, and `transition_in` gives fade, slide or zoom (an approximation, because the backend has no Timeline renderer yet).
- Background tab: hiding the tab pauses (reason `hidden`) and showing it resumes. While exporting, the clock keeps running on a timer.
- Reduced motion: slide and zoom transitions become fades. The `reduced-motion` event fires when the setting changes.

## Events (`engine.on`)

These are the clock events plus engine events:
- Clock events: `play`, `pause {reason: user|ended|hidden}`, `seek {from,to}`, `loop {to}`, `ended`, `rate {rate}`, `buffering {buffering}`. While buffering, the clock holds still: the URL is pending or an element has `readyState < 3`.
- `cue {sfx, url|null}`: the sound effect starts now. When `url` is null, the caller may synthesise it.
- `url-refreshed {ref}`: a link failed and was replaced in place, at the same position, and playback carried on.
- `media-error {ref}`: two refreshes in a row failed, so the engine paused. Show "This video could not play. Your edit is safe." and Retry.
- `reduced-motion {reduced}`.

## Clock and hooks (`lib/editor/playback`)

- `PlaybackClock`: `getState()` gives `{time, frame, playing, buffering, rate, duration, fps, loop, ended}`. `subscribe(fn, throttleMs)` only throttles ticks. Seeks, play and pause always arrive at once. Also `on(event)`, `frameAt` and `timeOfFrame`.
- Frame stepping uses `timeline.fps`. The backend now renders every cut part at one constant frame rate, so frames match the export.
- Hooks (`useSyncExternalStore`): `useClockSelector(clock, select, throttleMs?)`, `useClockTime(clock, 100)`, `useClockFrame(clock)`, `useClockPlaying`, `useClockBuffering`.
- The playhead and ruler should `clock.subscribe` and write `style.transform`, with no React state (frontend.md §5.3).

## Pure helpers (all tested)

- `evaluateOverlays(timeline, t, {words, wordsPerLine, reducedMotion})` returns `{frame, layers, base, broll, texts, hook, caption}`.
  - A `layers` entry is `{item, asset, sourceTime, transform, opacity, transition}`.
  - A `texts` entry is `{item, role: hook|pop|line|card|text, progress}`.
  - `caption` is `{words, activeIndex, style}`.
- `captionAt` and `groupCaptionWords` break lines the way the ASS burner does. `itemAt` and `itemAfter` are binary search over a track's items. `keyframeValue`, `sourceTimeAt`, `audibleAt`, `cuesBetween`.
- `fit.ts`:
  - `ASPECT_SIZE` (mirrors geometry.py), `aspectOf`, `containRect`, `placeSource`.
  - Safe zones: `SAFE_ZONES` (reels, shorts, tiktok), `combinedSafeZone`, `safeRect`, `unsafeBands`, `clearsVertically`. They return null or empty off 9:16.
- `looks.ts`: `lookFilter(look)` gives the CSS stand-ins for the FFmpeg looks. Apply it to the stage.
- `MediaUrls`: `get`, `peek`, `refresh(ref, failedUrl)`, `confirm`, `prime`, `expiryFromUrl`.

### Safe-zone values (share of 1080 × 1920, checked 5 Oct 2026)

| Platform | Top | Bottom | Left | Right | Source |
|---|---|---|---|---|---|
| Instagram Reels | 14 % | 35 % | 6 % | 6 % | Meta Ads Guide, Instagram Reels ("leave roughly 14% top, 35% bottom, 6% each side") |
| YouTube Shorts | 180 px | 390 px | 60 px | 120 px | YouTube publishes no template. These are the margins third-party templates agree on (e.g. Hopper HQ). |
| TikTok (aid only, Q4) | 130 px | 484 px | 60 px (assumed) | 140 px | TikTok in-feed ad templates, via third-party guides |

These values are tighter than the legacy studio's `SAFE_ZONES`, which were unsourced.

## NEEDS-BACKEND

- **EB-12:** 540p H.264/AAC proxies with a keyframe every 0.5 s and `faststart`. Also a storyboard sprite with VTT, and waveform peaks. Until then, `asset.proxy` is null and the full source plays.
- **Signed-URL endpoint for editor assets:** for example `GET /editor/projects/{id}/assets` returning `{asset_id: {url, proxy_url, expires_at}}`. It should accept a `refresh` flag. There are no editor asset URLs today.
- **URLs for music library tracks and sound-effect previews,** keyed by `MusicItem.track` and `SfxItem.name`.
- **EB-18:** transcript words in timeline time, for captions in editor mode.
- **HLS** (for sources over 10 min, share pages and render previews) is not built here, because composed playback uses MP4 proxies. Add `lib/media/hls.ts` once `hls.js` is installed (a Platform request).

## Requests and open questions

- **Q (owner/backend):** Should the audio in video-track clips play (`volume` on a picture clip), or only the audio tracks? The preview follows the reel adapter: picture is silent and the voice is on an audio track.
- **Q (backend):** What do the `slide_left` and `zoom` transitions mean? There is no Timeline renderer yet, so the preview approximates them.
- **Platform:** add `"type": "module"` or rename the files, to silence Node's `MODULE_TYPELESS_PACKAGE_JSON` warning in `npm test`. This is cosmetic, and it affects every `lib` test.
