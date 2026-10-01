"""Canonical caption style definitions.

This is the single source of truth for subtitle styling. The frontend mirrors
these ids in ``lib/utils/captionStyles.generated.ts`` for live preview; any id
here must exist there and vice versa, which is asserted by
``tests/test_caption_style_parity``.

Every face a template names is bundled in ``static/fonts`` under the SIL Open
Font License or Apache 2.0, with its license beside it, and the frontend serves
the same files, so previews and burns use identical glyphs. Style names are
descriptive and original: none names a creator, channel or brand.
"""

from __future__ import annotations

from typing import Any

# New clips, unknown ids and the fallback for retired ones use this style.
DEFAULT_STYLE = "karaoke"

# Applied under every template, so a template only states what makes it distinct.
TEMPLATE_DEFAULTS: dict[str, Any] = {
    "font_family": "Poppins Black",
    "font_size": 68,
    "font_color": "#FFFFFF",
    "highlight_color": "#FFFFFF",
    "emphasis_color": None,
    "stroke_color": "#000000",
    "stroke_width": 4,
    "italic": False,
    # A plate behind the whole line.
    "background": False,
    "background_color": None,
    # A box behind the spoken word only.
    "word_box": False,
    "word_box_color": None,
    # Words not yet spoken: a dimmer colour, or hidden until they are said.
    "upcoming_color": None,
    "hide_upcoming": False,
    # Two stacked rows; the second can take its own colour and size.
    "rows": 1,
    "second_line_color": None,
    "second_line_scale": 1.0,
    "animation": "pop",
    # Size of the spoken word relative to the others, for pop-style motions.
    "active_scale": 1.1,
    "word_pop": True,
    "emoji": False,
    "uppercase": True,
    "shadow": True,
    "glow": False,
    "max_words_per_line": 3,
    "position_y": 0.76,
    # The static headline pinned above the captions: size on the same
    # 1080-wide scale as font_size, top margin as a fraction of frame height.
    "title_font_size": 52,
    "title_position_y": 0.07,
}

CAPTION_TEMPLATES: dict[str, dict[str, Any]] = {
    # --- Word highlight ------------------------------------------------------
    "karaoke": {
        "name": "Karaoke",
        "description": "Wide heavy white caps, one short line at a time; the spoken word lights up green, key words yellow",
        "font_family": "Montserrat ExtraBold",
        "highlight_color": "#7CF25A",
        "emphasis_color": "#FFE100",
        "animation": "karaoke",
    },
    "simple": {
        "name": "Simple",
        "description": "Tall condensed white caps with a hard outline, nothing else",
        "font_family": "Anton",
        "font_size": 67,
        "animation": "fade",
        "max_words_per_line": 2,
    },
    "punch": {
        "name": "Punch",
        "description": "Compact italic cartoon caps that punch in word by word",
        "font_family": "Luckiest Guy",
        "font_size": 60,
        "italic": True,
        "active_scale": 1.18,
        "emoji": True,
    },
    "spotlight": {
        "name": "Spotlight",
        "description": "Clean caps where the spoken word glows teal and the rest wait in grey",
        "font_family": "Roboto",
        "font_size": 64,
        "highlight_color": "#5EEAD4",
        "emphasis_color": "#5EEAD4",
        "upcoming_color": "#A3A3A3",
        "stroke_width": 2,
        "animation": "karaoke",
        "max_words_per_line": 4,
    },
    "hot_pink": {
        "name": "Hot Pink",
        "description": "Condensed magenta caps with a dark outline",
        "font_family": "Anton",
        "font_size": 67,
        "font_color": "#F25CD4",
        "highlight_color": "#F25CD4",
        "stroke_color": "#1F0019",
        "active_scale": 1.15,
        "max_words_per_line": 2,
    },
    "reveal": {
        "name": "Reveal",
        "description": "Words darken on a light card as they are spoken",
        "font_family": "Anton",
        "font_size": 67,
        "font_color": "#1C1C1C",
        "highlight_color": "#1C1C1C",
        "upcoming_color": "#A3A3A3",
        "stroke_color": None,
        "stroke_width": 0,
        "background": True,
        "background_color": "#EDEDEDFF",
        "animation": "karaoke",
        "uppercase": False,
        "shadow": False,
    },
    "lime_stack": {
        "name": "Lime Stack",
        "description": "Two rows of heavy caps, white over lime green",
        "highlight_color": "#5BE24A",
        "emphasis_color": "#5BE24A",
        "second_line_color": "#5BE24A",
        "rows": 2,
        "emoji": True,
    },
    "purple_pop": {
        "name": "Purple Pop",
        "description": "The spoken word grows on a purple highlighter stripe",
        "font_size": 64,
        "word_box": True,
        "word_box_color": "#8B3DFF",
        "active_scale": 1.25,
        "rows": 2,
    },
    "gold_stack": {
        "name": "Gold Stack",
        "description": "Condensed caps on two rows, white over gold",
        "font_family": "Anton",
        "font_size": 67,
        "highlight_color": "#FFE100",
        "emphasis_color": "#FFE100",
        "second_line_color": "#FFE100",
        "rows": 2,
    },
    "candy": {
        "name": "Candy",
        "description": "Bubbly pink caps with a white outline",
        "font_size": 76,
        "font_color": "#FF2E97",
        "highlight_color": "#FF2E97",
        "stroke_color": "#FFFFFF",
        "active_scale": 1.18,
        "rows": 2,
        "emoji": True,
    },
    "backdrop": {
        "name": "Backdrop",
        "description": "Bold italic yellow on a dark band that keeps any frame readable",
        "font_size": 60,
        "font_color": "#FFF04D",
        "highlight_color": "#FFFFFF",
        "stroke_color": None,
        "stroke_width": 0,
        "italic": True,
        "background": True,
        "background_color": "#101010CC",
        "animation": "karaoke",
        "uppercase": False,
        "shadow": False,
        "rows": 2,
        "max_words_per_line": 4,
    },
    "typewriter": {
        "name": "Typewriter",
        "description": "Typewriter caps: a small white lead-in over a big yellow word",
        "font_family": "Courier Prime",
        "font_size": 52,
        "highlight_color": "#FFE45C",
        "second_line_color": "#FFE45C",
        "second_line_scale": 1.6,
        "stroke_width": 3,
        "rows": 2,
    },
    "highlighter": {
        "name": "Highlighter",
        "description": "Condensed pink words; the spoken one turns blue on a pink box",
        "font_family": "Anton",
        "font_size": 67,
        "font_color": "#F9A8D4",
        "highlight_color": "#2438C9",
        "stroke_color": "#FFFFFF",
        "stroke_width": 2,
        "word_box": True,
        "word_box_color": "#F472B6",
        "uppercase": False,
        "max_words_per_line": 2,
    },

    # --- Motion --------------------------------------------------------------
    "soft_rise": {
        "name": "Soft Rise",
        "description": "Sentence-case lines settle in gently; the spoken word turns cyan",
        "font_family": "Roboto",
        "font_size": 68,
        "highlight_color": "#7DF9FF",
        "emphasis_color": "#7DF9FF",
        "stroke_width": 2,
        "animation": "land",
        "uppercase": False,
    },
    "tremor": {
        "name": "Tremor",
        "description": "Big serif words that shake as they are spoken, in gold",
        "font_family": "DM Serif Display",
        "font_size": 87,
        "highlight_color": "#E8C07A",
        "emphasis_color": "#E8C07A",
        "second_line_color": "#E8C07A",
        "stroke_width": 2,
        "animation": "shake",
        "uppercase": False,
        "rows": 2,
    },
    "pulse": {
        "name": "Pulse",
        "description": "Chunky caps where the spoken word breathes in green",
        "font_size": 76,
        "highlight_color": "#4BE84B",
        "emphasis_color": "#4BE84B",
        "stroke_width": 5,
        "animation": "breathe",
        "active_scale": 1.15,
        "rows": 2,
    },
    "bounce": {
        "name": "Bounce",
        "description": "Rounded words wrapped in a thick green outline that bounce in",
        "font_size": 72,
        "highlight_color": "#D4FF3A",
        "stroke_color": "#2E7D32",
        "stroke_width": 8,
        "animation": "bounce",
        "uppercase": False,
        "shadow": False,
        "emoji": True,
    },
    "blur_swap": {
        "name": "Blur Swap",
        "description": "Each line sharpens out of a blur; the spoken word turns cyan",
        "font_size": 76,
        "highlight_color": "#7EE8FA",
        "emphasis_color": "#7EE8FA",
        "animation": "blur",
    },
    "grow": {
        "name": "Grow",
        "description": "Caps with a violet glow; the spoken word grows",
        "font_size": 76,
        "stroke_color": "#7C3AED",
        "stroke_width": 3,
        "glow": True,
        "animation": "grow",
        "active_scale": 1.3,
        "shadow": False,
    },
    "glitch": {
        "name": "Glitch",
        "description": "Orange condensed caps with a red edge that glitch on each word",
        "font_family": "Anton",
        "font_size": 67,
        "font_color": "#FFB020",
        "highlight_color": "#FFE45C",
        "emphasis_color": "#FFE45C",
        "stroke_color": "#E3262B",
        "animation": "glitch",
        "max_words_per_line": 2,
    },
    "blur_in": {
        "name": "Blur In",
        "description": "Serif words blur into view as they are spoken, white over violet",
        "font_family": "DM Serif Display",
        "font_size": 80,
        "second_line_color": "#E879F9",
        "stroke_color": "#2A0A3A",
        "stroke_width": 3,
        "hide_upcoming": True,
        "animation": "blur",
        "uppercase": False,
        "rows": 2,
    },
}

# Style ids retired from the catalogue, mapped to the closest current style so
# rows, saved editor settings and API calls made before a change still burn a
# sensible look instead of failing or silently changing to the default.
LEGACY_STYLE_ALIASES: dict[str, str] = {
    "default": "karaoke",
    "hormozi": "lime_stack",
    "mrbeast": "punch",
    "tiktok": "hot_pink",
    "impact": "simple",
    "comic": "candy",
    "neon": "grow",
    "cyberpunk": "glitch",
    "sunset": "gold_stack",
    "pastel": "soft_rise",
    "luxury": "blur_in",
    "clean_dark": "backdrop",
    "minimal": "spotlight",
    "podcast": "reveal",
    "news": "backdrop",
    "documentary": "blur_in",
    "bold_captions": "simple",
    "karaoke_yellow": "gold_stack",
    "tiny": "spotlight",
    "micro": "spotlight",
    "bold_pop": "highlighter",
    "headline": "simple",
    "comic_book": "punch",
    "marker": "candy",
    "bubble": "bounce",
    "clean_creator": "spotlight",
    "elegant": "blur_in",
    "boxed": "highlighter",
}


def resolve_style_id(style_id: str | None) -> str:
    """A current template id for ``style_id``: itself, its replacement, or the default."""
    if style_id in CAPTION_TEMPLATES:
        return style_id
    return LEGACY_STYLE_ALIASES.get(style_id or "", DEFAULT_STYLE)


def get_template(template_name: str | None) -> dict[str, Any]:
    """Return a fully populated template; retired and unknown ids resolve first."""
    merged: dict[str, Any] = dict(TEMPLATE_DEFAULTS)
    merged.update(CAPTION_TEMPLATES[resolve_style_id(template_name)])
    return merged


def has_template(template_name: str) -> bool:
    return template_name in CAPTION_TEMPLATES


def get_all_templates() -> dict[str, dict[str, Any]]:
    return {name: get_template(name) for name in CAPTION_TEMPLATES}


def get_template_names() -> list[str]:
    return list(CAPTION_TEMPLATES.keys())


def get_template_info() -> list[dict[str, Any]]:
    """Summary of every style, for the picker UI."""
    info = []
    for name in CAPTION_TEMPLATES:
        template = get_template(name)
        info.append({
            "id": name,
            "name": template["name"],
            "description": template["description"],
            "animation": template["animation"],
            "font_family": template["font_family"],
            "font_size": template["font_size"],
            "font_color": template["font_color"],
            "highlight_color": template["highlight_color"],
            "uppercase": template["uppercase"],
            "emoji": template["emoji"],
        })
    return info
