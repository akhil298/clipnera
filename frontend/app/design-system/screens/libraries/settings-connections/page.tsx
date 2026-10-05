import type { Metadata } from 'next';
import { notFound } from 'next/navigation';

import { SettingsConnections } from '../_screens/SettingsConnections';

export const metadata: Metadata = { title: 'Connected accounts · Mockup · Clipnera', robots: { index: false, follow: false } };

/** Static mockup. Development only: production builds return 404. */
export default function Page() {
  if (process.env.NODE_ENV === 'production') notFound();
  return <SettingsConnections />;
}
