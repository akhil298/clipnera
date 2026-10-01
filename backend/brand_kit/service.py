from __future__ import annotations

from brand_kit.model import LogoPosition
from brand_kit.repository import BrandKitRepository
from brand_kit.schema import CreateBrandKitRequest, BrandKitResponse
from subtitle_styling.templates import DEFAULT_STYLE, resolve_style_id

# What a user's kit holds until they save their own.
DEFAULT_BRAND_KIT = {
    "brand_name": "My Brand",
    "logo_url": None,
    "logo_position": LogoPosition.TOP_RIGHT,
    "logo_opacity": 85,
    "logo_size": 28,
    "primary_color": "#f59e0b",
    "secondary_color": "#f43f5e",
    "preferred_font": "Syne",
    "default_preset": DEFAULT_STYLE,
    "auto_emojis": True,
    "outro_cta_text": "",
}


class BrandKitService:
    """Business logic for brand kits."""

    def __init__(self, repository: BrandKitRepository) -> None:
        self._repository = repository

    async def get_brand_kit(self, user_id: str) -> BrandKitResponse:
        brand_kit = await self._repository.get_by_user_id(user_id)
        if not brand_kit:
            brand_kit = await self._repository.create(user_id=user_id, **DEFAULT_BRAND_KIT)
        return self._to_response(brand_kit)

    async def create_or_update_brand_kit(self, user_id: str, data: CreateBrandKitRequest) -> BrandKitResponse:
        existing = await self._repository.get_by_user_id(user_id)
        if existing:
            updated = await self._repository.update(
                existing,
                brand_name=data.brand_name,
                logo_url=data.logo_url,
                logo_position=LogoPosition(data.logo_position),
                logo_opacity=data.logo_opacity,
                logo_size=data.logo_size,
                primary_color=data.primary_color,
                secondary_color=data.secondary_color,
                preferred_font=data.preferred_font,
                default_preset=resolve_style_id(data.default_preset),
                auto_emojis=data.auto_emojis,
                outro_cta_text=data.outro_cta_text,
            )
            return self._to_response(updated)

        created = await self._repository.create(
            user_id=user_id,
            brand_name=data.brand_name,
            logo_url=data.logo_url,
            logo_position=LogoPosition(data.logo_position),
            logo_opacity=data.logo_opacity,
            logo_size=data.logo_size,
            primary_color=data.primary_color,
            secondary_color=data.secondary_color,
            preferred_font=data.preferred_font,
            default_preset=resolve_style_id(data.default_preset),
            auto_emojis=data.auto_emojis,
            outro_cta_text=data.outro_cta_text,
        )
        return self._to_response(created)

    async def delete_brand_kit(self, user_id: str, brand_kit_id: str) -> None:
        brand_kit = await self._repository.get_by_id(brand_kit_id, user_id)
        if not brand_kit:
            from core.exceptions import CustomException
            raise CustomException(message="Brand kit not found", code="NOT_FOUND", status_code=404)
        await self._repository.delete(brand_kit)

    async def list_brand_kits(self, user_id: str) -> list[BrandKitResponse]:
        brand_kits = await self._repository.list_for_user(user_id)
        return [self._to_response(bk) for bk in brand_kits]

    @staticmethod
    def _to_response(brand_kit) -> BrandKitResponse:
        return BrandKitResponse(
            id=brand_kit.id,
            userId=brand_kit.user_id,
            brandName=brand_kit.brand_name,
            logoUrl=brand_kit.logo_url,
            logoPosition=brand_kit.logo_position.value,
            logoOpacity=brand_kit.logo_opacity,
            logoSize=brand_kit.logo_size,
            primaryColor=brand_kit.primary_color,
            secondaryColor=brand_kit.secondary_color,
            preferredFont=brand_kit.preferred_font,
            defaultPreset=resolve_style_id(brand_kit.default_preset),
            autoEmojis=brand_kit.auto_emojis,
            outroCtaText=brand_kit.outro_cta_text,
            isCustomized=any(getattr(brand_kit, key) != value for key, value in DEFAULT_BRAND_KIT.items()),
            createdAt=brand_kit.created_at.isoformat(),
            updatedAt=brand_kit.updated_at.isoformat(),
        )
