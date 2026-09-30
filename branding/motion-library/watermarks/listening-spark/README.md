# Listening Spark

| | |
|---|---|
| Type | Watermark |
| Status | In use: top-right watermark on every branded video |
| Preview | `listening-spark.mp4`, 1080×1920, 30 fps, 8 s |
| Design round | 2 |
| Source | `branding/motion/source/kit.js`, function `W1` |

## What happens

The sparkle swells and glows with the voice in the clip, and three small level bars move with it. It goes quiet when nobody is speaking. In real exports it follows the clip's actual loudness; this preview uses a sample voice.

## Why it fits Clipnera

The mark listens to the video like the AI does, so the watermark feels alive without distracting.

## Where it runs

Sprites in `backend/static/branding/watermark/listening-spark/`. `backend/branding/watermark.py` rebuilds every frame from the clip's loudness and `backend/branding/service.py` lays it over the top-right corner.

## Re-render

```sh
node branding/motion/source/render.mjs library --only listening-spark
```
