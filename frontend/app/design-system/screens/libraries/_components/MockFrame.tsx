'use client';

import { ArrowLeft, Moon, Sun } from 'lucide-react';
import Link from 'next/link';
import { type ReactNode, useEffect, useState } from 'react';

import { Chip } from '@/components/ui/Chip';
import { SegmentedControl } from '@/components/ui/SegmentedControl';
import { ToastProvider } from '@/components/ui/Toast';
import { focusRing } from '@/lib/design/styles';
import { DEFAULT_THEME, type ThemeName } from '@/lib/design/tokens';

export interface MockState {
  id: string;
  label: string;
}

const THEMES = [
  { value: 'dark', label: <><Moon aria-hidden /> Dark</> },
  { value: 'light', label: <><Sun aria-hidden /> Light</> },
] as const;

export const INDEX_HREF = '/design-system/screens/libraries';

/**
 * Chrome around every mockup: back to the index, the screen's name, a state
 * switcher (kept in `?state=` so a state can be linked) and the theme toggle.
 * Nothing here is part of the designed screen.
 */
export function MockFrame({
  title,
  url,
  flag,
  states,
  children,
}: {
  title: string;
  /** The product URL this mockup stands for. */
  url: string;
  flag: string;
  states: readonly MockState[];
  children: (state: string, setState: (id: string) => void) => ReactNode;
}) {
  const [theme, setTheme] = useState<ThemeName>(DEFAULT_THEME);
  const [state, setStateRaw] = useState(states[0]?.id ?? 'default');

  useEffect(() => {
    const fromUrl = new URLSearchParams(window.location.search).get('state');
    if (fromUrl && states.some((s) => s.id === fromUrl)) setStateRaw(fromUrl);
  }, [states]);

  useEffect(() => {
    const root = document.documentElement;
    root.dataset.theme = theme;
    return () => {
      delete root.dataset.theme;
    };
  }, [theme]);

  const setState = (id: string) => {
    setStateRaw(id);
    const next = new URL(window.location.href);
    next.searchParams.set('state', id);
    window.history.replaceState(null, '', next);
  };

  return (
    <ToastProvider>
      <div className="min-h-screen bg-cn-bg font-cn-sans text-cn-fg">
        <div className="border-b border-dashed border-cn-border-strong bg-cn-surface">
          <div className="flex flex-wrap items-center gap-x-3 gap-y-2 px-4 py-2">
            <Link href={INDEX_HREF} className={`inline-flex items-center gap-1.5 rounded-cn-sm text-cn-label text-cn-fg-secondary hover:text-cn-fg ${focusRing}`}>
              <ArrowLeft aria-hidden className="size-4" /> All screens
            </Link>
            <span className="text-cn-label font-semibold text-cn-fg">{title}</span>
            <span className="font-cn-mono text-cn-caption text-cn-fg-muted">{url}</span>
            <span className="font-cn-mono text-cn-caption text-cn-fg-muted">flag {flag}</span>
            <span className="flex-1" />
            <SegmentedControl label="Theme" options={THEMES} value={theme} onValueChange={setTheme} size="sm" />
          </div>
          <div role="group" aria-label="Mockup state" className="flex gap-1.5 overflow-x-auto px-4 pb-2">
            {states.map((s) => (
              <Chip key={s.id} size="sm" selected={state === s.id} onClick={() => setState(s.id)}>
                {s.label}
              </Chip>
            ))}
          </div>
        </div>
        {children(state, setState)}
      </div>
    </ToastProvider>
  );
}
