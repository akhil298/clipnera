/**
 * Clipnera design tokens: the single source of truth.
 *
 * - `app/tokens.css` is generated from this file (`node lib/design/write-tokens-css.mts`)
 *   and checked against it by `lib/design/tokens.test.mts` (`npm test`).
 * - `tailwind.config.ts` maps its `cn-*` theme keys from this file.
 * - Spec, contrast ratios and usage rules: `docs/revamp/02-design-system.md`.
 *
 * Every CSS variable is namespaced `--cn-*` so it cannot collide with the
 * legacy variables in `globals.css` (`--border`, `--primary`, …).
 * Keep this file free of imports and non-erasable TypeScript: Node runs it
 * directly with type stripping in the token test.
 */

export type ThemeName = 'dark' | 'light';

/** Dark ships first and is the default (`:root`); light applies under `[data-theme="light"]`. */
export const DEFAULT_THEME: ThemeName = 'dark';

export type ColorToken =
  | 'bg'
  | 'surface'
  | 'surface-raised'
  | 'field'
  | 'surface-hover'
  | 'surface-active'
  | 'overlay'
  | 'border'
  | 'border-strong'
  | 'control-border'
  | 'fg'
  | 'fg-secondary'
  | 'fg-muted'
  | 'fg-disabled'
  | 'accent'
  | 'accent-hover'
  | 'accent-pressed'
  | 'accent-fg'
  | 'accent-text'
  | 'accent-subtle'
  | 'accent-border'
  | 'success'
  | 'success-subtle'
  | 'success-text'
  | 'danger'
  | 'danger-text'
  | 'danger-subtle'
  | 'danger-solid'
  | 'danger-solid-hover'
  | 'on-danger'
  | 'info'
  | 'info-text'
  | 'info-subtle'
  | 'focus';

/**
 * Semantic colours per theme. Values are Tailwind's neutral, amber, emerald,
 * rose and sky scales (no other hues). Three intermediate neutrals
 * (`#1c1c1c`, `#111111`, `#6b6b6b`/`#8a8a8a`) exist for elevation and the
 * 3:1 control-border rule; they are still neutral, not a new hue.
 */
export const colors = {
  dark: {
    bg: '#0a0a0a', // neutral-950: the page
    surface: '#171717', // neutral-900: cards, panels, sidebars
    'surface-raised': '#1c1c1c', // menus, popovers, dialogs, toasts
    field: '#111111', // inside inputs and the prompt bar
    'surface-hover': '#262626', // neutral-800: hover fill for rows and quiet buttons
    'surface-active': '#2e2e2e', // pressed / selected neutral fill
    overlay: '#000000', // scrim, always used with alpha (bg-cn-overlay/60)
    border: '#262626', // neutral-800: dividers and card edges (decorative)
    'border-strong': '#404040', // neutral-700: emphasised edges, hover borders
    'control-border': '#6b6b6b', // edges that identify a control: 3:1 on every surface
    fg: '#fafafa', // neutral-50: primary text
    'fg-secondary': '#a3a3a3', // neutral-400: supporting text
    'fg-muted': '#8c8c8c', // the project's lightened neutral-500: hints, meta
    'fg-disabled': '#525252', // neutral-600: disabled text (exempt from contrast)
    accent: '#f59e0b', // amber-500: primary action fill, selection
    'accent-hover': '#fbbf24', // amber-400
    'accent-pressed': '#d97706', // amber-600
    'accent-fg': '#0a0a0a', // text and icons on an amber fill
    'accent-text': '#fbbf24', // amber-400: amber text and links on neutral
    'accent-subtle': '#362a15', // amber-500 at 14% over surface: selected chips, accent badges
    'accent-border': '#f59e0b', // edge of a checked or selected control
    success: '#10b981', // emerald-500: fills, dots
    'success-text': '#34d399', // emerald-400
    'success-subtle': '#162e26',
    danger: '#f43f5e', // rose-500
    'danger-text': '#fb7185', // rose-400
    'danger-subtle': '#361d21',
    'danger-solid': '#e11d48', // rose-600: destructive button fill (white text 4.7:1)
    'danger-solid-hover': '#be123c', // rose-700
    'on-danger': '#ffffff',
    info: '#0ea5e9', // sky-500
    'info-text': '#38bdf8', // sky-400
    'info-subtle': '#162b34',
    focus: '#fbbf24', // amber-400: same as the global focus ring in globals.css
  },
  light: {
    bg: '#fafafa', // neutral-50
    surface: '#ffffff',
    'surface-raised': '#ffffff',
    field: '#ffffff',
    'surface-hover': '#f5f5f5', // neutral-100
    'surface-active': '#e5e5e5', // neutral-200
    overlay: '#0a0a0a',
    border: '#e5e5e5', // neutral-200
    'border-strong': '#d4d4d4', // neutral-300
    'control-border': '#8a8a8a',
    fg: '#0a0a0a', // neutral-950
    'fg-secondary': '#525252', // neutral-600
    'fg-muted': '#6b6b6b', // between neutral-500 and -600: AA on every light surface
    'fg-disabled': '#a3a3a3', // neutral-400
    accent: '#f59e0b', // amber-500: the brand fill does not change by theme
    'accent-hover': '#fbbf24', // amber-400
    'accent-pressed': '#d97706', // amber-600
    'accent-fg': '#0a0a0a',
    'accent-text': '#b45309', // amber-700: amber-400/500 text fails AA on white
    'accent-subtle': '#fffbeb', // amber-50
    'accent-border': '#b45309', // amber-500 is 2.2:1 on white; a checked edge needs 3:1
    success: '#10b981',
    'success-text': '#047857', // emerald-700
    'success-subtle': '#ecfdf5', // emerald-50
    danger: '#f43f5e',
    'danger-text': '#be123c', // rose-700
    'danger-subtle': '#fff1f2', // rose-50
    'danger-solid': '#e11d48',
    'danger-solid-hover': '#be123c',
    'on-danger': '#ffffff',
    info: '#0ea5e9',
    'info-text': '#0369a1', // sky-700
    'info-subtle': '#f0f9ff', // sky-50
    focus: '#b45309', // amber-700: amber-400 is 1.7:1 on white, below the 3:1 a focus ring needs
  },
} as const satisfies Record<ThemeName, Record<ColorToken, string>>;

/** Elevation. Dark mode leans on surface lightness and a hairline; shadows carry less. */
export const shadows = {
  dark: {
    '1': '0 1px 2px 0 rgb(0 0 0 / 0.5)',
    '2': '0 8px 24px -6px rgb(0 0 0 / 0.6), 0 0 0 1px rgb(255 255 255 / 0.04)',
    '3': '0 24px 64px -12px rgb(0 0 0 / 0.75), 0 0 0 1px rgb(255 255 255 / 0.05)',
  },
  light: {
    '1': '0 1px 2px 0 rgb(10 10 10 / 0.06)',
    '2': '0 8px 24px -6px rgb(10 10 10 / 0.12), 0 0 0 1px rgb(10 10 10 / 0.04)',
    '3': '0 24px 64px -12px rgb(10 10 10 / 0.22), 0 0 0 1px rgb(10 10 10 / 0.05)',
  },
} as const satisfies Record<ThemeName, Record<'1' | '2' | '3', string>>;

export const fontFamily = {
  /** UI text. Already self-hosted and used app-wide. */
  sans: ['"Plus Jakarta Sans"', 'ui-sans-serif', 'system-ui', 'sans-serif'],
  /** Wordmark and marketing display headings only. */
  display: ['Syne', '"Plus Jakarta Sans"', 'sans-serif'],
  /** Timecodes, durations, credits, shortcuts. Replaces the system `font-mono` stack. */
  mono: ['"JetBrains Mono"', 'ui-monospace', 'SFMono-Regular', 'monospace'],
} as const;

type TypeStep = readonly [size: string, style: { lineHeight: string; letterSpacing?: string; fontWeight?: string }];

/** Type scale. 12px is the floor for anything a user needs to read. */
export const fontSize = {
  caption: ['0.75rem', { lineHeight: '1rem' }], // 12/16: meta, badges, timecodes
  label: ['0.8125rem', { lineHeight: '1.125rem' }], // 13/18: controls, table cells, dense UI
  body: ['0.875rem', { lineHeight: '1.25rem' }], // 14/20: app default
  'body-lg': ['1rem', { lineHeight: '1.5rem' }], // 16/24: prompt bar, marketing body, mobile inputs
  'title-sm': ['1.125rem', { lineHeight: '1.625rem', letterSpacing: '-0.005em' }], // 18/26: card and dialog titles
  title: ['1.25rem', { lineHeight: '1.75rem', letterSpacing: '-0.01em' }], // 20/28: section headings, mobile page title
  'title-lg': ['1.5rem', { lineHeight: '2rem', letterSpacing: '-0.015em' }], // 24/32: page title
  'display-sm': ['2rem', { lineHeight: '2.5rem', letterSpacing: '-0.02em' }], // 32/40
  display: ['3rem', { lineHeight: '3.5rem', letterSpacing: '-0.025em' }], // 48/56: home hero
  'display-lg': ['4rem', { lineHeight: '4.25rem', letterSpacing: '-0.03em' }], // 64/68: marketing hero
} as const satisfies Record<string, TypeStep>;

export const fontWeight = { regular: '400', medium: '500', semibold: '600', bold: '700' } as const;

/** 4px grid. These are Tailwind's own steps; listed so non-Tailwind code uses the same values. */
export const space = {
  '0': '0px',
  '0.5': '2px',
  '1': '4px',
  '1.5': '6px',
  '2': '8px',
  '3': '12px',
  '4': '16px',
  '5': '20px',
  '6': '24px',
  '8': '32px',
  '10': '40px',
  '12': '48px',
  '16': '64px',
} as const;

/** Control heights. `lg` is the touch size on phones (44px). */
export const controlHeight = { sm: '32px', md: '36px', lg: '44px' } as const;

export const radius = {
  xs: '4px', // kbd, tiny badges
  sm: '6px', // chips, small buttons, menu items
  md: '8px', // buttons, inputs
  lg: '12px', // cards, menus, popovers, toasts
  xl: '16px', // dialogs, drawers, panels
  '2xl': '20px', // home prompt bar
  full: '9999px',
} as const;

/**
 * Layer order, low to high. Every overlay renders in a portal on `document.body`,
 * so these values are global. The audit's collision (sticky navbar and sign-in
 * modal both `z-50`) cannot happen: sticky chrome is 100, dialogs 400.
 */
export const zIndex = {
  base: '0',
  raised: '10', // inside a component: sticky table header, selected clip on the timeline
  sticky: '100', // app header, landing navbar, editor top bar
  banner: '200', // cookie notice, plan banner: under every overlay
  drawer: '300', // drawers, sheets, mobile navigation
  dialog: '400', // modal dialogs
  popover: '500', // menus, popovers, select lists, slash menu: above a dialog that opened them
  toast: '600',
  tooltip: '700',
  skiplink: '800',
} as const;

/** Durations in ms. Interface motion stays within 150–250; `highlight` is the one exception. */
export const duration = {
  instant: 0,
  stream: 120, // streaming text word-group fade
  fast: 150, // hover, press, tooltip, step tick, page cross-fade
  base: 200, // panels, dialogs, menus, height collapse
  slow: 250, // drawers and sheets
  highlight: 600, // an operation landing on the timeline
} as const;

export const easing = {
  /** Entering: decelerates into place. */
  out: 'cubic-bezier(0.16, 1, 0.3, 1)',
  /** Leaving: accelerates away. */
  in: 'cubic-bezier(0.4, 0, 1, 1)',
  /** Moving or resizing on screen. */
  'in-out': 'cubic-bezier(0.65, 0, 0.35, 1)',
} as const;

/** Delays in ms for pointer-driven reveals. */
export const delay = {
  tooltip: 500, // first tooltip; others open instantly within `tooltipSkip`
  tooltipSkip: 300,
  mediaHover: 150, // hover preview on a media card
} as const;

/** Tailwind's default breakpoints, restated so JS layout code matches CSS. */
export const breakpoint = { sm: 640, md: 768, lg: 1024, xl: 1280, '2xl': 1536 } as const;

/* ------------------------------------------------------------------------ */
/* CSS generation                                                            */
/* ------------------------------------------------------------------------ */

/** `#f59e0b` → `245 158 11`, so Tailwind can apply alpha: `rgb(var(--cn-accent) / 0.1)`. */
export function hexToRgbChannels(hex: string): string {
  const value = hex.replace('#', '');
  return [0, 2, 4].map((i) => parseInt(value.slice(i, i + 2), 16)).join(' ');
}

function themeBlock(theme: ThemeName): string[] {
  const lines = Object.entries(colors[theme]).map(([name, hex]) => `  --cn-${name}: ${hexToRgbChannels(hex)};`);
  for (const [level, value] of Object.entries(shadows[theme])) lines.push(`  --cn-shadow-${level}: ${value};`);
  return lines;
}

function staticBlock(): string[] {
  const lines: string[] = [];
  for (const [name, value] of Object.entries(radius)) lines.push(`  --cn-radius-${name}: ${value};`);
  for (const [name, value] of Object.entries(zIndex)) lines.push(`  --cn-z-${name}: ${value};`);
  for (const [name, value] of Object.entries(duration)) lines.push(`  --cn-duration-${name}: ${value}ms;`);
  for (const [name, value] of Object.entries(easing)) lines.push(`  --cn-ease-${name}: ${value};`);
  lines.push(`  --cn-font-sans: ${fontFamily.sans.join(', ')};`);
  lines.push(`  --cn-font-display: ${fontFamily.display.join(', ')};`);
  lines.push(`  --cn-font-mono: ${fontFamily.mono.join(', ')};`);
  return lines;
}

/** The whole of `app/tokens.css`. */
export function renderTokensCss(): string {
  return [
    '/* Generated from lib/design/tokens.ts by `node lib/design/write-tokens-css.mts`. Do not edit by hand. */',
    '/* Only --cn-* variables, cn-* keyframes and [data-theme] colour-scheme: nothing here restyles an existing screen. */',
    '',
    ':root,',
    '[data-theme="dark"] {',
    ...themeBlock('dark'),
    ...staticBlock(),
    '}',
    '',
    '[data-theme="light"] {',
    ...themeBlock('light'),
    '}',
    '',
    '/* Native controls and scrollbars follow the theme only where a theme is set explicitly. */',
    '[data-theme="dark"] {',
    '  color-scheme: dark;',
    '}',
    '',
    '[data-theme="light"] {',
    '  color-scheme: light;',
    '}',
    '',
    '/* Working text: a slow light sweep across the active step. Static under reduced motion. */',
    '@keyframes cn-shimmer {',
    '  from { background-position: 100% 0; }',
    '  to { background-position: -100% 0; }',
    '}',
    '',
    '.cn-shimmer-text {',
    '  background-image: linear-gradient(90deg, rgb(var(--cn-fg-secondary)) 0%, rgb(var(--cn-fg-secondary)) 40%, rgb(var(--cn-fg)) 50%, rgb(var(--cn-fg-secondary)) 60%, rgb(var(--cn-fg-secondary)) 100%);',
    '  background-size: 200% 100%;',
    '  -webkit-background-clip: text;',
    '  background-clip: text;',
    '  color: transparent;',
    '  animation: cn-shimmer 2.4s linear infinite;',
    '}',
    '',
    '/* An operation landing on the timeline: amber outline that fades over 600 ms. */',
    '@keyframes cn-highlight {',
    '  from { box-shadow: 0 0 0 2px rgb(var(--cn-accent)); }',
    '  to { box-shadow: 0 0 0 2px rgb(var(--cn-accent) / 0); }',
    '}',
    '',
    '/* Indeterminate bars: a short segment travels along the track. Replaces spinners. */',
    '@keyframes cn-sweep {',
    '  from { transform: translateX(-100%); }',
    '  to { transform: translateX(250%); }',
    '}',
    '',
    '/* Skeleton blocks. */',
    '@keyframes cn-pulse {',
    '  0%, 100% { opacity: 1; }',
    '  50% { opacity: 0.55; }',
    '}',
    '',
    '@media (prefers-reduced-motion: reduce) {',
    '  .cn-shimmer-text {',
    '    animation: none;',
    '    background-image: none;',
    '    color: rgb(var(--cn-fg-secondary));',
    '  }',
    '}',
    '',
  ].join('\n');
}
