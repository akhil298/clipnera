/**
 * Brand kit types. Wire types mirror backend/brand_kit/schema.py exactly; keep them in step.
 * `BrandKitResponse` is still camelCase on the wire (L-API-12b asks for snake_case), so
 * kit.ts maps it to `BrandKit`, the snake_case shape the v2 screens use.
 */

/** backend/brand_kit/model.py LogoPosition. */
export type LogoPosition = 'top_left' | 'top_right' | 'bottom_left' | 'bottom_right';

/** `BrandKitResponse` as sent by `GET /brand-kits/me` and `POST /brand-kits` (bare body, camelCase). */
export interface BrandKitResponse {
  id: string;
  userId: string;
  brandName: string;
  logoUrl: string | null;
  logoPosition: LogoPosition;
  logoOpacity: number;
  logoSize: number;
  primaryColor: string;
  secondaryColor: string;
  preferredFont: string;
  defaultPreset: string;
  autoEmojis: boolean;
  outroCtaText: string;
  /** False while the kit still holds the defaults it was auto-created with. */
  isCustomized: boolean;
  createdAt: string;
  updatedAt: string;
}

/** `CreateBrandKitRequest` (`POST /brand-kits`, Pro `brand_kit_edit`). Limits are the schema's. */
export interface CreateBrandKitRequest {
  /** 1–255 characters. */
  brand_name: string;
  logo_url: string | null;
  logo_position: LogoPosition;
  /** Integer, 20–100. */
  logo_opacity: number;
  /** Integer, 18–48. */
  logo_size: number;
  /** `#rrggbb`, exactly 7 characters. */
  primary_color: string;
  secondary_color: string;
  /** Up to 100 characters. */
  preferred_font: string;
  /** A caption style id (subtitle_styling/templates.py), up to 50 characters. */
  default_preset: string;
  auto_emojis: boolean;
  /** Up to 500 characters. */
  outro_cta_text: string;
}

/** The kit as the v2 screens hold it: the editable fields plus what the server owns. */
export interface BrandKit extends CreateBrandKitRequest {
  id: string;
  is_customized: boolean;
  updated_at: string;
}

/** Schema limits, shared by the form and its validation. */
export const BRAND_KIT_LIMITS = {
  brandName: 255,
  outroCta: 500,
  opacity: { min: 20, max: 100, step: 5 },
  size: { min: 18, max: 48, step: 2 },
} as const;

// NEEDS-BACKEND: POST /brand-kits/logo {content_type, size_bytes} -> {key, url}, and `logo_key` on
// CreateBrandKitRequest (L-API-11). Until then the logo can't be uploaded; an existing logo_url is kept.
