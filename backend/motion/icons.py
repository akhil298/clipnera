"""Icons for list items, matched to the words said, never guessed.

An item gets an icon only when one of its words names the thing the icon
draws ("wings" -> chicken leg). Anything else gets none: an empty slot reads
as clean, a wrong picture reads as a mistake.
"""

from __future__ import annotations

import re

# emoji -> words that name what it shows (singular; plurals match too).
ICON_WORDS: dict[str, tuple[str, ...]] = {
    "🍗": ("chicken", "wing", "drumstick", "tender", "nugget"),
    "🍔": ("burger", "hamburger", "cheeseburger", "whopper"),
    "🍟": ("fry", "fries", "chips"),
    "🍕": ("pizza",),
    "🌮": ("taco",),
    "🌯": ("burrito", "wrap"),
    "🥤": ("soda", "coke", "pepsi", "sprite", "drink", "shake", "milkshake"),
    "☕": ("coffee", "latte", "espresso", "tea"),
    "🍦": ("ice cream", "icecream", "sundae"),
    "🍩": ("donut", "doughnut"),
    "🍪": ("cookie", "biscuit"),
    "🎂": ("cake", "birthday"),
    "🥒": ("pickle", "cucumber"),
    "🧀": ("cheese",),
    "🥚": ("egg",),
    "🍞": ("bread", "toast"),
    "🍚": ("rice", "biryani"),
    "🍜": ("noodle", "ramen", "maggi"),
    "🥗": ("salad",),
    "🍎": ("apple",),
    "🍌": ("banana",),
    "🍉": ("watermelon",),
    "🥩": ("steak", "meat", "beef"),
    "🐟": ("fish",),
    "🍫": ("chocolate",),
    "💧": ("water",),
    "💰": ("money", "cash", "dollar", "rupee", "profit", "salary", "income", "revenue"),
    "💳": ("card", "credit"),
    "📈": ("growth", "grow", "increase", "investment", "invest", "stock", "stocks"),
    "🏠": ("house", "home", "apartment", "flat", "property"),
    "🚗": ("car",),
    "✈️": ("flight", "plane", "travel", "airport"),
    "📱": ("phone", "iphone", "mobile", "app"),
    "💻": ("laptop", "computer", "pc", "coding", "code"),
    "🎮": ("game", "gaming", "console", "controller", "playstation", "xbox"),
    "⚽": ("football", "soccer"),
    "🏀": ("basketball",),
    "🏏": ("cricket",),
    "🏋️": ("gym", "workout", "lift", "lifting", "weight"),
    "🏃": ("running", "cardio", "jog", "jogging"),
    "😴": ("sleep", "sleeping", "nap"),
    "📚": ("book", "books", "study", "studying", "reading"),
    "🎓": ("college", "degree", "university", "graduate"),
    "💼": ("job", "work", "office", "business", "career"),
    "🎵": ("music", "song", "songs"),
    "🎤": ("mic", "sing", "singing", "rap"),
    "🎨": ("art", "drawing", "draw", "paint", "painting"),
    "📸": ("photo", "picture", "camera"),
    "🎥": ("video", "videos", "film", "movie"),
    "👕": ("shirt", "tshirt", "hoodie", "jersey", "clothes", "outfit"),
    "👟": ("shoe", "shoes", "sneaker", "sneakers"),
    "⌚": ("watch",),
    "💍": ("ring", "wedding"),
    "❤️": ("love",),
    "🐶": ("dog", "puppy"),
    "🐱": ("cat", "kitten"),
    "⏰": ("alarm", "morning", "wake"),
    "🔥": ("fire", "hot", "spicy"),
    "🧠": ("brain", "mind"),
    "💡": ("idea", "ideas"),
    "📝": ("note", "notes", "list", "plan"),
    "🎁": ("gift", "present"),
    "🛒": ("shopping", "grocery", "groceries"),
}

_TOKEN = re.compile(r"[a-z]+")


def _forms(word: str) -> set[str]:
    forms = {word}
    for suffix in ("es", "s"):
        if word.endswith(suffix) and len(word) > len(suffix) + 2:
            forms.add(word[: -len(suffix)])
    return forms


_LOOKUP: dict[str, str] = {
    name: emoji for emoji, names in ICON_WORDS.items() for name in names if " " not in name
}
_PHRASES: dict[str, str] = {
    name: emoji for emoji, names in ICON_WORDS.items() for name in names if " " in name
}


def icon_for(text: str) -> str:
    """The icon one of ``text``'s words names, or ``""``."""
    lowered = text.lower()
    for phrase, emoji in _PHRASES.items():
        if phrase in lowered:
            return emoji
    for token in _TOKEN.findall(lowered):
        for form in _forms(token):
            if form in _LOOKUP:
                return _LOOKUP[form]
    return ""
