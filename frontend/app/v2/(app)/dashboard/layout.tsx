import type { Metadata } from 'next';
import type { ReactNode } from 'react';

import { AppShell } from '@/components/shell';

export const metadata: Metadata = {
  title: { template: '%s · Clipnera', default: 'Clipnera' },
};

/**
 * Every signed-in /dashboard page renders inside one AppShell that never
 * remounts. `modal` is the @modal slot for intercepted routes (upload, plans, payment).
 */
export default function DashboardLayout({ children, modal }: { children: ReactNode; modal: ReactNode }) {
  return <AppShell modal={modal}>{children}</AppShell>;
}
