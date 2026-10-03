import type { Metadata } from 'next';
import { notFound } from 'next/navigation';

import { ReelBoard } from './ReelBoard';

export const metadata: Metadata = { title: 'Reels · Screens · Clipnera', robots: { index: false, follow: false } };

/** Reels mockup. Development only: production builds return 404. */
export default function ReelsPage() {
  if (process.env.NODE_ENV === 'production') notFound();
  return <ReelBoard />;
}
