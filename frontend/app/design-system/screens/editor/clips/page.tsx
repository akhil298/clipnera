import type { Metadata } from 'next';
import { notFound } from 'next/navigation';

import { ClipList } from './ClipList';

export const metadata: Metadata = { title: 'Project clips · Screens · Clipnera', robots: { index: false, follow: false } };

/** Project clips mockup. Development only: production builds return 404. */
export default function ClipsPage() {
  if (process.env.NODE_ENV === 'production') notFound();
  return <ClipList />;
}
