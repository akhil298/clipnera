"""Script, scenes and what each scene shows.

Scenes follow the voiceover: each is a sentence or two, 2-8 seconds, cut on
sentence ends so pictures change when the thought does. For each scene the
LLM chooses one of the creator's images, a stock B-roll search, or a text card
(for a number, a list or a quote); a validator keeps every choice usable.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any

from core.logging_config import get_logger
from transcription.language import SENTENCE_TERMINALS

log = get_logger(__name__)

MIN_SCENE_SECONDS = 2.0
# Reels hold attention with a new picture every few seconds.
MAX_SCENE_SECONDS = 6.0

SCRIPT_SYSTEM = """You write scripts for 30-45 second vertical reels. The first sentence is a hook that stops the scroll. Short spoken sentences, one idea each, concrete and specific, no hashtags, no stage directions, no emojis. Write in the language the user asks for; for Hinglish or Tenglish use Roman script mixed the way people speak. Return only the script text."""

SCENE_SYSTEM = """You are a reel editor choosing the picture for each scene of a voiceover. You return valid JSON only.

For each scene choose one:
- "image": one of the creator's own images by index, when it shows what the scene says. Prefer the creator's images: they are the product, the person, the proof. Never the same image in two scenes in a row.
- "broll": stock footage, with an English query (2-5 words) and subject (the 1-2 nouns the shot must show), for concrete things the images do not show.
- "text": a bold on-screen headline (at most 6 words) for a number, a list item, a quote or a punchline.
The first scene is the hook: give it the strongest visual. Use text for at most one scene in four."""

EXAMPLE = '{"scenes":[{"index":0,"kind":"image","image":2},{"index":1,"kind":"broll","query":"busy city morning","subject":"city"},{"index":2,"kind":"text","headline":"3x more sales"}]}'


@dataclass
class Scene:
    start: float
    end: float
    text: str
    kind: str = "text"
    image_index: int | None = None
    asset_id: str | None = None
    query: str = ""
    subject: str = ""
    headline: str = ""
    alternates: list[str] = field(default_factory=list)
    # An AI shot is being generated for this scene.
    generating: bool = False

    @property
    def duration(self) -> float:
        return self.end - self.start


def scenes_to_json(scenes: list[Scene]) -> str:
    return json.dumps([asdict(s) for s in scenes], ensure_ascii=False)


def scenes_from_json(value: str | None) -> list[Scene]:
    try:
        return [Scene(**item) for item in json.loads(value or "[]")]
    except (TypeError, ValueError):
        return []


def split_scenes(words: list[dict[str, Any]]) -> list[Scene]:
    """Scenes cut at sentence ends, merged up to MIN and split down to MAX seconds."""
    scenes: list[Scene] = []
    current: list[dict[str, Any]] = []

    def close() -> None:
        if current:
            scenes.append(Scene(float(current[0]["start"]), float(current[-1]["end"]), " ".join(w["word"] for w in current)))
            current.clear()

    for word in words:
        if current and float(word["end"]) - float(current[0]["start"]) > MAX_SCENE_SECONDS:
            close()
        current.append(word)
        long_enough = float(word["end"]) - float(current[0]["start"]) >= MIN_SCENE_SECONDS
        if str(word["word"]).endswith(SENTENCE_TERMINALS) and long_enough:
            close()
    close()
    # A short tail joins the scene before it.
    if len(scenes) > 1 and scenes[-1].duration < MIN_SCENE_SECONDS:
        tail = scenes.pop()
        scenes[-1] = Scene(scenes[-1].start, tail.end, f"{scenes[-1].text} {tail.text}")
    # Scenes play back to back: each runs until the next one starts.
    for current_scene, following in zip(scenes, scenes[1:]):
        current_scene.end = following.start
    if scenes:
        scenes[0].start = 0.0
    return scenes


async def write_script(topic: str, language: str, client: Any) -> str:
    response = await client.chat(
        [{"role": "system", "content": SCRIPT_SYSTEM},
         {"role": "user", "content": f"Language: {language}\nTopic: {topic}\n\nWrite the script."}],
        temperature=0.8, max_tokens=700,
    )
    return " ".join(response.strip().strip('"').split())


def scene_prompt(scenes: list[Scene], images: list[dict[str, Any]]) -> str:
    image_lines = "\n".join(
        f"[{i}] {img.get('role', 'other')}: {img.get('description', '')} ({', '.join(img.get('tags') or [])})"
        for i, img in enumerate(images)
    ) or "(no images)"
    scene_lines = "\n".join(f"[{i}] {s.duration:.1f}s: {s.text}" for i, s in enumerate(scenes))
    return f"Creator's images:\n{image_lines}\n\nScenes:\n{scene_lines}\n\nReturn JSON only, like: {EXAMPLE}"


async def assign_visuals(scenes: list[Scene], images: list[dict[str, Any]], client: Any) -> list[Scene]:
    """Fill each scene's kind and parameters; an unreadable answer leaves the fallback plan."""
    raw: dict[int, dict[str, Any]] = {}
    try:
        response = await client.chat(
            [{"role": "system", "content": SCENE_SYSTEM}, {"role": "user", "content": scene_prompt(scenes, images)}],
            temperature=0.4, max_tokens=120 * len(scenes) + 200, json_mode=True,
        )
        data = json.loads(response[response.find("{"): response.rfind("}") + 1])
        raw = {int(item["index"]): item for item in data.get("scenes", []) if isinstance(item, dict) and "index" in item}
    except Exception as exc:
        log.warning("Scene planning failed, using the fallback plan: %s", exc)
    return validate_visuals(scenes, images, raw)


def validate_visuals(scenes: list[Scene], images: list[dict[str, Any]], raw: dict[int, dict[str, Any]]) -> list[Scene]:
    previous_image: int | None = None
    unused = list(range(len(images)))
    for index, scene in enumerate(scenes):
        choice = raw.get(index, {})
        kind = choice.get("kind")
        image = choice.get("image")
        if kind == "image" and isinstance(image, int) and 0 <= image < len(images) and image != previous_image:
            scene.kind, scene.image_index = "image", image
        elif kind == "broll" and str(choice.get("query") or "").strip():
            scene.kind, scene.query = "broll", str(choice["query"]).strip()[:80]
            scene.subject = str(choice.get("subject") or "").strip()[:60]
        elif kind == "text" and str(choice.get("headline") or "").strip():
            scene.kind, scene.headline = "text", str(choice["headline"]).strip()[:60]
        else:
            fallback_image(scene, images, unused, previous_image)
        if scene.kind == "image" and scene.image_index in unused:
            unused.remove(scene.image_index)
        previous_image = scene.image_index if scene.kind == "image" else None
    return scenes


def avoid_repeats(scenes: list[Scene], images: list[dict[str, Any]]) -> None:
    """Swap an image that would show in two scenes in a row for another, or a text card."""
    for previous, scene in zip(scenes, scenes[1:]):
        if scene.kind == "image" and previous.kind == "image" and scene.image_index == previous.image_index:
            fallback_image(scene, images, [], previous.image_index)


def fallback_image(scene: Scene, images: list[dict[str, Any]], unused: list[int], previous: int | None) -> None:
    """An image not shown yet (else any other than the last), or a text card of the scene's words."""
    pool = [i for i in unused if i != previous] or [i for i in range(len(images)) if i != previous]
    if pool:
        scene.kind, scene.image_index = "image", pool[0]
    else:
        scene.kind, scene.headline = "text", " ".join(scene.text.split()[:6])
