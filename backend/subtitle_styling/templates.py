"""Canonical caption style definitions.

This is the single source of truth for subtitle styling. The frontend mirrors
these ids in ``lib/utils/captionStyles.ts`` for live preview; any id here must
exist there and vice versa, which is asserted by ``tests/test_caption_templates``.

Font note for Linux/EC2: libass is pointed at ``static/fonts`` (see
``ass_generator.ass_filter``), so the display faces bundled there render the
same on every host; the frontend loads the same families from Google Fonts.
Other names resolve through fontconfig: "DejaVu Sans" and "DejaVu Serif" ship
with virtually every distribution, while Impact, Arial or Georgia fall back to
a default face unless msttcorefonts is installed.
"""

from __future__ import annotations

from typing import Any

AnimationType = (
    "none",
    "karaoke",
    "pop",
    "fade",
)

# Applied under every template, so a template only states what makes it distinct.
TEMPLATE_DEFAULTS: dict[str, Any] = {
    "font_family": "DejaVu Sans",
    "font_size": 32,
    "font_color": "#FFFFFF",
    "highlight_color": "#FFE000",
    "emphasis_color": None,
    "stroke_color": "#000000",
    "stroke_width": 3,
    "background": False,
    "background_color": None,
    "word_box": False,
    "word_box_color": None,
    "animation": "karaoke",
    "word_pop": True,
    "emoji": True,
    "uppercase": False,
    "shadow": True,
    "glow": False,
    "max_words_per_line": 4,
    "position_y": 0.80,
    # The static headline pinned above the captions: size on the same
    # 1080-wide scale as font_size, top margin as a fraction of frame height.
    "title_font_size": 56,
    "title_position_y": 0.07,
}

CAPTION_TEMPLATES: dict[str, dict[str, Any]] = {
    # --- Creator / viral -----------------------------------------------------
    "default": {
        "name": "Default",
        "description": "Punchy word-by-word captions with a pop highlight and emojis",
        "highlight_color": "#FFE000",
        "emphasis_color": "#FFE000",
    },
    "hormozi": {
        "name": "Hormozi",
        "description": "Bold green highlight with a pill behind the active word",
        "font_size": 38,
        "highlight_color": "#00FF66",
        "emphasis_color": "#FFE000",
        "stroke_width": 4,
        "word_box": True,
        "word_box_color": "#00BF49",
        "uppercase": True,
        "max_words_per_line": 3,
        "position_y": 0.74,
    },
    "mrbeast": {
        "name": "MrBeast",
        "description": "Large yellow text with red pop highlights and emojis",
        "font_family": "Impact",
        "font_size": 42,
        "font_color": "#FFFF00",
        "highlight_color": "#FF2D2D",
        "emphasis_color": "#FFFFFF",
        "stroke_width": 5,
        "uppercase": True,
        "max_words_per_line": 3,
        "position_y": 0.70,
    },
    "tiktok": {
        "name": "TikTok",
        "description": "TikTok-style with pink pop highlights",
        "font_size": 34,
        "highlight_color": "#FE2C55",
        "emphasis_color": "#FE2C55",
        "max_words_per_line": 4,
        "position_y": 0.78,
    },
    "impact": {
        "name": "Impact",
        "description": "Oversized all-caps words for maximum stopping power",
        "font_family": "Impact",
        "font_size": 48,
        "highlight_color": "#FFD400",
        "stroke_width": 6,
        "uppercase": True,
        "animation": "pop",
        "max_words_per_line": 2,
        "position_y": 0.68,
    },
    "comic": {
        "name": "Comic Pop",
        "description": "Playful punchy words with a bright outline",
        "font_size": 36,
        "highlight_color": "#FF7A00",
        "emphasis_color": "#00C2FF",
        "stroke_color": "#2B0A3D",
        "stroke_width": 4,
        "animation": "pop",
        "uppercase": True,
        "max_words_per_line": 3,
        "position_y": 0.76,
    },

    # --- Neon / stylised -----------------------------------------------------
    "neon": {
        "name": "Neon",
        "description": "Glowing neon text with magenta highlights",
        "font_size": 36,
        "font_color": "#00FFFF",
        "highlight_color": "#FF00FF",
        "emphasis_color": "#FF00FF",
        "stroke_color": "#002A6B",
        "stroke_width": 2,
        "emoji": False,
        "shadow": False,
        "glow": True,
        "position_y": 0.76,
    },
    "cyberpunk": {
        "name": "Cyberpunk",
        "description": "Hard magenta and cyan contrast with a dark edge",
        "font_size": 36,
        "font_color": "#00F0FF",
        "highlight_color": "#FF2BD1",
        "emphasis_color": "#FFE600",
        "stroke_color": "#12002B",
        "stroke_width": 4,
        "uppercase": True,
        "glow": True,
        "emoji": False,
        "max_words_per_line": 3,
        "position_y": 0.74,
    },
    "sunset": {
        "name": "Sunset",
        "description": "Warm orange and pink tones with a soft shadow",
        "font_size": 34,
        "font_color": "#FFF3E0",
        "highlight_color": "#FF6B35",
        "emphasis_color": "#FF3D77",
        "stroke_color": "#3D1A00",
        "stroke_width": 3,
        "position_y": 0.78,
    },
    "pastel": {
        "name": "Pastel",
        "description": "Soft, low-contrast palette for calm content",
        "font_size": 30,
        "font_color": "#FFF8FB",
        "highlight_color": "#A8D8EA",
        "emphasis_color": "#FFB7B2",
        "stroke_color": "#5B5B6E",
        "stroke_width": 2,
        "animation": "fade",
        "word_pop": False,
        "max_words_per_line": 5,
        "position_y": 0.80,
    },
    "luxury": {
        "name": "Luxury",
        "description": "Gold serif lettering for premium brand content",
        "font_family": "DejaVu Serif",
        "font_size": 32,
        "font_color": "#F5E6C8",
        "highlight_color": "#D4AF37",
        "emphasis_color": "#FFFFFF",
        "stroke_color": "#1A1206",
        "stroke_width": 2,
        "emoji": False,
        "animation": "fade",
        "max_words_per_line": 5,
        "position_y": 0.82,
    },

    # --- Clean / professional ------------------------------------------------
    "minimal": {
        "name": "Minimal",
        "description": "Clean, subtle captions with a soft background",
        "font_size": 26,
        "highlight_color": "#FFFFFF",
        "stroke_color": None,
        "stroke_width": 0,
        "background": True,
        "background_color": "#00000080",
        "animation": "fade",
        "word_pop": False,
        "emoji": False,
        "shadow": False,
        "max_words_per_line": 6,
        "position_y": 0.82,
    },
    "podcast": {
        "name": "Podcast",
        "description": "Professional podcast-style captions",
        "font_size": 28,
        "highlight_color": "#FFB800",
        "emphasis_color": "#FFB800",
        "stroke_color": "#1A1A1A",
        "stroke_width": 2,
        "background": True,
        "background_color": "#1A1A1ACC",
        "word_pop": False,
        "emoji": False,
        "shadow": False,
        "max_words_per_line": 5,
    },
    "news": {
        "name": "News",
        "description": "Broadcast lower-third with a solid plate",
        "font_size": 27,
        "highlight_color": "#FFFFFF",
        "stroke_color": None,
        "stroke_width": 0,
        "background": True,
        "background_color": "#0B2B5BE6",
        "animation": "none",
        "word_pop": False,
        "emoji": False,
        "shadow": False,
        "max_words_per_line": 7,
        "position_y": 0.86,
    },
    "documentary": {
        "name": "Documentary",
        "description": "Understated serif subtitles that stay out of the way",
        "font_family": "DejaVu Serif",
        "font_size": 26,
        "highlight_color": "#FFFFFF",
        "stroke_color": "#000000",
        "stroke_width": 1,
        "animation": "none",
        "word_pop": False,
        "emoji": False,
        "max_words_per_line": 7,
        "position_y": 0.84,
    },
    "bold_captions": {
        "name": "Bold Captions",
        "description": "Heavy white text with a thick outline, readable anywhere",
        "font_size": 34,
        "highlight_color": "#FFFFFF",
        "stroke_width": 5,
        "uppercase": True,
        "emoji": False,
        "max_words_per_line": 4,
        "position_y": 0.80,
    },
    "karaoke_yellow": {
        "name": "Karaoke Yellow",
        "description": "Classic yellow fill that follows the vocal line",
        "font_size": 32,
        "font_color": "#FFFFFF",
        "highlight_color": "#FFE000",
        "emphasis_color": "#FFE000",
        "stroke_width": 3,
        "emoji": False,
        "max_words_per_line": 5,
        "position_y": 0.80,
    },
    "typewriter": {
        "name": "Typewriter",
        "description": "Monospaced text for tech and tutorial content",
        "font_family": "DejaVu Sans Mono",
        "font_size": 24,
        "font_color": "#E0E0E0",
        "highlight_color": "#7CFF6B",
        "stroke_width": 1,
        "animation": "none",
        "word_pop": False,
        "emoji": False,
        "max_words_per_line": 6,
        "position_y": 0.82,
    },

    # --- Compact -------------------------------------------------------------
    "tiny": {
        "name": "Tiny",
        "description": "Small captions that leave the frame clear",
        "font_size": 20,
        "highlight_color": "#FFE000",
        "stroke_width": 2,
        "word_pop": False,
        "emoji": False,
        "max_words_per_line": 7,
        "position_y": 0.86,
    },
    "micro": {
        "name": "Micro",
        "description": "Smallest readable size for dense, information-heavy clips",
        "font_size": 16,
        "highlight_color": "#8AB4FF",
        "stroke_width": 1,
        "animation": "none",
        "word_pop": False,
        "emoji": False,
        "shadow": False,
        "max_words_per_line": 9,
        "position_y": 0.88,
    },

    # --- Font-driven (faces bundled in static/fonts) -------------------------
    "bold_pop": {
        "name": "Bold Pop",
        "description": "Condensed Anton caps with a red box snapping to each word",
        "font_family": "Anton",
        "font_size": 40,
        "highlight_color": "#FFFFFF",
        "emphasis_color": "#FFE000",
        "stroke_width": 4,
        "word_box": True,
        "word_box_color": "#E52222",
        "uppercase": True,
        "animation": "pop",
        "max_words_per_line": 3,
        "position_y": 0.72,
    },
    "headline": {
        "name": "Headline",
        "description": "Tall Bebas Neue lettering with a cyan karaoke sweep",
        "font_family": "Bebas Neue",
        "font_size": 46,
        "highlight_color": "#00E5FF",
        "emphasis_color": "#FFE000",
        "stroke_width": 4,
        "uppercase": True,
        "max_words_per_line": 3,
        "position_y": 0.74,
    },
    "comic_book": {
        "name": "Comic Book",
        "description": "Bangers comic lettering in yellow with red pops",
        "font_family": "Bangers",
        "font_size": 42,
        "font_color": "#FFE600",
        "highlight_color": "#FF3B30",
        "emphasis_color": "#FFFFFF",
        "stroke_width": 5,
        "uppercase": True,
        "animation": "pop",
        "max_words_per_line": 3,
        "position_y": 0.74,
    },
    "marker": {
        "name": "Marker",
        "description": "Hand-drawn Permanent Marker for casual, vlog-style clips",
        "font_family": "Permanent Marker",
        "font_size": 34,
        "highlight_color": "#FF4FA3",
        "emphasis_color": "#FFE000",
        "stroke_width": 3,
        "max_words_per_line": 4,
        "position_y": 0.78,
    },
    "bubble": {
        "name": "Bubble",
        "description": "Chunky rounded Luckiest Guy letters with a purple outline",
        "font_family": "Luckiest Guy",
        "font_size": 38,
        "highlight_color": "#7CFC00",
        "emphasis_color": "#FFD60A",
        "stroke_color": "#3A0CA3",
        "stroke_width": 5,
        "uppercase": True,
        "animation": "pop",
        "max_words_per_line": 3,
        "position_y": 0.74,
    },
    "clean_creator": {
        "name": "Clean Creator",
        "description": "Heavy Archivo Black in sentence case with a green highlight",
        "font_family": "Archivo Black",
        "font_size": 30,
        "highlight_color": "#4ADE80",
        "emphasis_color": "#4ADE80",
        "stroke_width": 2,
        "emoji": False,
        "max_words_per_line": 4,
        "position_y": 0.78,
    },
    "elegant": {
        "name": "Elegant",
        "description": "High-contrast DM Serif Display with a soft gold fade",
        "font_family": "DM Serif Display",
        "font_size": 36,
        "highlight_color": "#F5C542",
        "emphasis_color": "#F5C542",
        "stroke_width": 1,
        "animation": "fade",
        "word_pop": False,
        "emoji": False,
        "max_words_per_line": 5,
        "position_y": 0.80,
    },
}


def get_template(template_name: str) -> dict[str, Any]:
    """Return a fully populated template, falling back to ``default``."""
    template = CAPTION_TEMPLATES.get(template_name)
    if template is None:
        template = CAPTION_TEMPLATES["default"]
    merged: dict[str, Any] = dict(TEMPLATE_DEFAULTS)
    merged.update(template)
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
