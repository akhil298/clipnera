import type { Metadata } from 'next';
import Link from 'next/link';
import { notFound } from 'next/navigation';

import { Badge } from '@/components/ui/Badge';
import { Card, cardLinkOverlay } from '@/components/ui/Card';
import { cx, focusRing } from '@/lib/design/styles';

import { ENTRY_BASE } from './_mock/data';
import { SCREENS } from './_mock/states';

export const metadata: Metadata = {
  title: 'Entry and dashboard mockups · Clipnera',
  robots: { index: false, follow: false },
};

/**
 * Index of the Wave 2 entry and dashboard mockups (Product Designer 1).
 * Spec: docs/revamp/screens/01-entry-and-dashboard.md. Development only.
 */
export default function EntryScreensIndex() {
  if (process.env.NODE_ENV === 'production') notFound();
  return (
    <div className="min-h-screen bg-cn-bg font-cn-sans text-cn-fg">
      <main className="mx-auto max-w-5xl px-4 py-12 sm:px-6">
        <p className="text-cn-label text-cn-fg-muted">Design system · Wave 2 screens · development only</p>
        <h1 className="mt-1 text-cn-title-lg font-bold">Entry and dashboard</h1>
        <p className="mt-2 max-w-2xl text-cn-body text-cn-fg-secondary">
          Clickable static mockups built only from <code className="font-cn-mono text-cn-label">components/ui</code> and the{' '}
          <code className="font-cn-mono text-cn-label">cn-*</code> tokens, with sample data and no API calls. Each screen has a state switcher
          and a dark/light toggle. Spec: <code className="font-cn-mono text-cn-label">docs/revamp/screens/01-entry-and-dashboard.md</code>.
        </p>
        <p className="mt-2 max-w-2xl text-cn-caption text-cn-fg-muted">
          If the screens look unstyled, the running dev server has not picked up the new Tailwind <code className="font-cn-mono">cn-*</code> keys
          yet; it needs a restart (02 §2.9).
        </p>
        <ul className="mt-8 grid gap-4 sm:grid-cols-2">
          {Object.values(SCREENS).map((screen) => (
            <li key={screen.slug}>
              <Card interactive className="flex h-full flex-col gap-2">
                <div className="flex items-start justify-between gap-3">
                  <h2 className="text-cn-title-sm font-semibold">
                    <Link href={`${ENTRY_BASE}/${screen.slug}`} className={cx(cardLinkOverlay, focusRing, 'rounded-cn-xs')}>
                      {screen.title}
                    </Link>
                  </h2>
                  <Badge className="relative z-cn-raised">{screen.flag}</Badge>
                </div>
                <p className="font-cn-mono text-cn-caption text-cn-fg-muted">{screen.url}</p>
                <p className="text-cn-body text-cn-fg-secondary">{screen.summary}</p>
                <p className="mt-auto pt-2 text-cn-caption text-cn-fg-muted">
                  {screen.states.length} states: {screen.states.map((state) => state.label).join(' · ')}
                </p>
              </Card>
            </li>
          ))}
        </ul>
      </main>
    </div>
  );
}
