# Caption Beat

| | |
|---|---|
| Type | End card |
| Status | In use: end card after every branded video |
| Preview | `caption-beat.mp4`, 1080×1920, 30 fps, 6.5 s |
| Design round | 2 |
| Source | `branding/motion/source/kit.js`, function `F4` |

## What happens

The last frame blurs and darkens. "MADE" and "WITH" pop in on the beat with a karaoke highlight, the logo slams in and pulses with the beat, a sound line moves along the bottom, and a "Turn long videos into shorts" pill appears. In real exports the blurred frame is the clip's own last frame.

## Why it fits Clipnera

Ends every video in Clipnera's own caption style, with a clear call to action.

## Where it runs

Rendered for 9:16, 16:9 and 1:1 in `backend/static/branding/outro/`. `backend/branding/service.py` adds it to every branded export.

## Re-render

```sh
node branding/motion/source/render.mjs library --only caption-beat
```
