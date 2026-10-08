/** CSS stand-ins for the FFmpeg looks in backend/edit_engine/looks.py; the preview is close, not exact. */
export const LOOK_FILTERS: Record<string, string> = {
  natural: 'contrast(1.03) saturate(1.05)',
  clean_bright: 'brightness(1.05) contrast(1.05) saturate(1.08)',
  warm_film: 'sepia(0.15) contrast(1.06) saturate(0.95)',
  teal_orange: 'contrast(1.08) saturate(1.1) hue-rotate(-8deg)',
  moody: 'contrast(1.12) brightness(0.94) saturate(0.8)',
  vivid: 'contrast(1.08) saturate(1.3)',
  bw_punch: 'grayscale(1) contrast(1.25)',
};

/** The CSS `filter` for a Timeline's `look`, for the stage that holds the picture layers. */
export const lookFilter = (look: string): string => LOOK_FILTERS[look] ?? LOOK_FILTERS.natural;
