import type { Metadata } from 'next';
import type { ReactNode } from 'react';

import { AppShell } from '@/components/shell';
import { THEME_BOOT_SCRIPT } from '@/components/shell/theme';

export const metadata: Metadata = {
  title: { template: '%s · Clipnera', default: 'Clipnera' },
};

/**
 * Every signed-in /dashboard page renders inside one AppShell that never
 * remounts. `modal` is the @modal slot for intercepted routes (upload, plans, payment).
 * The theme script comes first so the saved theme is set before the shell paints.
 * It lives here rather than in app/layout.tsx because only the v2 shell reads
 * `data-theme`; the legacy screens stay dark whatever was chosen.
 */
export default function DashboardLayout({ children, modal }: { children: ReactNode; modal: ReactNode }) {
  return (
    <>
      <script dangerouslySetInnerHTML={{ __html: THEME_BOOT_SCRIPT }} />
      <AppShell modal={modal}>{children}</AppShell>
    </>
  );
}
