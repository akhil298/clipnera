# Motion kit: every asset the Before/After look needs, where it comes from, how it is stored

Built from the 84 reels in `before_after_reels/` (see `before_after_reels/ANALYSIS.md`).
Rule carried over from the owner's licensing decisions: **only assets with a clean licence**
(CC0, public domain, MIT/ISC/OFL, or made by us). The old `backend/static/motion/library/`
(Drive packs, no licence) is never copied into this kit.

---

## 1. Three kinds of asset

| Kind | Share of what the reels show | How we get it |
|---|---|---|
| **A. Drawn by our templates** (no file) | ~50 % | Code: count-up numbers, list chips, ✓/✗ stacks, keyword-behind-subject, bar/line charts, flow diagrams, timelines, UI mock-ups (search bar, notification, chat bubble, profile card, price ticket, checklist), name tags, CTA pills, frames, highlight boxes |
| **B. Free with a clean licence** (download once) | ~30 % | The sets in §2 |
| **C. Made by us with an image model** (generate once, cache forever) | ~20 % | Prompts in §5: 3D objects the free sets lack, realistic metaphor and documentary stills, backgrounds |

Brand logos are a special case: the SVG files are CC0, but the trademarks still belong to their owners.
They may only be shown when the speaker names the brand, never as an endorsement, and never in an ad
for a competitor.

---

## 2. Free sets to download (kind B)

| Set | What it gives | Licence | Approx. size |
|---|---|---|---|
| Microsoft Fluent Emoji, 3D style only | ~1,500 glossy 3D objects (money bag, brain, tooth, rocket, trophy, pizza, phone, house, calendar, chart…): the "3D icon pops" in the reels | MIT | ~250 MB (3D PNGs) |
| Lucide | ~1,500 line icons for chips, bullets and UI mocks | ISC | ~5 MB |
| Tabler Icons | ~5,000 line + filled icons (fallback for Lucide gaps) | MIT | ~20 MB |
| Simple Icons | ~3,000 brand logos as SVG (Swiggy, Zomato, ChatGPT, YouTube, Instagram…) | CC0 files, trademarks apply | ~15 MB |
| Natural Earth (1:10m) | World countries + admin-1 (Indian states, US states) for the map-zoom template | Public domain | ~60 MB |
| Kenney: UI Audio, Interface Sounds, Impact Sounds | Clicks, pops, whooshes, impacts, notification blips | CC0 | ~30 MB |
| Poly Haven + ambientCG textures | Paper, kraft, fabric, wood, marble, concrete surfaces for card backgrounds | CC0 | ~400 MB at 2K (pick ~40) |
| Google Fonts (OFL) | Inter, Instrument Serif, Playfair Display, Bricolage Grotesque, Space Grotesk, Oswald, Sora, Caveat (handwritten), plus the Noto scripts we already ship | OFL | ~30 MB |

Already in the repo and kept: `static/motion/sfx/synth/` (236 synthesised sounds), `static/motion/fonts/`
(Anton, Bebas, Montserrat, Poppins, Noto scripts, Twemoji), the 10 curated SFX that are clean.

---

## 3. Folder layout

```
backend/static/motion/kit/
  manifest.json                 one entry per asset (schema in §4), the only thing code reads
  LICENSES/                     one file per source set, copied verbatim
  fonts/<family>/<file>.ttf
  icons/
    line/lucide/<name>.svg
    line/tabler/<name>.svg
    3d/fluent/<name>.png        transparent, 512 px (+ 1024 px in 3d/fluent@2x/)
    3d/made/<name>.png          our generated 3D objects, same spec as fluent
  logos/<brand>.svg             Simple Icons, filename = slug
  objects/                      (= icons/3d/made; kept as one place, see above)
  stills/
    metaphor/<id>.jpg           realistic concept images, 1080x1920 and 1920x1080 crops
    business/<id>.jpg
    india/<id>.jpg
    documentary/<id>.jpg
    places/<id>.jpg
  backgrounds/
    paper/  grid/  gradient/  studio/  bokeh/  shadow/  desk/  fabric/
  textures/
    grain/  dust/  light_leak/  halftone/  glitch/  paper_overlay/
  maps/
    world_countries.geojson
    admin1_india.geojson
    admin1_usa.geojson
  sfx/
    whoosh/  pop/  click/  ding/  riser/  impact/  cash/  typing/
    notification/  glitch/  swipe/  camera/  heartbeat/  tick/
  luts/<name>.cube              our own grades: warm_teal_orange, clean_bright, moody_dark, bw_before
```

Built by `backend/scripts/build_motion_kit.py` (free sets, manifest, `--push`/`--pull` one tarball per source
through S3) and `backend/scripts/generate_kit_images.py` (the made images; its lists in §5 below are the
canonical ones). Only `kit/README.md` is in git; the worker pulls the rest in `setup_ec2.sh`. LUTs are
written by `backend/beats/grade.py` on first use. Fonts stay in `static/motion/fonts/`.
`kit/` is separate from the unlicensed `library/` so the two can never mix.

---

## 4. Manifest entry (one per asset)

```json
{
  "id": "obj.rupee_coin",
  "kind": "object3d",
  "path": "icons/3d/made/rupee_coin.png",
  "words": ["rupee", "rupees", "₹", "inr", "money", "salary", "paise"],
  "topics": ["money", "india", "finance"],
  "style": "glossy_3d",
  "palette": ["#16a3a3", "#f2c94c"],
  "size": [1024, 1024],
  "anchor": "center",
  "transparent": true,
  "source": "made",
  "source_url": "",
  "licence": "own",
  "attribution": "",
  "made_with": "image model + prompt id obj.rupee_coin v1",
  "added": "2026-10-19"
}
```

- `kind`: `icon_line | object3d | logo | still | background | texture | map | sfx | font | lut`.
- `words` are what the beat planner matches against the speech. A beat only uses an asset whose `words` contain a word that was actually said.
- SFX entries add `peak_s` (when the hit lands) and `duration_s`, like `sfx/manifest.json` today.
- Stills add `orientation` and a `safe_zone` box (where text can sit without covering the subject).

Naming: lowercase snake_case, no spaces, ids prefixed by kind (`obj.`, `still.`, `bg.`, `sfx.`, `logo.`, `icon.`).

---

## 5. Prompt for the image model (kind C)

Use one shared style block per family, so everything looks like one kit. Generate each item
in the list below it. Never real people, real logos or readable real text inside an image.

### 5.1 3D objects (only those Fluent 3D lacks)

**Style block**

```
A single {OBJECT}, glossy 3D render, soft studio lighting from the top-left, subtle reflections,
smooth rounded forms, slightly stylised (not photoreal, not cartoon), centred, three-quarter view,
fills about 80 % of the frame, fully transparent background, no shadow on the ground, no text,
no logos, no hands, no people. Colours: {PALETTE}. Square, 1024x1024, PNG with alpha.
```

`{PALETTE}` default: "rich teal and warm gold accents". Money items: "teal and gold".
Health: "soft red and white". Tech: "deep blue and white". Food: natural colours.

**Items** (id: object)
- Money: `rupee_coin` (Indian rupee coin with a ₹ embossed), `rupee_notes_stack`, `dollar_coin`,
  `gold_bars`, `calculator`, `credit_card_blank`, `wallet_open`, `piggy_bank`, `cheque_blank`, `upi_qr_card_blank`
- Charts: `bar_chart_rising`, `line_chart_arrow_up`, `arrow_down_red`, `pie_chart`, `target_with_arrow`
- Health: `kidney`, `lungs`, `liver`, `thyroid_gland`, `molecule_generic`, `dopamine_molecule`,
  `dna_helix`, `capsule_pill`, `pill_bottle`, `denture`, `tooth_implant`, `skin_layers_cross_section`,
  `collagen_protein_blob`, `stethoscope`, `water_glass`
- Work & tech: `laptop_open`, `smartphone_blank_screen`, `microphone_podcast`, `clapperboard`,
  `film_reel`, `retro_tv`, `retro_radio`, `server_rack`, `robot_head_friendly`, `ai_chip`
- Ideas: `lightbulb_glowing`, `gear_pair`, `puzzle_pieces`, `chess_king`, `hourglass`, `key`,
  `padlock`, `shield_check`, `megaphone`, `magnifying_glass`
- Status: `check_badge_green`, `cross_badge_red`, `question_mark_3d`, `exclamation_warning_3d`,
  `star_badge`, `stamp_approved_blank`
- Places & things: `house_small`, `apartment_tower`, `office_building`, `shop_front_blank`,
  `metro_train`, `delivery_scooter`, `car_generic`, `airplane`, `globe`, `map_pin`
- Food & fashion: `burger_fries_combo`, `sushi_platter`, `chai_glass`, `pizza_slice`, `tshirt_folded`, `hoodie`

### 5.2 Realistic stills (metaphor, business, India, documentary)

**Style block**

```
Cinematic photograph, {SCENE}. Natural light, shallow depth of field, 35 mm look, subtle film grain,
warm highlights with teal shadows, real-world textures, believable people seen from behind,
in silhouette or too small to identify, no faces in focus, no text, no signs with words, no logos,
no watermarks. Leave clean negative space in the {SAFE_ZONE} for a title.
Vertical 1080x1920 (also deliver a 1920x1080 version of the same scene).
```

`{SAFE_ZONE}` default: "upper third".

**Metaphor** (`still.metaphor.*`)
lone climber reaching a snowy summit at dawn · man standing on a pile of rubble lit by a single spotlight ·
person standing on a glowing pillar above a dark crowd · hand reaching up toward a floating golden trophy ·
crossroads signpost in fog · maze seen from above with one figure inside · figure walking toward light at the end of a tunnel ·
seedling pushing through cracked earth · staircase rising into clouds · door opening onto bright light ·
broken chain on concrete · lone figure in an empty stadium · silhouette in a field at dusk looking at the horizon ·
person holding an umbrella alone in heavy rain · storm clouds over a city skyline · road through an empty desert ·
person juggling too many papers at a desk at night · tangled cables leading to one plug · empty chair in a spotlight ·
sand running through a large hourglass on a table

**Business** (`still.business.*`)
small team meeting around a laptop · two hands shaking over a desk · busy call centre (backs only) ·
warehouse aisles with boxes · factory line close-up · shop owner arranging a counter (from behind) ·
customer paying by phone at a counter (hands only) · real-estate living room, kitchen, bathroom, facade (four images) ·
clinic waiting room · dental chair in a modern clinic · doctor's hands with a stethoscope and a chart ·
gym with equipment · restaurant table seen from above with many dishes · laptop with a blurred analytics dashboard

**India** (`still.india.*`)
Mumbai skyline at dusk · metro train platform · Bangalore tech park at night · small kirana shop shelves ·
roadside chai stall with steam · monsoon street with umbrellas · highway at night with light trails ·
train interior with passengers (backs) · wedding crowd from above (no faces) · farmer's field at sunrise

**Documentary** (`still.documentary.*`, generic, never real events or real people)
officers in plain dark uniforms entering a building at dawn (no insignia) · court gavel on a wooden desk ·
newspaper lying on a wooden table with blank columns · cash being handed over inside a car (hands only) ·
open-pit coal mine from above · bare interrogation room with one lamp · cluster of press microphones on a podium ·
generic government building with columns · police barricade at night with blue light · freight train crossing a bridge

### 5.3 Backgrounds (`bg.*`)

**Style block**

```
Clean background plate for a vertical video card, {SURFACE}, even soft lighting, no objects in the centre,
no text, subtle texture only, 1080x1920 (and 1920x1080).
```

**Surfaces**
cream paper · kraft paper · light grid paper · dark blueprint grid · pastel gradients (peach, mint, lavender, sky) ·
dark studio with thin vertical gold light strips · purple neon studio haze · white seamless wall with plant-leaf shadow ·
warm wall with palm-leaf shadows · wooden desk seen from above · white marble · rust-orange fabric ·
grey concrete · warm bokeh lights · deep navy gradient with soft glow

---

## 6. Prompt for the collection agent (kinds B and C, end to end)

```
You are building Clipnera's clean motion kit at backend/static/motion/kit/, following docs/motion_kit/ASSET_KIT.md.

1. Download only the sets in §2, from their official repositories or sites. Save each set's licence
   verbatim into kit/LICENSES/<set>.txt. If a file's licence is unclear, skip it.
2. Normalise:
   - Fluent 3D PNGs: trim, square-pad, 512 px and 1024 px. Lucide/Tabler/Simple Icons: keep SVG, slug names.
   - Natural Earth: export the countries + admin-1 (India, USA) layers to GeoJSON, simplified to under 2 MB each.
   - SFX: mono or stereo 48 kHz WAV, loudness-normalised to -16 LUFS, leading silence trimmed, peak time measured.
   - Textures/backgrounds: 2K JPEG at quality 85, plus 1080x1920 crops.
3. Generate the kind-C items in §5 with the configured image model, one image per item, using each family's
   style block. Reject and regenerate any image with readable text, a logo, an identifiable face, or a
   background that is not transparent where it must be. Record the prompt id in made_with.
4. Write one manifest entry per asset (schema §4). Fill `words` with the spoken words that should trigger it:
   singular, plural, common Hindi/Hinglish forms and the symbol (e.g. ₹). Fill `topics`.
5. Validate: every manifest path exists, every id is unique, every asset has a licence, there are no
   files outside the manifest, and total size is reported per folder.
6. Upload the binaries to S3 (the same bucket as the settings), commit the manifest, LICENSES, SVGs, maps,
   fonts and LUTs, and print a summary table: count and size per kind, and anything skipped with the reason.
Never copy anything from backend/static/motion/library/ or motion_assets/ into the kit.
```

---

## 7. Rough totals

| Kind | Count | Size |
|---|---|---|
| Line icons | ~6,500 | ~25 MB |
| 3D objects (Fluent + made) | ~1,580 | ~300 MB |
| Logos | ~3,000 | ~15 MB |
| Stills (made) | ~60 scenes × 2 crops | ~60 MB |
| Backgrounds + textures | ~60 | ~150 MB |
| Maps | 3 files | ~5 MB |
| SFX (Kenney + synth) | ~450 | ~80 MB |
| Fonts | ~12 families | ~30 MB |
