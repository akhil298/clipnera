/** Class helpers shared by every design-system component. */

export type ClassValue = string | false | null | undefined;

/** Joins truthy class names. The codebase has no clsx; this is the one helper. */
export function cx(...values: ClassValue[]): string {
  return values.filter(Boolean).join(' ');
}

/**
 * Keyboard focus ring in the theme's focus colour. The global `:focus-visible`
 * rule in globals.css already draws a 2px outline with a 2px offset; this only
 * swaps its colour so it stays 3:1 in the light theme.
 */
export const focusRing =
  'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cn-focus';

/** The same ring for a wrapper whose inner input has focus (text fields with adornments). */
export const focusWithinRing =
  'focus-within:outline focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-cn-focus';

export type ControlSize = 'sm' | 'md' | 'lg';

/** Heights 32 / 36 / 44 px. `lg` is the phone touch size. */
export const controlHeight: Record<ControlSize, string> = {
  sm: 'h-8',
  md: 'h-9',
  lg: 'h-11',
};

/** A field's edge in each state; shared by Input, Textarea and the prompt bar. */
export function fieldEdge({ invalid, disabled }: { invalid?: boolean; disabled?: boolean }): string {
  if (disabled) return 'border-cn-border bg-cn-surface cursor-not-allowed opacity-60';
  if (invalid) return 'border-cn-danger-text bg-cn-field';
  return 'border-cn-control-border bg-cn-field hover:border-cn-fg-muted';
}

/** Panels that float above the page: menus, popovers, tooltips, toasts. */
export const floatingSurface = 'rounded-cn-lg border border-cn-border-strong bg-cn-surface-raised text-cn-fg shadow-cn-2';
