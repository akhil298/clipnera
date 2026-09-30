# The Moment

| | |
|---|---|
| Type | Intro |
| Status | In use: intro before every branded video |
| Preview | `the-moment.mp4`, 1080×1920, 30 fps, 7.2 s |
| Design round | 2 |
| Source | `branding/motion/source/kit.js`, function `F1` |

## What happens

A 1 h 24 m podcast appears as its sound wave. An amber scan line reads it end to end and comes back to the peak. Brackets snap around the best 29 seconds, everything else falls away, and those bars fold into the amber tile. The sparkle draws itself, a ring bursts, and the name slides out with the line "Every long video has a moment."

## Why it fits Clipnera

The whole product in one shot: long video in, the AI finds the moment, a clip comes out, and that clip is the logo.

## Beats

- **0.0 s** The sound wave grows in, timecodes at both ends
- **1.0 s** Scan line sweeps the whole video
- **2.3 s** Scan line returns to the peak
- **2.8 s** Brackets snap around "BEST MOMENT · 0:29"
- **3.2 s** The rest falls away; the moment folds into the tile
- **4.1 s** Sparkle draws itself, ring burst
- **4.6 s** Name slides out, tagline fades in

## Where it runs

Rendered for 9:16, 16:9 and 1:1 in `backend/static/branding/intro/`. `backend/branding/service.py` adds it to every branded export.

## Re-render

```sh
node branding/motion/source/render.mjs library --only the-moment
```
