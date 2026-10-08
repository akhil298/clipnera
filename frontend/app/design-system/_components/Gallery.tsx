'use client';

import { Moon, Sun } from 'lucide-react';
import { useEffect, useState } from 'react';

import { SegmentedControl } from '@/components/ui/SegmentedControl';
import { ToastProvider } from '@/components/ui/Toast';
import { focusRing } from '@/lib/design/styles';
import { DEFAULT_THEME, type ThemeName } from '@/lib/design/tokens';

import { AgentSection } from './AgentSection';
import { ControlsSection } from './ControlsSection';
import { DataSection } from './DataSection';
import { DisplaySection } from './DisplaySection';
import { EditorSection } from './EditorSection';
import { FeedbackSection } from './FeedbackSection';
import { FormsSection } from './FormsSection';
import { FoundationsSection } from './FoundationsSection';
import { MediaSection } from './MediaSection';
import { OverlaysSection } from './OverlaysSection';
import { PromptSection } from './PromptSection';
import { ShellSection } from './ShellSection';

const SECTIONS = [
  { id: 'foundations', label: 'Foundations' },
  { id: 'controls', label: 'Controls' },
  { id: 'overlays', label: 'Overlays' },
  { id: 'display', label: 'Display' },
  { id: 'forms', label: 'More inputs' },
  { id: 'feedback', label: 'Messages' },
  { id: 'data', label: 'Data and figures' },
  { id: 'shell', label: 'App shell' },
  { id: 'prompt', label: 'Prompt experience' },
  { id: 'agent', label: 'Agent replies' },
  { id: 'media', label: 'Media' },
  { id: 'editor', label: 'Editor primitives' },
] as const;

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

/**
 * Every design-system component in every state. The theme toggle sets
 * `data-theme` on <html> while this page is open, so portalled overlays
 * follow it too, and removes it on leave.
 */
export function Gallery() {
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
      <div className="min-h-screen bg-cn-bg font-cn-sans text-cn-fg">
        <a
          href="#gallery-main"
          className="fixed left-4 top-2 z-cn-skiplink -translate-y-16 rounded-cn-md bg-cn-accent px-3 py-2 text-cn-label font-semibold text-cn-accent-fg focus:translate-y-0"
        >
          Skip to components
        </a>
        <header className="sticky top-0 z-cn-sticky border-b border-cn-border bg-cn-bg/90 backdrop-blur">
          <div className="mx-auto flex h-14 max-w-7xl items-center gap-3 px-4 sm:px-6">
            <h1 className="flex items-baseline gap-3">
              <span className="font-cn-display text-cn-title-sm font-bold tracking-tight">clipnera</span>
              <span className="hidden text-cn-label font-normal text-cn-fg-muted sm:inline">Design system · development only</span>
              <span className="sr-only sm:hidden">Design system</span>
            </h1>
            <span className="flex-1" />
            <SegmentedControl label="Theme" options={THEMES} value={theme} onValueChange={setTheme} size="sm" />
          </div>
        </header>
        <div className="mx-auto flex max-w-7xl gap-10 px-4 py-10 sm:px-6">
          <nav aria-label="Gallery sections" className="sticky top-24 hidden h-fit w-44 shrink-0 lg:block">
            <ul className="space-y-1">
              {SECTIONS.map((section) => (
                <li key={section.id}>
                  <a
                    href={`#${section.id}`}
                    className={`block rounded-cn-sm px-2 py-1.5 text-cn-label text-cn-fg-secondary hover:bg-cn-surface-hover hover:text-cn-fg ${focusRing}`}
                  >
                    {section.label}
                  </a>
                </li>
              ))}
            </ul>
          </nav>
          <main id="gallery-main" className="min-w-0 flex-1 space-y-10">
            <FoundationsSection theme={theme} />
            <ControlsSection />
            <OverlaysSection />
            <DisplaySection />
            <FormsSection />
            <FeedbackSection />
            <DataSection />
            <ShellSection />
            <PromptSection />
            <AgentSection />
            <MediaSection />
            <EditorSection />
          </main>
        </div>
      </div>
    </ToastProvider>
  );
}
