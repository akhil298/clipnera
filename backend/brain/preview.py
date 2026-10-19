"""What the server render will draw over the picture, for the studio's preview to match it.

It comes from the renderer's own compiled timeline (brain.render_adapter.to_reel), so the
preview and the export can't disagree about which caption words show, where titles sit or
when sounds land.
"""

from __future__ import annotations

from collections.abc import Mapping

from brain.render_adapter import to_reel
from brain.schema import CaptionLook, CaptionStyleOption, PreviewSound, PreviewText, PreviewWord, ProjectPreview
from editor.timeline import Timeline
from subtitle_styling.templates import get_template, get_template_info, resolve_style_id
from understanding.mud import MUD


def caption_look(style: str) -> CaptionLook:
    template = get_template(resolve_style_id(style))
    return CaptionLook.model_validate({key: template.get(key) for key in CaptionLook.model_fields})


def caption_styles() -> list[CaptionStyleOption]:
    """Every caption style, in the catalogue's order."""
    return [CaptionStyleOption(id=item["id"], name=item["name"], description=item["description"], look=caption_look(item["id"]))
            for item in get_template_info()]


def preview(timeline: Timeline, muds: Mapping[str, MUD], version: int) -> ProjectPreview:
    compiled, _ = to_reel(timeline, muds)
    style = compiled["caption_style"] if timeline.captions and timeline.captions.enabled else None
    return ProjectPreview(
        version=version,
        look=compiled["look"],
        caption_style=style,
        caption_look=caption_look(style) if style else None,
        words=[PreviewWord(**w) for w in compiled["words"]],
        texts=[PreviewText(**t) for t in compiled["texts"]],
        sounds=[PreviewSound(name=s["name"], at=s["at"], gain_db=s["gain_db"]) for s in compiled["sfx"]],
    )
