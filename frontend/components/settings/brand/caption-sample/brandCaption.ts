import type { CreateBrandKitRequest } from '@/lib/api/brand/types';
import type { CaptionConfig } from '@/lib/types';
import { getCaptionConfig, resolveCaptionPreset } from '@/lib/utils/captionStyles';

/**
 * A caption style as the editor applies it with this kit: the kit's colours and
 * emoji choice over the style's look. Fonts stay the style's, because the burn
 * can't render the kit's font (same rule as withBrandKitCaption in lib/editor/clip-doc.ts).
 */
export function brandCaptionConfig(
  styleId: string,
  kit: Pick<CreateBrandKitRequest, 'primary_color' | 'secondary_color' | 'auto_emojis'>,
): CaptionConfig {
  return {
    ...getCaptionConfig(resolveCaptionPreset(styleId)),
    highlightColor: kit.primary_color,
    secondaryHighlightColor: kit.secondary_color,
    emojisEnabled: kit.auto_emojis,
  };
}
