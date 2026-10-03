import type { Metadata } from 'next';
import { notFound } from 'next/navigation';

import { SettingsBilling } from '../_screens/SettingsBilling';

export const metadata: Metadata = { title: 'Billing · Mockup · Clipnera', robots: { index: false, follow: false } };

/** Static mockup. Development only: production builds return 404. */
export default function Page() {
  if (process.env.NODE_ENV === 'production') notFound();
  return <SettingsBilling />;
}
