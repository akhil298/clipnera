"""Generate the frontend emoji catalog mirror from the canonical whitelist.

The backend owns the catalog because it is what gates the LLM and what gets
burned in; the frontend needs the same list so the editor's preview shows the
emoji the export will actually contain.

Usage (from backend/):
    python -m subtitle_styling.export_emoji_catalog
"""

from __future__ import annotations

import json
from pathlib import Path

from subtitle_styling.emoji_catalog import CATEGORIES, EMOJI_CATALOG

OUTPUT_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "frontend" / "lib" / "data" / "emojiCatalog.generated.ts"
)


def _ts(value: object) -> str:
    return json.dumps(value, ensure_ascii=False)


def render() -> str:
    lines: list[str] = [
        "// GENERATED FILE - do not edit by hand.",
        "// Mirrors backend/subtitle_styling/emoji_catalog.py, the canonical whitelist.",
        "// Regenerate with: cd backend && python -m subtitle_styling.export_emoji_catalog",
        "",
        "export interface EmojiCatalogEntry {",
        "  slug: string;",
        "  char: string;",
        "  category: EmojiCategory;",
        "  keywords: string[];",
        "}",
        "",
        "export type EmojiCategory =",
    ]
    for index, category in enumerate(CATEGORIES):
        lines.append(f"  | {_ts(category)}{';' if index == len(CATEGORIES) - 1 else ''}")

    lines += [
        "",
        f"export const EMOJI_CATEGORIES: EmojiCategory[] = {_ts(list(CATEGORIES))};",
        "",
        "export const EMOJI_CATALOG: EmojiCatalogEntry[] = [",
    ]
    for entry in EMOJI_CATALOG:
        lines.append(
            "  { slug: %s, char: %s, category: %s, keywords: %s },"
            % (_ts(entry.slug), _ts(entry.char), _ts(entry.category), _ts(list(entry.keywords)))
        )
    lines += [
        "];",
        "",
        "const BY_SLUG = new Map(EMOJI_CATALOG.map((e) => [e.slug, e]));",
        "const BY_KEYWORD = new Map<string, EmojiCatalogEntry>();",
        "for (const entry of EMOJI_CATALOG) {",
        "  for (const keyword of entry.keywords) {",
        "    if (!BY_KEYWORD.has(keyword)) BY_KEYWORD.set(keyword, entry);",
        "  }",
        "}",
        "",
        "export const normalizeEmojiKeyword = (value: string): string =>",
        "  (value || '').toLowerCase().replace(/[^a-z0-9%]+/g, '');",
        "",
        "/** Resolve a catalog slug to its emoji, or null when it is not whitelisted. */",
        "export const emojiForSlug = (slug: string): string | null =>",
        "  BY_SLUG.get(slug)?.char ?? null;",
        "",
        "/** Resolve a spoken word to its emoji, mirroring the backend keyword map. */",
        "export const emojiForKeyword = (word: string): string | null =>",
        "  BY_KEYWORD.get(normalizeEmojiKeyword(word))?.char ?? null;",
        "",
        "export const emojiByCategory = (category: EmojiCategory): EmojiCatalogEntry[] =>",
        "  EMOJI_CATALOG.filter((e) => e.category === category);",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(render(), encoding="utf-8")
    print(f"Wrote {len(EMOJI_CATALOG)} emojis to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
