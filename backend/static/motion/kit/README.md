# Clean motion kit

Assets the graphic beats (`backend/beats`) may show. Only `manifest.json` is read by the code.
Everything here is built by `backend/scripts/build_motion_kit.py` and `backend/scripts/generate_kit_images.py`,
and synced through S3 with `build_motion_kit.py --push` / `--pull`; none of it is in git.
Sources, licences and layout: `docs/motion_kit/ASSET_KIT.md`.
