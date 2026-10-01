from __future__ import annotations

from subtitle_styling.emoji_art import FIRST_LAYER, GHOST, colourize, layers

HEADER = "\n".join([
    "[V4+ Styles]",
    "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
    "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, "
    "MarginR, MarginV, Encoding",
    "Style: Caption,Anton,60,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,3,4,5,54,54,0,1",
    "Style: Box,Anton,60,&HFF000000,&HFF000000,&HFF000000,&HFF000000,0,0,0,0,100,100,0,0,3,8,0,5,54,54,0,1",
    "",
    "[Events]",
])


def _dialogues(ass: str) -> list[str]:
    return [line for line in ass.splitlines() if line.startswith("Dialogue: ")]


def _line(style: str, text: str) -> str:
    return f"{HEADER}\nDialogue: 1,0:00:00.00,0:00:01.00,{style},,0,0,0,,{text}\n"


def test_every_emoji_layer_has_a_colour_and_the_same_square():
    art = layers("😍", 60)
    assert len(art) == 3
    for colour, drawing in art:
        assert colour.startswith("&H") and drawing.startswith("m 0 0 l 1 0 l 0 1 m 240 240")


def test_sequences_and_plain_forms_are_found():
    assert layers("❤️", 60) and layers("👍🏽", 60) and layers("🇮🇳", 60)
    assert layers("a", 60) == ()


def test_a_line_gains_one_hidden_text_copy_per_colour_layer():
    out = _dialogues(colourize(_line("Caption", "{\\c&H00FF00&}MONEY 💰{\\r} IS")))
    assert len(out) == 1 + len(layers("💰", 60))
    assert "💰" not in "".join(out)
    assert [d.split(",")[0] for d in out[1:]] == [f"Dialogue: {FIRST_LAYER + k}" for k in range(len(out) - 1)]
    assert all(",CaptionEmoji," in d for d in out[1:])


def test_the_placeholder_restores_the_alpha_it_hid():
    main = _dialogues(colourize(_line("Caption", "{\\alpha&H80&}WOW 😮 OK")))[0]
    assert "{\\1a&HFF&\\3a&HFF&\\4a&HFF&\\p3}" in main and "\\p0\\1a&H80&\\3a&H80&\\4a&H80&}" in main


def test_upcoming_and_see_through_lines_only_hold_the_space():
    assert len(_dialogues(colourize(_line("Caption", f"SOON {GHOST}🔥")))) == 1
    assert len(_dialogues(colourize(_line("Box", "MONEY 💰")))) == 1


def test_a_second_pass_changes_nothing():
    once = colourize(_line("Caption", "MONEY 💰 and 🫠x"))
    assert colourize(once) == once


def test_text_without_emoji_is_untouched():
    plain = _line("Caption", "no emoji here")
    assert colourize(plain) == plain
