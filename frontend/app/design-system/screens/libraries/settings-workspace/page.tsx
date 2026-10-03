import type { Metadata } from 'next';
import { notFound } from 'next/navigation';

import { SettingsWorkspace } from '../_screens/SettingsWorkspace';

export const metadata: Metadata = { title: 'Workspace and team · Mockup · Clipnera', robots: { index: false, follow: false } };

/** Static mockup. Development only: production builds return 404. */
export default function Page() {
  if (process.env.NODE_ENV === 'production') notFound();
  return <SettingsWorkspace />;
}
