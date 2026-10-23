"""The asset registry: every asset the reel engine made, kept so later reels find it instead of making it again.

``scope`` is ``global`` for generic assets any user's reel may reuse (a sizzle sound, a music bed) and ``user``
for anything made from or for one user's footage (a score composed to their cuts); ``owner_id`` is set for
``user`` assets. ``words`` are the search words; ``made_by`` records how it was made (recipe, model, prompt).
"""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class ReelAsset(Base):
    __tablename__ = "reel_assets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    kind: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    scope: Mapped[str] = mapped_column(String(10), nullable=False, default="global", index=True)
    owner_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    words: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    licence: Mapped[str] = mapped_column(String(200), nullable=False)
    source: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    made_by: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    meta: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    uses: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
