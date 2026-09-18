"""Generate the frontend caption style mirror from the canonical templates.

The backend owns the style list; the frontend needs the same definitions to
render live previews without a round trip. Generating one from the other keeps
the two in step — they previously drifted to the point where six of the ten
styles the UI offered had no backend template and silently burned as Default.

Usage (from backend/):
    python -m subtitle_styling.export_styles
"""

from __future__ import annotations

import json
from pathlib import Path

from subtitle_styling.templates import CAPTION_TEMPLATES, get_template

OUTPUT_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "frontend" / "lib" / "utils" / "captionStyles.generated.ts"
)

# CaptionConfig.animation in the frontend accepts a wider set than the templates
# use; anything unmapped falls back to the karaoke reveal.
ANIMATIONS = {"karaoke", "pop", "fade", "bounce", "none"}


def _badge(template: dict) -> str:
    if template["glow"]:
        return "Neon"
    if template["font_size"] >= 40:
        return "High CTR"
    if template["font_size"] <= 20:
        return "Compact"
    if template["background"]:
        return "Clean"
    return "Popular"


def _ts(value: object) -> str:
    """Render a Python value as a TypeScript literal."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    return json.dumps(value, ensure_ascii=False)


def render() -> str:
    ids = list(CAPTION_TEMPLATES)
    lines: list[str] = [
        "// GENERATED FILE - do not edit by hand.",
        "// Mirrors backend/subtitle_styling/templates.py, the canonical style list.",
        "// Regenerate with: cd backend && python -m subtitle_styling.export_styles",
        "",
        "import { CaptionConfig } from '@/lib/types';",
        "",
        "export type CaptionPreset =",
    ]
    for index, name in enumerate(ids):
        lines.append(f"  | {_ts(name)}{';' if index == len(ids) - 1 else ''}")
    lines += [
        "",
        "export interface CaptionStyle {",
        "  id: CaptionPreset;",
        "  name: string;",
        "  brandName: string;",
        "  description: string;",
        "  badge: string;",
        "  config: CaptionConfig;",
        "}",
        "",
        "export const captionStyles: Record<CaptionPreset, CaptionStyle> = {",
    ]

    for name in ids:
        template = get_template(name)
        animation = template["animation"] if template["animation"] in ANIMATIONS else "karaoke"
        lines += [
            f"  {name}: {{",
            f"    id: {_ts(name)},",
            f"    name: {_ts(template['name'])},",
            f"    brandName: {_ts(template['name'].upper())},",
            f"    description: {_ts(template['description'])},",
            f"    badge: {_ts(_badge(template))},",
            "    config: {",
            f"      preset: {_ts(name)},",
            f"      fontSize: {_ts(template['font_size'])},",
            f"      fontFamily: {_ts(template['font_family'])},",
            f"      textColor: {_ts(template['font_color'])},",
            f"      highlightColor: {_ts(template['highlight_color'])},",
            f"      secondaryHighlightColor: {_ts(template['emphasis_color'] or template['highlight_color'])},",
            f"      hasBgBox: {_ts(bool(template['background']))},",
            f"      bgBoxColor: {_ts(template['background_color'] or 'rgba(0,0,0,0.85)')},",
            f"      uppercase: {_ts(bool(template['uppercase']))},",
            f"      animation: {_ts(animation)},",
            "      animationSpeed: 1.0,",
            f"      positionY: {_ts(round(template['position_y'] * 100))},",
            f"      emojisEnabled: {_ts(bool(template['emoji']))},",
            f"      maxWordsPerLine: {_ts(template['max_words_per_line'])},",
            f"      shadowIntensity: {_ts(0.8 if template['shadow'] else 0.0)},",
            "    },",
            "  },",
        ]

    lines += ["};", ""]
    return "\n".join(lines)


def main() -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(render(), encoding="utf-8")
    print(f"Wrote {len(CAPTION_TEMPLATES)} styles to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
