from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import String, ForeignKey, DateTime, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class SubtitleStyleType:
    """Resolves caption style ids against the canonical template list.

    Retired ids map to their closest current style through
    ``templates.LEGACY_STYLE_ALIASES``; anything else becomes the default.
    """

    @staticmethod
    def is_template(style_type: str) -> bool:
        from subtitle_styling.templates import has_template

        return has_template(SubtitleStyleType.to_template(style_type))

    @staticmethod
    def to_template(style_type: str) -> str:
        from subtitle_styling.templates import resolve_style_id

        return resolve_style_id(style_type)

    @staticmethod
    def values() -> list[str]:
        from subtitle_styling.templates import get_template_names

        return get_template_names()


class SubtitleStyle(Base):
    __tablename__ = "subtitle_styles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    style_type: Mapped[str] = mapped_column(String(50), nullable=False)
    config: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_preset: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
