'use client';

import { ArrowLeft, Moon, Sun } from 'lucide-react';
import Link from 'next/link';
import { type ReactNode, useEffect, useState } from 'react';

import { Badge } from '@/components/ui/Badge';
import { Chip } from '@/components/ui/Chip';
import { SegmentedControl } from '@/components/ui/SegmentedControl';
import { ToastProvider } from '@/components/ui/Toast';
import { cx, focusRing } from '@/lib/design/styles';
import { DEFAULT_THEME, type ThemeName } from '@/lib/design/tokens';

const THEMES = [
  {
    value: 'dark',
    label: (
      <>
        <Moon aria-hidden /> Dark
      </>
    ),
  },
  {
    value: 'light',
    label: (
      <>
        <Sun aria-hidden /> Light
      </>
    ),
  },
] as const;

export const INDEX_HREF = '/design-system/screens/editor';

export interface ScreenShellProps {
  title: string;
  /** One line under the title: what this mockup shows. */
  summary: string;
  /** Flags that gate the real screen (04-architecture §4). */
  flags: ReadonlyArray<string>;
  /** State switcher, scenario picker, replay controls. */
  controls?: ReactNode;
  children: ReactNode;
  /** Full-bleed screens (the Editor) skip the content gutter. */
  bleed?: boolean;
}

/**
 * Frame for every Editor mockup: back to the index, theme toggle, the flags
 * that gate the real screen, and a control strip. Development only.
 */
export function ScreenShell({ title, summary, flags, controls, children, bleed = false }: ScreenShellProps) {
  const [theme, setTheme] = useState<ThemeName>(DEFAULT_THEME);

  useEffect(() => {
    const root = document.documentElement;
    root.dataset.theme = theme;
    return () => {
      delete root.dataset.theme;
    };
  }, [theme]);

  return (
    <ToastProvider>
      <div className="flex min-h-screen flex-col bg-cn-bg font-cn-sans text-cn-fg">
        <a
          href="#mock-main"
          className="fixed left-4 top-2 z-cn-skiplink -translate-y-16 rounded-cn-md bg-cn-accent px-3 py-2 text-cn-label font-semibold text-cn-accent-fg focus:translate-y-0"
        >
          Skip to the mockup
        </a>
        <header className="border-b border-cn-border bg-cn-surface">
          <div className="flex flex-wrap items-center gap-x-3 gap-y-2 px-4 py-2.5 sm:px-6">
            <Link
              href={INDEX_HREF}
              className={cx('inline-flex items-center gap-1.5 rounded-cn-sm text-cn-label font-semibold text-cn-fg-secondary hover:text-cn-fg', focusRing)}
            >
              <ArrowLeft aria-hidden className="size-4" /> Editor screens
            </Link>
            <span aria-hidden className="h-4 w-px bg-cn-border-strong" />
            <h1 className="text-cn-body font-semibold">{title}</h1>
            <span className="hidden text-cn-label text-cn-fg-muted lg:inline">{summary}</span>
            <span className="flex-1" />
            <span className="flex flex-wrap items-center gap-1.5" aria-label="Flags">
              {flags.map((flag) => (
                <Badge key={flag} className="font-cn-mono">
                  {flag}
                </Badge>
              ))}
            </span>
            <SegmentedControl label="Theme" options={THEMES} value={theme} onValueChange={setTheme} size="sm" />
          </div>
          {controls && <div className="flex flex-wrap items-center gap-x-4 gap-y-2 border-t border-cn-border px-4 py-2 sm:px-6">{controls}</div>}
        </header>
        <main id="mock-main" className={cx('flex min-h-0 flex-1 flex-col', !bleed && 'px-4 py-6 sm:px-6')}>
          {children}
        </main>
      </div>
    </ToastProvider>
  );
}

export interface SwitcherOption {
  value: string;
  label: string;
}

/** A labelled row of toggle chips: the state switcher on every mockup. */
export function StateSwitcher({
  label,
  options,
  value,
  onChange,
}: {
  label: string;
  options: ReadonlyArray<SwitcherOption>;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <div role="group" aria-label={label} className="flex min-w-0 flex-wrap items-center gap-1.5">
      <span className="mr-1 text-cn-caption font-semibold text-cn-fg-muted">{label}</span>
      {options.map((option) => (
        <Chip key={option.value} size="sm" selected={option.value === value} onClick={() => onChange(option.value)}>
          {option.label}
        </Chip>
      ))}
    </div>
  );
}

/** Desktop / tablet / phone frames so all three layouts can be seen on one screen. */
export type Device = 'desktop' | 'tablet' | 'phone';

export const DEVICES: ReadonlyArray<SwitcherOption> = [
  { value: 'desktop', label: 'Desktop' },
  { value: 'tablet', label: 'Tablet' },
  { value: 'phone', label: 'Phone' },
];

export function DeviceFrame({ device, children, className }: { device: Device; children: ReactNode; className?: string }) {
  if (device === 'desktop') return <div className={cx('flex min-h-0 flex-1 flex-col', className)}>{children}</div>;
  const size = device === 'tablet' ? 'h-[min(1024px,calc(100dvh-140px))] w-[min(820px,100%)]' : 'h-[min(844px,calc(100dvh-140px))] w-[390px] max-w-full';
  return (
    <div className="flex flex-1 items-start justify-center overflow-auto bg-cn-bg p-4">
      <div
        className={cx(
          'relative flex flex-col overflow-hidden rounded-cn-2xl border border-cn-border-strong bg-cn-bg shadow-cn-3',
          size,
          className,
        )}
        aria-label={`${device === 'tablet' ? 'Tablet' : 'Phone'} frame`}
        role="region"
      >
        {children}
      </div>
    </div>
  );
}
