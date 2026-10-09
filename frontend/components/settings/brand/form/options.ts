import type { LogoPosition } from '@/lib/api/brand/types';

/** The four watermark corners, in reading order for the 2 × 2 picker. */
export const LOGO_POSITIONS: ReadonlyArray<{ value: LogoPosition; label: string }> = [
  { value: 'top_left', label: 'Top left' },
  { value: 'top_right', label: 'Top right' },
  { value: 'bottom_left', label: 'Bottom left' },
  { value: 'bottom_right', label: 'Bottom right' },
];

/** The three brand fonts (legacy parity). `className` sets the face from the self-hosted tokens. */
export const BRAND_FONTS = [
  { value: 'Syne', note: 'Ultra bold', className: 'font-cn-display' },
  { value: 'Plus Jakarta Sans', note: 'Clean', className: 'font-cn-sans' },
  { value: 'JetBrains Mono', note: 'Techy', className: 'font-cn-mono' },
] as const;

/** The token class for a stored font name; an unknown one falls back to the UI face. */
export const fontClassFor = (font: string): string => BRAND_FONTS.find((f) => f.value === font)?.className ?? 'font-cn-sans';

export const HEX_COLOUR = /^#[0-9a-f]{6}$/i;
