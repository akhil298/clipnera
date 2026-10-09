import type { Entitlements } from '@/lib/api/credits';
import { type CaptionStyle, getAllCaptionStyles, resolveCaptionPreset } from '@/lib/utils/captionStyles';

/**
 * The caption style catalogue (21 styles) for the brand kit picker.
 *
 * It comes from lib/utils/captionStyles.generated.ts, the generated mirror of
 * backend/subtitle_styling/templates.py (parity is asserted by
 * tests/test_caption_style_parity), so the picker and the burn always agree.
 *
 * NEEDS-BACKEND: GET /subtitle-styles/presets — the route fails response validation today
 * (the service returns `style_type`/`description`/`uses_ass` and a dict `config`, while
 * SubtitleStylePresetResponse wants `id`, `is_preset` and a string `config`). Once it is fixed
 * and says Free/Pro per style, this file can read it instead of the generated mirror.
 */
export const CAPTION_CATALOGUE: ReadonlyArray<CaptionStyle> = getAllCaptionStyles();

/** The catalogue entry for any stored id, old ids included (`hormozi` → Lime stack). */
export const captionStyleFor = (id: string): CaptionStyle =>
  CAPTION_CATALOGUE.find((style) => style.id === resolveCaptionPreset(id)) ?? CAPTION_CATALOGUE[0];

/**
 * Whether the caller's plan can use a style. `caption_styles: null` means every
 * style; unknown entitlements (still loading or failed) count as allowed, since
 * the server checks again on use.
 */
export const isStyleOnPlan = (id: string, entitlements: Entitlements | undefined): boolean =>
  !entitlements?.caption_styles || entitlements.caption_styles.includes(resolveCaptionPreset(id));
