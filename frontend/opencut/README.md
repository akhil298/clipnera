# Vendored OpenCut editor

The timeline editor at `/studio/[projectId]` is the editor from
[opencut-classic](https://github.com/opencut-app/opencut-classic) (MIT, see `LICENSE`),
copied from upstream commit `cf5e79e` (the archived repo's last `main`) on 2026-10-09.
The upstream repo is archived, so fixes here are ours to make.

## What was copied

Only the files the upstream editor page reaches through its imports (`src/`), plus its
global stylesheet (`tools/editor.css`). Upstream's accounts, database, blog, changelog,
feedback form, onboarding tour and theme toggle were left out.

## Changes from upstream

- Imports use `@opencut/...` instead of `@/...`, and `lucide-react-oc` (an npm alias of the
  newer lucide-react the editor needs) so Clipnera's own icons don't change.
- `src/clipnera/editor-shell.tsx` is upstream's editor page without the tour and changelog,
  with the tooltip and toast providers its root layout used to supply.
- `src/clipnera/opencut-wasm.ts` loads `opencut-wasm` in the browser; webpack can't parse
  its `.wasm` (see `next.config.mjs`).
- Header: Clipnera icon, no Discord link or feedback form, "Exit" goes to `/dashboard/editor`.
- Colours: Clipnera's amber accent and neutral dark theme.
- Fixed upstream type errors in `services/storage/migrations` and `stickers/providers`.

## Styles

The editor uses Tailwind v4; Clipnera uses v3. They are built apart:

```sh
cd frontend/opencut/tools && npm install && npm run build
```

This writes `frontend/public/opencut/editor.css`, with every token moved from `:root` to
`.oc-root`. The studio page adds `oc-root` to `<body>` and loads the file only while the
editor is open. Rebuild after changing classes in `src/`.

## Not wired yet

- Projects and media live in the browser (IndexedDB/OPFS), not in Clipnera's backend.
- The Sounds tab calls upstream's `/api/sounds` proxy, which Clipnera doesn't have.


## Browser support (TODO 17.3)

Not yet tried in real Safari or Firefox; this is what the code needs, and what it does without it.

| Needs | Used for | Chrome / Edge | Safari | Firefox | Without it |
|---|---|---|---|---|---|
| WebCodecs (`VideoDecoder`/`VideoEncoder`, via mediabunny) | decoding imports, browser export | yes | decode from 16.4, encode from 17 | from 130 | imports may not preview; use **Render on server** to export |
| WebGPU (`navigator.gpu`) | the preview renderer | yes | 26+ | 141+ (Windows) | falls back to canvas; the header shows "For the best experience, open the editor in Chrome" |
| IndexedDB + OPFS | the media cache for opened projects | yes | yes (OPFS 15.2+) | yes | media downloads again on every open |
| Streaming `fetch` bodies | following a running AI plan | yes | yes | yes | — |

Screens under 1024 px wide get the mobile gate (`src/components/editor/mobile-gate.tsx`), in Clipnera's words.
