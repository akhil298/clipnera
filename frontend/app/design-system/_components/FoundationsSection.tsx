'use client';

import { useState } from 'react';

import { Button } from '@/components/ui/Button';
import { cx } from '@/lib/design/styles';
import { colors, duration, fontSize, radius, type ThemeName, zIndex } from '@/lib/design/tokens';

import { GallerySection, Specimen } from './Specimen';

const COLOR_GROUPS: ReadonlyArray<{ title: string; names: ReadonlyArray<keyof (typeof colors)['dark']> }> = [
  { title: 'Surfaces', names: ['bg', 'surface', 'surface-raised', 'field', 'surface-hover', 'surface-active'] },
  { title: 'Lines', names: ['border', 'border-strong', 'control-border', 'focus'] },
  { title: 'Text', names: ['fg', 'fg-secondary', 'fg-muted', 'fg-disabled'] },
  { title: 'Accent', names: ['accent', 'accent-hover', 'accent-pressed', 'accent-fg', 'accent-text', 'accent-subtle', 'accent-border'] },
  {
    title: 'Status',
    names: ['success', 'success-text', 'success-subtle', 'danger', 'danger-text', 'danger-subtle', 'danger-solid', 'info', 'info-text', 'info-subtle'],
  },
];

const MOTION_DEMO = ['fast', 'base', 'slow', 'highlight'] as const;

export function FoundationsSection({ theme }: { theme: ThemeName }) {
  const [moved, setMoved] = useState(false);

  return (
    <GallerySection
      id="foundations"
      title="Foundations"
      intro="Tokens from lib/design/tokens.ts, read through the --cn-* variables. Values shown are for the current theme."
    >
      <Specimen title="Colour" note="Semantic names, not scale steps. Contrast ratios are in 02-design-system.md §2.1.">
        <div className="space-y-6">
          {COLOR_GROUPS.map((group) => (
            <div key={group.title} className="space-y-2">
              <h4 className="text-cn-label font-semibold text-cn-fg-secondary">{group.title}</h4>
              <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
                {group.names.map((name) => (
                  <li key={name} className="flex items-center gap-2.5">
                    <span
                      aria-hidden
                      className="size-9 shrink-0 rounded-cn-md border border-cn-border-strong"
                      style={{ backgroundColor: `rgb(var(--cn-${name}))` }}
                    />
                    <span className="min-w-0">
                      <span className="block truncate font-cn-mono text-cn-caption text-cn-fg">{name}</span>
                      <span className="block font-cn-mono text-cn-caption text-cn-fg-muted">{colors[theme][name]}</span>
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </Specimen>

      <Specimen title="Type" note="Plus Jakarta Sans for UI, Syne for the wordmark and marketing display, JetBrains Mono for numbers. 12px floor.">
        <ul className="space-y-3">
          {Object.entries(fontSize).map(([name, [size, step]]) => (
            <li key={name} className="flex items-baseline gap-4">
              <span className="w-28 shrink-0 font-cn-mono text-cn-caption text-cn-fg-muted">
                {name} {parseFloat(size) * 16}/{parseFloat(step.lineHeight) * 16}
              </span>
              {/* Inline style: Tailwind cannot see class names built at runtime. */}
              <span
                style={{ fontSize: size, ...step }}
                className={cx(name.startsWith('display') ? 'font-cn-display font-bold' : 'font-semibold', 'truncate')}
              >
                Clips from your long videos
              </span>
            </li>
          ))}
          <li className="flex items-baseline gap-4">
            <span className="w-28 shrink-0 font-cn-mono text-cn-caption text-cn-fg-muted">mono</span>
            <span className="font-cn-mono text-cn-body tabular-nums">0:12 – 0:31 · 1,240 credits</span>
          </li>
        </ul>
      </Specimen>

      <div className="grid gap-6 lg:grid-cols-2">
        <Specimen title="Radius">
          <ul className="flex flex-wrap gap-4">
            {Object.entries(radius).map(([name, value]) => (
              <li key={name} className="flex flex-col items-center gap-1.5">
                <span aria-hidden className="size-14 border border-cn-control-border bg-cn-surface" style={{ borderRadius: value }} />
                <span className="font-cn-mono text-cn-caption text-cn-fg-muted">{name}</span>
              </li>
            ))}
          </ul>
        </Specimen>
        <Specimen title="Elevation">
          <ul className="flex flex-wrap gap-5">
            {['1', '2', '3'].map((level) => (
              <li
                key={level}
                className="flex size-20 items-center justify-center rounded-cn-lg bg-cn-surface-raised font-cn-mono text-cn-caption text-cn-fg-muted"
                style={{ boxShadow: `var(--cn-shadow-${level})` }}
              >
                shadow-{level}
              </li>
            ))}
          </ul>
        </Specimen>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Specimen title="Motion" note="Press Play. Under reduced motion every bar jumps at once (the CSS transition is motion-safe only).">
          <div className="space-y-3">
            {MOTION_DEMO.map((name) => (
              <div key={name} className="flex items-center gap-3">
                <span className="w-24 shrink-0 font-cn-mono text-cn-caption text-cn-fg-muted">
                  {name} {duration[name]}ms
                </span>
                <span className="relative h-2 flex-1 rounded-cn-full bg-cn-surface-active">
                  <span
                    className="absolute inset-y-0 left-0 rounded-cn-full bg-cn-accent ease-cn-out motion-safe:transition-[width]"
                    style={{ width: moved ? '100%' : '8%', transitionDuration: `${duration[name]}ms` }}
                  />
                </span>
              </div>
            ))}
            <Button size="sm" variant="secondary" onClick={() => setMoved(!moved)}>
              Play
            </Button>
          </div>
        </Specimen>
        <Specimen title="Layers (z-index)" note="Overlays portal to <body>. Sticky chrome can never cover a dialog.">
          <ol className="space-y-1 font-cn-mono text-cn-caption">
            {Object.entries(zIndex)
              .reverse()
              .map(([name, value]) => (
                <li key={name} className="flex justify-between border-b border-cn-border py-1 last:border-b-0">
                  <span className="text-cn-fg">z-cn-{name}</span>
                  <span className="text-cn-fg-muted">{value}</span>
                </li>
              ))}
          </ol>
        </Specimen>
      </div>
    </GallerySection>
  );
}
