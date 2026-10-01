"""Replace the caption style catalogue: free-text style columns, old ids remapped

The brand kit preset and saved subtitle styles were Postgres enums holding a
handful of long-retired ids, so most styles could not be stored at all. Both
become strings, and every stored id from the old catalogue is moved to its
closest current style (the same table as templates.LEGACY_STYLE_ALIASES, copied
here so this migration never changes when the catalogue does).

Revision ID: 20261001020000
Revises: 20261001010000
Create Date: 2026-10-01 02:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20261001020000"
down_revision: Union[str, None] = "20261001010000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DEFAULT_STYLE = "karaoke"
RETIRED_TO_CURRENT = {
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
# (table, column) holding a caption style id.
STYLE_COLUMNS = (
    ("brand_kits", "default_preset"),
    ("subtitle_styles", "style_type"),
    ("edit_projects", "caption_style"),
)


def _remap(table: str, column: str) -> None:
    for old, new in RETIRED_TO_CURRENT.items():
        op.execute(sa.text(f"UPDATE {table} SET {column} = :new WHERE {column} = :old").bindparams(new=new, old=old))


def upgrade() -> None:
    op.alter_column(
        "brand_kits", "default_preset",
        type_=sa.String(length=50), postgresql_using="default_preset::text",
        server_default=None, existing_nullable=False,
    )
    op.alter_column(
        "subtitle_styles", "style_type",
        type_=sa.String(length=50), postgresql_using="style_type::text", existing_nullable=False,
    )
    op.execute("DROP TYPE IF EXISTS caption_preset")
    op.execute("DROP TYPE IF EXISTS subtitle_style_type")
    op.alter_column("edit_projects", "caption_style", server_default=DEFAULT_STYLE, existing_nullable=False)
    for table, column in STYLE_COLUMNS:
        _remap(table, column)


def downgrade() -> None:
    # The old enums cannot hold the new ids, so the columns stay strings; only
    # the edit default goes back.
    op.alter_column("edit_projects", "caption_style", server_default="hormozi", existing_nullable=False)
