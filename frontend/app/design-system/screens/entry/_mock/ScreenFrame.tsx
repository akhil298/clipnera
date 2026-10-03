'use client';

import { ArrowLeft, Moon, Sun } from 'lucide-react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { type ReactNode, useEffect, useState } from 'react';

import { Chip } from '@/components/ui/Chip';
import { SegmentedControl } from '@/components/ui/SegmentedControl';
import { ToastProvider } from '@/components/ui/Toast';
import { cx, focusRing } from '@/lib/design/styles';
import type { ThemeName } from '@/lib/design/tokens';

import { ENTRY_BASE } from './data';
import type { StateOption } from './states';


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

export interface ScreenFrameProps {
  /** Screen name shown in the mockup bar. */
  screen: string;
  states: ReadonlyArray<StateOption>;
  /** Current state (from `?state=`). */
  state: string;
  /** Initial theme (from `?theme=`). */
  theme?: string;
  /** One line under the bar: what the owner should look at. */
  note?: ReactNode;
  children: ReactNode;
}

/**
 * The mockup chrome: a dashed bar that is clearly not product UI, with a state
 * switcher (`?state=`) and the dark/light toggle. The theme sets `data-theme`
 * on <html> so portalled overlays follow it, and is removed on leave.
 */
export function ScreenFrame({ screen, states, state, theme: initialTheme, note, children }: ScreenFrameProps) {
  const router = useRouter();
  const pathname = usePathname();
  const [theme, setTheme] = useState<ThemeName>(initialTheme === 'light' ? 'light' : 'dark');

  useEffect(() => {
    const root = document.documentElement;
    root.dataset.theme = theme;
    return () => {
      delete root.dataset.theme;
    };
  }, [theme]);

  const query = (next: { state?: string; theme?: ThemeName }) => {
    const params = new URLSearchParams();
    params.set('state', next.state ?? state);
    if ((next.theme ?? theme) === 'light') params.set('theme', 'light');
    return `${pathname}?${params.toString()}`;
  };

  const changeTheme = (next: ThemeName) => {
    setTheme(next);
    router.replace(query({ theme: next }), { scroll: false });
  };

  return (
    <ToastProvider>
      <div className="min-h-screen bg-cn-bg font-cn-sans text-cn-fg">
        <div
          role="region"
          aria-label="Mockup controls"
          className="border-b border-dashed border-cn-border-strong bg-cn-surface px-4 py-3 sm:px-6"
        >
          <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
            <Link
              href={ENTRY_BASE}
              className={cx('inline-flex items-center gap-1.5 rounded-cn-sm text-cn-label text-cn-fg-secondary hover:text-cn-fg', focusRing)}
            >
              <ArrowLeft aria-hidden className="size-3.5" />
              Entry screens
            </Link>
            <p className="text-cn-label font-semibold text-cn-fg">
              {screen} <span className="font-normal text-cn-fg-muted">· mockup, sample data</span>
            </p>
            <span className="flex-1" />
            <SegmentedControl label="Theme" size="sm" options={THEMES} value={theme} onValueChange={changeTheme} />
          </div>
          <div role="group" aria-label="Screen state" className="mt-2 flex flex-wrap gap-1.5">
            {states.map((option) => (
              <Chip
                key={option.value}
                size="sm"
                selected={option.value === state}
                onClick={() => router.replace(query({ state: option.value }), { scroll: false })}
              >
                {option.label}
              </Chip>
            ))}
          </div>
          {note && <p className="mt-2 max-w-3xl text-cn-caption text-cn-fg-muted">{note}</p>}
        </div>
        {children}
      </div>
    </ToastProvider>
  );
}
