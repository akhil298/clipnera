import type { Metadata } from 'next';
import { notFound } from 'next/navigation';

import { TimelineStates } from './TimelineStates';

export const metadata: Metadata = { title: 'Timeline and preview · Screens · Clipnera', robots: { index: false, follow: false } };

/** Timeline and preview mockup. Development only: production builds return 404. */
export default function TimelinePage() {
  if (process.env.NODE_ENV === 'production') notFound();
  return <TimelineStates />;
}
