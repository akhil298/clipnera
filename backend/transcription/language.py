"""Language and script handling for multilingual transcripts.

Clipnera's audience speaks English, Hindi, Telugu and the mixes in between
(Hinglish, Tenglish). Whisper writes Hindi and Telugu in their own scripts, and
often writes the English words of a mixed sentence in those scripts too; viewers
of mixed-language shorts read captions in Roman script. This module holds the
pieces every stage shares: sentence ends, language names, script detection,
hesitation sounds, and a rule-based romaniser used when the LLM one fails.
"""

from __future__ import annotations

import re
import unicodedata

# Includes the Devanagari danda, which ends Hindi sentences the way "." ends English ones.
SENTENCE_TERMINALS = (".", "?", "!", "।", "॥")

# Whisper reports languages by name ("english") or code ("en"); the pipeline uses codes.
_LANGUAGE_CODES = {
    "english": "en", "hindi": "hi", "telugu": "te", "tamil": "ta", "kannada": "kn",
    "malayalam": "ml", "marathi": "mr", "bengali": "bn", "gujarati": "gu", "punjabi": "pa",
    "urdu": "ur", "spanish": "es", "french": "fr", "german": "de", "portuguese": "pt",
}


def normalize_language(value: str | None) -> str:
    """ISO 639-1 code for a Whisper language name or code; empty when unknown."""
    text = (value or "").strip().lower()
    if not text:
        return ""
    return _LANGUAGE_CODES.get(text, text if len(text) == 2 else "")


def spoken_hindi_misread_as_urdu(code: str) -> bool:
    """Whisper often labels spoken Hindi as Urdu and writes it in Arabic script.

    Spoken Hindi and Urdu are near identical and Clipnera's viewers read Hindi
    captions in Devanagari or Roman script, so such chunks are re-run as Hindi.
    """
    return code == "ur"


_SCRIPT_RANGES = {
    "devanagari": (0x0900, 0x097F),
    "telugu": (0x0C00, 0x0C7F),
    "arabic": (0x0600, 0x06FF),
}


def script_of(text: str) -> str:
    """The dominant writing system of ``text``: latin, devanagari, telugu, arabic or other."""
    counts: dict[str, int] = {}
    for char in text:
        if not char.isalpha() and not unicodedata.category(char).startswith("M"):
            continue
        code = ord(char)
        name = next((s for s, (lo, hi) in _SCRIPT_RANGES.items() if lo <= code <= hi), None)
        if name is None:
            name = "latin" if code < 0x0250 else "other"
        counts[name] = counts.get(name, 0) + 1
    return max(counts, key=counts.get) if counts else "latin"


def is_indic(text: str) -> bool:
    return script_of(text) in ("devanagari", "telugu")


# Pure hesitation sounds only. Words like "matlab", "basically" or Telugu "ante"
# carry meaning often enough that cutting them would damage sentences.
HESITATIONS = frozenset({
    "um", "uh", "uhm", "umm", "erm", "er", "hmm", "mm", "hm", "uhh", "ahh", "aah",
    "हम्म",  # हम्म
    "ह्म",  # ह्म
    "उम्म",  # उम्म
    "अं",  # अं
    "హ్మ్",  # హ్మ్
    "ఉమ్మ్",  # ఉమ్మ్
})

# Words that open a sentence continuing an earlier thought ("and...", "lekin..."),
# so a clip must not start on them. Hindi and Telugu in both scripts.
CONTINUATION_WORDS = frozenset({
    "and", "but", "so", "because", "or", "which", "then", "also", "plus",
    "aur", "lekin", "par", "toh", "kyunki", "phir", "jo",
    "और", "लेकिन", "तो", "क्योंकि", "फिर",
    "mariyu", "kaani", "anduke",
    "మరియు", "కానీ", "అందుకే",
})

_PUNCTUATION = ".,!?;:\"'।॥"


def is_hesitation(word: str) -> bool:
    return word.strip(_PUNCTUATION).lower() in HESITATIONS


# ---- Rule-based romanisation --------------------------------------------------
# Spellings follow how Hinglish and Tenglish are typed, not a scholarly scheme:
# no diacritics, "ee"/"oo" for long i/u, "sh" for both sibilants.

_DEVANAGARI = {
    "vowels": {"अ": "a", "आ": "aa", "इ": "i", "ई": "ee", "उ": "u", "ऊ": "oo", "ऋ": "ri", "ए": "e",
               "ऐ": "ai", "ओ": "o", "औ": "au", "ऍ": "e", "ऑ": "o"},
    "signs": {"ा": "aa", "ि": "i", "ी": "ee", "ु": "u", "ू": "oo", "ृ": "ri", "े": "e", "ै": "ai",
              "ो": "o", "ौ": "au", "ॅ": "e", "ॉ": "o"},
    "consonants": {"क": "k", "ख": "kh", "ग": "g", "घ": "gh", "ङ": "n", "च": "ch", "छ": "chh", "ज": "j",
                   "झ": "jh", "ञ": "n", "ट": "t", "ठ": "th", "ड": "d", "ढ": "dh", "ण": "n", "त": "t",
                   "थ": "th", "द": "d", "ध": "dh", "न": "n", "प": "p", "फ": "ph", "ब": "b", "भ": "bh",
                   "म": "m", "य": "y", "र": "r", "ल": "l", "ळ": "l", "व": "v", "श": "sh", "ष": "sh",
                   "स": "s", "ह": "h", "क़": "q", "ख़": "kh", "ग़": "g", "ज़": "z", "ड़": "d", "ढ़": "rh",
                   "फ़": "f", "य़": "y"},
    "virama": "्", "nasals": {"ं", "ँ"}, "visarga": "ः", "nukta": "़",
    "drop_final_a": True, "final_nasal": "n",
}

_TELUGU = {
    "vowels": {"అ": "a", "ఆ": "aa", "ఇ": "i", "ఈ": "ee", "ఉ": "u", "ఊ": "oo", "ఋ": "ru", "ఎ": "e",
               "ఏ": "e", "ఐ": "ai", "ఒ": "o", "ఓ": "o", "ఔ": "au"},
    "signs": {"ా": "aa", "ి": "i", "ీ": "ee", "ు": "u", "ూ": "oo", "ృ": "ru", "ె": "e", "ే": "e",
              "ై": "ai", "ొ": "o", "ో": "o", "ౌ": "au"},
    "consonants": {"క": "k", "ఖ": "kh", "గ": "g", "ఘ": "gh", "ఙ": "n", "చ": "ch", "ఛ": "chh", "జ": "j",
                   "ఝ": "jh", "ఞ": "n", "ట": "t", "ఠ": "th", "డ": "d", "ఢ": "dh", "ణ": "n", "త": "t",
                   "థ": "th", "ద": "d", "ధ": "dh", "న": "n", "ప": "p", "ఫ": "ph", "బ": "b", "భ": "bh",
                   "మ": "m", "య": "y", "ర": "r", "ఱ": "r", "ల": "l", "ళ": "l", "వ": "v", "శ": "sh",
                   "ష": "sh", "స": "s", "హ": "h"},
    "virama": "్", "nasals": {"ం", "ఁ"}, "visarga": "ః", "nukta": "",
    "drop_final_a": False, "final_nasal": "m",
}

_LABIALS = {"p", "ph", "b", "bh", "m"}


def _table_for(word: str) -> dict | None:
    script = script_of(word)
    return _DEVANAGARI if script == "devanagari" else _TELUGU if script == "telugu" else None


def _tokens(word: str, table: dict) -> list[tuple[str, str]]:
    """(kind, roman) per unit; a consonant followed by a nukta is one unit."""
    units: list[tuple[str, str]] = []
    chars = unicodedata.normalize("NFD", word) if table["nukta"] else word
    i = 0
    while i < len(chars):
        char = chars[i]
        pair = chars[i:i + 2]
        if table["nukta"] and len(pair) == 2 and pair[1] == table["nukta"] and pair in table["consonants"]:
            units.append(("C", table["consonants"][pair]))
            i += 2
            continue
        if char in table["consonants"]:
            units.append(("C", table["consonants"][char]))
        elif char in table["signs"]:
            units.append(("V", table["signs"][char]))
        elif char in table["vowels"]:
            units.append(("I", table["vowels"][char]))
        elif char == table["virama"]:
            units.append(("X", ""))
        elif char in table["nasals"]:
            units.append(("N", ""))
        elif char == table["visarga"]:
            units.append(("H", "h"))
        elif char != table["nukta"]:
            units.append(("O", char))
        i += 1
    return units


def romanize_word(word: str) -> str:
    """Roman-script spelling of one Hindi or Telugu word; other words are returned unchanged."""
    table = _table_for(word)
    if table is None:
        return word
    units = _tokens(word, table)
    out: list[str] = []
    for index, (kind, roman) in enumerate(units):
        following = units[index + 1] if index + 1 < len(units) else None
        if kind == "C":
            out.append(roman)
            # The inherent vowel sounds unless a sign or virama follows.
            if following is None or following[0] not in ("V", "X"):
                is_final = following is None or following[0] == "O"
                if not (is_final and table["drop_final_a"] and len(out) > 1):
                    out.append("a")
        elif kind == "N":
            if following and following[0] == "C":
                out.append("m" if following[1] in _LABIALS else "n")
            else:
                out.append(table["final_nasal"])
        else:
            out.append(roman)
    text = "".join(out)
    if table is _DEVANAGARI:
        # Hinglish shortens word-final long vowels: "kya", "bhi", "tu".
        text = re.sub(r"aa$", "a", text)
        text = re.sub(r"ee$", "i", text)
        text = re.sub(r"oo$", "u", text)
    return text
