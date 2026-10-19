"""Make the kit's own images with the configured image model (docs/motion_kit/ASSET_KIT.md §5).

Three families, each with one shared style so the kit looks like one set:
3D objects the free sets lack (transparent PNG), realistic stills for ideas,
business, India and generic documentary moments (portrait JPEG), and card
backgrounds. Every image is recorded with its prompt id and trigger words in
``kit/made/records.json``; ``build_motion_kit.py --only made`` adds them to the
manifest. Images already on disk are skipped, so a run can be resumed.

The model is ``IMAGE_MODEL`` (e.g. a gpt-image deployment) at OPENAI_ENDPOINT.
This spends money: about 150 images. Try ``--dry-run`` and ``--only`` first.

    cd backend && venv/bin/python scripts/generate_kit_images.py --dry-run
    venv/bin/python scripts/generate_kit_images.py --only objects --limit 5
"""

from __future__ import annotations

import argparse
import base64
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from beats.kit import kit_dir  # noqa: E402
from clients.ai.openai import OpenAI  # noqa: E402
from core.config import get_settings  # noqa: E402

KIT = kit_dir()
RECORDS = KIT / "made" / "records.json"

OBJECT_STYLE = (
    "A single {thing}, glossy 3D render, soft studio lighting from the top-left, subtle reflections, smooth rounded "
    "forms, slightly stylised (not photoreal, not cartoon), centred, three-quarter view, fills about 80% of the frame, "
    "fully transparent background, no shadow on the ground, no text, no logos, no hands, no people. Colours: {palette}."
)
STILL_STYLE = (
    "Cinematic photograph, {thing}. Natural light, shallow depth of field, 35 mm look, subtle film grain, warm "
    "highlights with teal shadows, real-world textures, believable people seen from behind, in silhouette or too small "
    "to identify, no faces in focus, no text, no signs with words, no logos, no watermarks. Leave clean negative "
    "space in the upper third for a title. Vertical composition."
)
BACKGROUND_STYLE = (
    "Clean background plate for a vertical video card, {thing}, even soft lighting, no objects in the centre, "
    "no text, subtle texture only. Vertical composition."
)
PALETTES = {
    "money": "rich teal and warm gold accents", "chart": "fresh green and white", "health": "soft red and white",
    "tech": "deep blue and white", "idea": "warm amber and white", "status": "bright, clean colours",
    "place": "warm neutral tones with teal accents", "food": "natural appetising colours",
}

# (id, what to draw, extra trigger words) per group; the id's own words trigger it too.
OBJECTS: dict[str, list[tuple[str, str, str]]] = {
    "money": [
        ("rupee_coin", "Indian rupee coin with a ₹ symbol embossed", "rupee rupees ₹ inr salary paise money"),
        ("rupee_notes_stack", "neat stack of Indian rupee banknotes (no readable text)", "rupees cash notes lakh crore money"),
        ("dollar_coin", "gold coin with a $ symbol", "dollar dollars $ usd coin"),
        ("gold_bars", "three stacked gold bars", "gold bars bullion wealth"),
        ("calculator", "pocket calculator", "calculator calculate math maths"),
        ("credit_card_blank", "blank credit card with a chip", "card credit debit payment"),
        ("wallet_open", "open leather wallet", "wallet purse spend"),
        ("piggy_bank", "piggy bank", "savings save piggy"),
        ("upi_qr_card_blank", "small stand with a QR code pattern (no text)", "upi qr scan pay"),
    ],
    "chart": [
        ("bar_chart_rising", "3D bar chart with rising bars and an arrow", "growth grow increase revenue sales"),
        ("arrow_down_red", "bold red arrow pointing down", "drop fall loss decrease down"),
        ("pie_chart", "3D pie chart with one slice pulled out", "share percent percentage split"),
        ("target_with_arrow", "dartboard target with an arrow in the bullseye", "target goal aim"),
    ],
    "health": [
        ("kidney", "anatomical human kidney", "kidney kidneys renal"),
        ("lungs", "anatomical human lungs", "lungs lung breathing"),
        ("liver", "anatomical human liver", "liver fatty"),
        ("thyroid_gland", "anatomical thyroid gland", "thyroid hormones"),
        ("dopamine_molecule", "ball-and-stick molecule model", "dopamine molecule chemical serotonin hormone"),
        ("dna_helix", "DNA double helix", "dna genes genetic"),
        ("capsule_pill", "two-tone medicine capsule", "pill pills tablet medicine capsule"),
        ("pill_bottle", "medicine bottle with pills", "medicine medication prescription"),
        ("denture", "full denture set", "denture dentures teeth"),
        ("tooth_implant", "dental implant in a tooth model", "implant implants tooth teeth"),
        ("skin_layers_cross_section", "cross-section of human skin layers", "skin pores acne collagen"),
        ("stethoscope", "stethoscope", "doctor stethoscope checkup"),
        ("water_glass", "glass of water", "water hydration drink fluid"),
    ],
    "tech": [
        ("laptop_open", "open laptop with a blank glowing screen", "laptop computer work"),
        ("smartphone_blank_screen", "smartphone with a blank glowing screen", "phone mobile smartphone app"),
        ("microphone_podcast", "podcast microphone", "podcast microphone mic"),
        ("clapperboard", "film clapperboard", "film video shoot movie"),
        ("film_reel", "film reel", "film reel cinema"),
        ("retro_tv", "retro television set", "television tv"),
        ("retro_radio", "retro radio", "radio"),
        ("robot_head_friendly", "friendly robot head", "ai robot automation"),
        ("ai_chip", "computer chip with glowing circuits", "ai chip processor gpu"),
    ],
    "idea": [
        ("lightbulb_glowing", "glowing light bulb", "idea ideas lightbulb"),
        ("gear_pair", "two interlocking gears", "process system systems"),
        ("puzzle_pieces", "two puzzle pieces fitting together", "puzzle fit solution"),
        ("chess_king", "chess king piece", "strategy chess"),
        ("hourglass", "hourglass with sand", "time patience hourglass"),
        ("key", "golden key", "key secret unlock"),
        ("padlock", "closed padlock", "security lock locked"),
        ("shield_check", "shield with a check mark", "safe protect protection"),
        ("megaphone", "megaphone", "marketing announce loud"),
        ("magnifying_glass", "magnifying glass", "search research find"),
    ],
    "status": [
        ("check_badge_green", "round green badge with a white check mark", "yes correct right done"),
        ("cross_badge_red", "round red badge with a white cross", "no wrong mistake"),
        ("question_mark_3d", "bold question mark", "question why what how"),
        ("exclamation_warning_3d", "warning triangle with an exclamation mark", "warning danger careful"),
        ("star_badge", "gold star badge", "best star rating"),
    ],
    "place": [
        ("house_small", "small modern house", "house home homes"),
        ("apartment_tower", "modern apartment tower", "apartment flat property tower"),
        ("office_building", "glass office building", "office company corporate"),
        ("shop_front_blank", "small shop front with a blank sign", "shop store dukaan business"),
        ("metro_train", "metro train carriage", "metro train"),
        ("delivery_scooter", "delivery scooter with a box", "delivery swiggy zomato order"),
        ("car_generic", "modern car", "car cars drive"),
        ("airplane", "passenger airplane", "flight travel plane"),
        ("globe", "globe of the earth", "world global globe"),
    ],
    "food": [
        ("burger_fries_combo", "burger with fries", "combo burger fries"),
        ("sushi_platter", "sushi platter", "sushi"),
        ("chai_glass", "glass of Indian masala chai", "chai tea"),
        ("pizza_slice", "slice of pizza", "pizza"),
        ("tshirt_folded", "folded t-shirt", "tshirt shirt clothes apparel"),
    ],
}

# (id, scene, trigger words)
STILLS: dict[str, list[tuple[str, str, str]]] = {
    "metaphor": [
        ("summit_dawn", "a lone climber reaching a snowy summit at dawn", "goal success top climb achieve"),
        ("rubble_spotlight", "a man standing on a pile of rubble lit by a single spotlight", "work out survive comeback"),
        ("pillar_above_crowd", "a person standing on a glowing pillar above a dark crowd", "stand out different future"),
        ("trophy_reach", "a hand reaching up toward a floating golden trophy", "reward win winner prize"),
        ("crossroads_fog", "a crossroads signpost in fog", "choice decision direction lost"),
        ("maze_above", "a hedge maze seen from above with one small figure inside", "confused lost maze complex"),
        ("tunnel_light", "a figure walking toward light at the end of a tunnel", "hope light end"),
        ("seedling_cracks", "a seedling pushing through cracked earth", "growth start begin grow"),
        ("stairs_clouds", "a staircase rising into clouds", "steps progress level"),
        ("door_light", "a door opening onto bright light", "opportunity open new"),
        ("broken_chain", "a broken chain on concrete", "freedom free break"),
        ("empty_stadium", "a lone figure in an empty stadium", "alone pressure lonely"),
        ("dusk_field", "a silhouette in a field at dusk looking at the horizon", "hope dream future"),
        ("rain_umbrella", "a person holding an umbrella alone in heavy rain", "sad hard struggle tough"),
        ("storm_city", "storm clouds over a city skyline", "crisis storm problem"),
        ("desert_road", "a straight road through an empty desert", "journey road long"),
        ("desk_overload", "a person buried in papers at a desk at night", "stress busy overwhelmed work"),
        ("empty_chair_spot", "an empty chair in a spotlight", "missing empty absence"),
    ],
    "business": [
        ("team_laptop", "a small team meeting around a laptop", "team meeting work office"),
        ("handshake_desk", "two hands shaking over a desk", "deal client partner agreement"),
        ("call_centre", "a busy call centre seen from behind", "calls leads support"),
        ("warehouse", "warehouse aisles stacked with boxes", "stock inventory warehouse"),
        ("customer_pay_phone", "a customer paying by phone at a counter, hands only", "payment pay customer"),
        ("living_room", "a bright modern living room interior", "interior home living room"),
        ("kitchen_modern", "a modern kitchen interior", "kitchen interior"),
        ("bathroom_modern", "a modern bathroom with a stone basin", "bathroom basin"),
        ("clinic_waiting", "a clean clinic waiting room", "clinic hospital doctor"),
        ("dental_chair", "a dental chair in a modern clinic", "dentist dental teeth"),
        ("gym_floor", "a gym floor with equipment", "gym fitness workout"),
        ("restaurant_spread", "a restaurant table seen from above with many dishes", "restaurant food dinner"),
    ],
    "india": [
        ("mumbai_dusk", "the Mumbai skyline at dusk", "mumbai city india"),
        ("metro_platform", "a metro train platform in an Indian city", "metro delhi station"),
        ("tech_park_night", "a Bangalore tech park at night", "bangalore tech it job"),
        ("kirana_shelves", "the shelves of a small Indian kirana shop", "shop kirana dukaan"),
        ("chai_stall", "a roadside chai stall with steam", "chai tea stall"),
        ("monsoon_street", "a monsoon street with umbrellas", "monsoon rain"),
        ("highway_trails", "an Indian highway at night with light trails", "highway road travel"),
        ("train_interior", "an Indian train interior with passengers seen from behind", "train railway"),
        ("farm_sunrise", "a farmer's field at sunrise", "farmer farm village"),
    ],
    "documentary": [
        ("dawn_raid", "officers in plain dark uniforms entering a building at dawn, no insignia", "raid police cbi ed"),
        ("court_gavel", "a court gavel on a wooden desk", "court judge law case"),
        ("newspaper_table", "a newspaper lying on a wooden table with blank columns", "news newspaper report"),
        ("cash_handover_car", "cash being handed over inside a car, hands only", "bribe cash hawala corruption"),
        ("coal_mine", "an open-pit coal mine from above", "coal mining mine"),
        ("interrogation_room", "a bare interrogation room with one lamp", "arrest interrogation custody"),
        ("press_mics", "a cluster of press microphones on a podium", "press media statement"),
        ("government_building", "a generic government building with columns", "government minister parliament"),
        ("police_barricade", "a police barricade at night with blue light", "police security"),
        ("freight_bridge", "a freight train crossing a bridge", "train freight transport"),
    ],
}

BACKGROUNDS: list[tuple[str, str, str]] = [
    ("cream_paper", "cream paper", "paper cream"), ("kraft_paper", "kraft paper", "paper kraft"),
    ("grid_paper", "light grid paper", "grid paper"), ("blueprint_grid", "dark blueprint grid", "blueprint grid"),
    ("gold_strip_studio", "a dark studio with thin vertical gold light strips", "studio dark gold"),
    ("neon_haze", "a purple neon studio haze", "neon purple"), ("leaf_shadow_wall", "a white wall with plant-leaf shadow", "white shadow plant"),
    ("palm_shadow_wall", "a warm wall with palm-leaf shadows", "warm palm shadow"), ("desk_top", "a wooden desk seen from above", "desk wood"),
    ("rust_fabric", "rust-orange fabric", "fabric orange"), ("warm_bokeh", "warm bokeh lights", "bokeh warm"),
    ("navy_glow", "a deep navy gradient with a soft glow", "navy blue gradient"),
]


def plan() -> list[dict[str, Any]]:
    jobs = []
    for group, items in OBJECTS.items():
        for ident, thing, words in items:
            jobs.append({"family": "objects", "id": f"obj.made.{ident}", "path": f"icons/3d/made/{ident}.png", "kind": "object3d",
                         "prompt": OBJECT_STYLE.format(thing=thing, palette=PALETTES[group]), "size": "1024x1024",
                         "background": "transparent", "words": [*ident.split("_"), *words.split()], "topics": [group]})
    for group, items in STILLS.items():
        for ident, scene, words in items:
            jobs.append({"family": "stills", "id": f"still.{group}.{ident}", "path": f"stills/{group}/{ident}.jpg", "kind": "still",
                         "prompt": STILL_STYLE.format(thing=scene), "size": "1024x1536", "background": "opaque",
                         "words": [*ident.split("_"), *words.split()], "topics": [group]})
    for ident, surface, words in BACKGROUNDS:
        jobs.append({"family": "backgrounds", "id": f"bg.made.{ident}", "path": f"backgrounds/made/{ident}.jpg", "kind": "background",
                     "prompt": BACKGROUND_STYLE.format(thing=surface), "size": "1024x1536", "background": "opaque",
                     "words": [*ident.split("_"), *words.split()], "topics": ["background"]})
    return jobs


def generate(client: httpx.Client, model: str, job: dict[str, Any]) -> bytes:
    body = {"model": model, "prompt": job["prompt"], "size": job["size"], "n": 1, "quality": "high",
            "background": job["background"], "output_format": "png" if job["background"] == "transparent" else "jpeg"}
    response = client.post("images/generations", json=body)
    response.raise_for_status()
    return base64.b64decode(response.json()["data"][0]["b64_json"])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--only", nargs="+", choices=("objects", "stills", "backgrounds"))
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    jobs = [job for job in plan() if not args.only or job["family"] in args.only]
    todo = [job for job in jobs if not (KIT / job["path"]).is_file()]
    if args.limit:
        todo = todo[:args.limit]
    print(f"{len(jobs)} planned, {len(todo)} to make")
    if args.dry_run:
        for job in todo:
            print(f"- {job['id']}: {job['prompt'][:90]}...")
        return
    settings = get_settings()
    model = (getattr(settings, "IMAGE_MODEL", "") or "").strip()
    if not model:
        sys.exit("Set IMAGE_MODEL to the image deployment's name first.")
    records = json.loads(RECORDS.read_text(encoding="utf-8")) if RECORDS.is_file() else []
    known = {record["id"] for record in records}
    headers = {"Authorization": f"Bearer {settings.OPENAI_API_KEY}", "Content-Type": "application/json"}
    with httpx.Client(base_url=OpenAI.BASE_URL, headers=headers, timeout=300) as client:
        for job in todo:
            try:
                data = generate(client, model, job)
            except httpx.HTTPError as exc:
                print(f"failed {job['id']}: {exc}")
                continue
            target = KIT / job["path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            if job["id"] not in known:
                records.append({"id": job["id"], "kind": job["kind"], "path": job["path"], "words": sorted(set(job["words"])),
                                "topics": job["topics"], "source": "made", "source_url": "", "licence": "own",
                                "made_with": f"{model}: {job['prompt']}", "added": date.today().isoformat(),
                                **({"transparent": True, "style": "glossy_3d"} if job["kind"] == "object3d" else {})})
                known.add(job["id"])
            RECORDS.parent.mkdir(parents=True, exist_ok=True)
            RECORDS.write_text(json.dumps(records, ensure_ascii=False, indent=1), encoding="utf-8")
            print(f"made {job['id']}")


if __name__ == "__main__":
    main()
