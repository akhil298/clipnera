"""Checks on a clip's text as a pair, measured rather than asked of a model.

The titles skill says the burned-in title and the hook line make the same
promise in different words. Models drift from that, so it is checked here:
:func:`repeats` finds the content words the two share (number words count as
their digits, plurals as their singular), and a title that repeats its hook is
written again (see :mod:`content_intelligence.metadata_gen`).
"""

from __future__ import annotations

from motion.moments import tokens

# Two shared content words means the title restates the hook; one can be the topic itself.
MAX_SHARED_WORDS = 1
STOP_WORDS = frozenset("""
a an the and or but so if then than that this these those to of in on at by for with from up down out over into
is are was were be been being am do does did have has had will would can could should may might must just only
very really also too not no yes it its it's i me my we our you your he him his she her they them their what which
who how why when where all any some more most much many one get got gets like about as there here
""".split())


def content_words(text: str) -> set[str]:
    """The words of ``text`` that carry meaning, normalised for comparison."""
    words = set()
    for token in tokens(text):
        if token in STOP_WORDS or (len(token) < 3 and not token.isdigit()):
            continue
        words.add(token[:-1] if len(token) > 3 and token.endswith("s") else token)
    return words


def repeats(title: str, hook: str) -> set[str]:
    """Content words the title shares with the hook line."""
    return content_words(title) & content_words(hook)


def restates(title: str, hook: str | None) -> bool:
    """Whether ``title`` says its hook again instead of pairing with it."""
    return bool(title and hook) and len(repeats(title, hook)) > MAX_SHARED_WORDS
