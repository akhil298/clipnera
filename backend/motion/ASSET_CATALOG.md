# Motion asset library

All motion assets live under `backend/static/motion/`. Raw assets are
categorized under `library/<category>/`, compiled runtime graphics and fonts
have their own folders, and the catalog, previews, curated sound effects, and
generated sound effects are also under this root.
`backend/static/motion/catalog.json` is the consolidated index across all of
them.

Readable guides for editing models, regenerated after any change:

- `static/motion/ASSETS.md`: everything renders can use (shipped): sounds with length, peak, shape,
  tone and loudness, hook graphics, fonts, branding.
- `static/motion/LIBRARY.md`: the local library (never on servers) with the same facts and a
  licence status per file, for choosing what to promote.

Clean the library (duplicates, rips, meme audio, unusable font formats) before indexing:

```sh
cd backend
venv/bin/python -m scripts.clean_motion_library            # dry run
venv/bin/python -m scripts.clean_motion_library --apply
venv/bin/python -m scripts.describe_motion_assets
```

Build or refresh the index locally:

```sh
cd backend
venv/bin/python -m scripts.organize_motion_library --dry-run
venv/bin/python -m scripts.organize_motion_library
venv/bin/python -m scripts.index_motion_library
```

Each catalog entry includes its backend-relative runtime path and original
source path, inferred category and
tags, file type, size, and available media facts such as duration, dimensions,
frame rate, codecs, audio streams, and alpha-channel hints. Videos get a
contact sheet and uniformly sampled time slices, allowing a downstream vision
model to inspect representative frames without opening the original file.
Files inside ZIP bundles are listed separately with their member paths and
sizes; they must be extracted before a renderer can use them.
Contact sheets are local generated files and are excluded from Git; regenerate
them with the catalog command when needed.

Backend callers can retrieve ranked candidates with
`motion.catalog.search_assets(query, category=...)`; `prompt_context(...)`
serializes the best candidates and their preview/time-slice references for an
editing-model prompt. `resolve_asset(...)` returns directly stored assets or
safely extracts a selected ZIP member to a local cache. Direct files rank
ahead of archive-only copies.

Descriptions and tags are inferred from filenames and folders only. The local
indexer does not generate semantic captions or upload assets to a provider;
the catalog marks that limitation on every entry. License status is also
explicitly left for review before publication.
