# Reframe

| | |
|---|---|
| Type | End card |
| Status | In use: end card after every branded video |
| Preview | `reframe.mp4`, 1080×1920, 30 fps, 7 s |
| Design round | 2 |
| Source | `branding/motion/source/kit.js`, function `F2` |

## What happens

The clip's last frame blurs and darkens. Over it, a wide video with a face-tracking box on the speaker: a 9:16 crop window follows them, then shrinks into the tile, and the name pops in word by word like Clipnera's karaoke captions under "MADE WITH", then a "Turn long videos into shorts" pill. In real exports the blurred frame is the clip's own last frame.

## Why it fits Clipnera

Shows reframing to vertical, the other half of the product. The crop window literally becomes the logo.

## Where it runs

Rendered for 9:16, 16:9 and 1:1 in `backend/static/motion/branding/outro/`. `backend/branding/service.py` adds it to every branded export.

## Re-render

```sh
node branding/motion/source/render.mjs library --only reframe
```
