import type { Metadata } from 'next';
import { notFound } from 'next/navigation';

import { SettingsNotifications } from '../_screens/SettingsNotifications';

export const metadata: Metadata = { title: 'Notifications · Mockup · Clipnera', robots: { index: false, follow: false } };

/** Static mockup. Development only: production builds return 404. */
export default function Page() {
  if (process.env.NODE_ENV === 'production') notFound();
  return <SettingsNotifications />;
}
