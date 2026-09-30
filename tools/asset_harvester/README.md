# Asset harvester

Collects sound effects and video-editing assets that are safe for commercial use into a local library. Each file it keeps comes with an audit trail.

Only these licenses pass the gate:

- **CC0-1.0**
- **Public domain**, including the CC Public Domain Mark
- **MIT** and **Apache-2.0**: the repo's `LICENSE`/`NOTICE` file is saved to `_licenses/` and linked to the asset

Everything else is rejected and logged with a reason, including CC-BY, CC-BY-SA, NC, ND, GPL and missing licenses. Pexels and Pixabay use their own licenses. Those allow commercial use but limit redistribution, so they stay off unless you pass `--allow-platform-licenses`.

## Setup

```bash
cd tools/asset_harvester
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium        # only needed for --use-browser
```

API keys come from the environment only. Sources without a key are skipped with a warning.

| Source     | Env var             | Required |
|------------|---------------------|----------|
| Freesound  | `FREESOUND_API_KEY` | yes      |
| Pexels     | `PEXELS_API_KEY`    | yes (+ `--allow-platform-licenses`) |
| Pixabay    | `PIXABAY_API_KEY`   | yes (+ `--allow-platform-licenses`) |
| GitHub     | `GITHUB_TOKEN`      | no (higher rate limits with it) |
| Wikimedia Commons, Internet Archive | — | no |

Set `HARVESTER_CONTACT` or pass `--contact` with an email or URL. Wikimedia asks for this in the User-Agent and rate-limits clients that don't send one.

## Commands

```bash
# Preview: search and license-check everything, download nothing
python harvest_assets.py --dry-run --limit-per-category 10

# Full run, all sources and categories, into a custom folder
python harvest_assets.py --dest ~/clipnera-assets --limit-per-category 50 --max-total 450

# Audio-only categories from the no-key sources, more parallel downloads
python harvest_assets.py --sources wikimedia,archive,github \
  --categories ambient,foley,ui,whooshes --download-workers 10 --per-query 40

# Strictest mode: also confirm the license on the human-facing page (JS pages via Playwright)
python harvest_assets.py --verify-pages --use-browser --categories green_screen,overlays

# Include Pexels/Pixabay video (not CC0; read their terms first)
python harvest_assets.py --sources pexels,pixabay --allow-platform-licenses \
  --categories green_screen,motion_graphics,overlays --max-file-mb 300
```

Run `python harvest_assets.py --help` for every flag. Limits apply per run. Re-running skips anything already stored, so you can top up a category by running again.

## Output

```
<dest>/
  Ambient/ Foley/ Glitch/ Green Screen/ Motion Graphics/ Overlays/ Transitions/ UI/ Whooshes/
    A/ B/ … Z/ 0-9/
      <title-slug>--<source>-<sha256[:10]>.<ext>
  _licenses/        LICENSE/NOTICE texts for MIT/Apache collections
  assets.db         SQLite ledger: assets (provenance) + decisions (every accept/reject/duplicate/failure)
  manifest.json     JSON export of the assets table, rewritten after each run
  harvest.log
```

```bash
sqlite3 asset_library/assets.db "select license_id, count(*) from assets group by 1"
sqlite3 asset_library/assets.db "select reason, count(*) from decisions where decision='rejected' group by 1 order by 2 desc"
```

## Before shipping assets to users

The license labels come from the uploaders, and the harvester trusts them. Uploaders sometimes get them wrong, for example a commercial VHS rip marked CC0 on archive.org. Use the ledger to review files by hand before they go into the product. A GitHub repo's license may cover only its code, so check the README of any repo you keep files from. Freesound gives out 128 kbps MP3 previews. Getting the original WAV/FLAC files requires Freesound OAuth2, which this tool does not implement.
