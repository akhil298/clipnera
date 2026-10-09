import { apiFetch } from '@/lib/api/client';

import type { BrandKit, BrandKitResponse, CreateBrandKitRequest } from './types';

/** One brand kit per user (L-D6). `GET /brand-kits` and `DELETE /brand-kits/{id}` are not used. */

function fromResponse(kit: BrandKitResponse): BrandKit {
  return {
    id: kit.id,
    brand_name: kit.brandName,
    logo_url: kit.logoUrl,
    logo_position: kit.logoPosition,
    logo_opacity: kit.logoOpacity,
    logo_size: kit.logoSize,
    primary_color: kit.primaryColor,
    secondary_color: kit.secondaryColor,
    preferred_font: kit.preferredFont,
    default_preset: kit.defaultPreset,
    auto_emojis: kit.autoEmojis,
    outro_cta_text: kit.outroCtaText,
    is_customized: kit.isCustomized,
    updated_at: kit.updatedAt,
  };
}

/** The request body for a kit: only the fields `CreateBrandKitRequest` takes. */
export function toRequest(kit: CreateBrandKitRequest): CreateBrandKitRequest {
  return {
    brand_name: kit.brand_name.trim(),
    logo_url: kit.logo_url,
    logo_position: kit.logo_position,
    logo_opacity: Math.round(kit.logo_opacity),
    logo_size: Math.round(kit.logo_size),
    primary_color: kit.primary_color,
    secondary_color: kit.secondary_color,
    preferred_font: kit.preferred_font,
    default_preset: kit.default_preset,
    auto_emojis: kit.auto_emojis,
    outro_cta_text: kit.outro_cta_text,
  };
}

/** `GET /brand-kits/me`: the caller's kit; the server creates the default one on first read. */
export const getBrandKit = async (signal?: AbortSignal) => fromResponse(await apiFetch<BrandKitResponse>('/brand-kits/me', { signal }));

/** `POST /brand-kits`: creates or replaces the caller's kit. Pro only (`brand_kit_edit`); Free gets a plan error. */
export const saveBrandKit = async (kit: CreateBrandKitRequest) =>
  fromResponse(await apiFetch<BrandKitResponse>('/brand-kits', { method: 'POST', body: toRequest(kit) }));
