# Clipnera brand motion

Every branded export plays as **The Moment** (intro) → the clip with the **Listening Spark**
watermark in the top-right corner → **Caption Beat** (end card). Branding follows the
existing watermark switch: always on for Free, on by default for paid plans, which can turn it off.

| Folder | What is in it |
|---|---|
| `motion-library/` | Every motion, grouped by type (intros, transitions, end cards, watermarks). Each folder has a preview video and a README with its details. |
| `motion/source/` | The motion code (`kit.js` for round 2, `reel.html` for round 1), `catalog.json` with every motion's details, bundled fonts, and `render.mjs`. |
| `../backend/static/branding/` | The files exports are made with: the intro and end card for 9:16, 16:9 and 1:1, the watermark pieces, and `manifest.json`. |
| `../backend/branding/` | The branding pass: `service.py` joins intro, clip and end card; `watermark.py` makes the watermark follow the clip's sound. |

## Changing a motion

1. Edit the code in `motion/source/` (and the text in `catalog.json`).
2. Re-render with Node and Google Chrome installed (no npm packages needed):

   ```sh
   node branding/motion/source/render.mjs production            # files the backend uses
   node branding/motion/source/render.mjs library               # every preview + README
   node branding/motion/source/render.mjs library --only comet  # one preview
   ```

3. Run `cd backend && pytest tests/test_branding.py`, then commit the new files. They deploy with the code.

To use a different library motion in exports, point `production` in `catalog.json` at it and re-render `production`.
Intros and end cards drawn in `kit.js` work directly. A round-1 piece first needs porting from CSS to `kit.js`.
