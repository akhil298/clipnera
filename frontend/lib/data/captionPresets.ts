import { CaptionPreset } from '@/lib/types';
import { getAllCaptionStyles } from '@/lib/utils/captionStyles';

export interface CaptionPresetStyle {
  id: CaptionPreset;
  name: string;
  description: string;
  badge: string;
  font: string;
  previewTextColor: string;
  previewHighlight: string;
  bg: string;
}

/**
 * Derived from the generated (backend-owned) style table rather than written by
 * hand. The hand-maintained list had drifted to 9 of the backend's 20 templates,
 * so eleven styles the burner supports were unreachable from the UI.
 */
export const CAPTION_PRESETS: CaptionPresetStyle[] = getAllCaptionStyles().map((style) => ({
  id: style.id,
  name: style.name,
  description: style.description,
  badge: style.badge,
  font: style.config.fontFamily,
  previewTextColor: style.config.textColor,
  previewHighlight: style.config.highlightColor,
  bg: style.config.hasBgBox ? style.config.bgBoxColor : '#000000',
}));
