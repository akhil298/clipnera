import type { Metadata } from 'next';
import { notFound } from 'next/navigation';

import { Gallery } from './_components/Gallery';

export const metadata: Metadata = {
  title: 'Design system · Clipnera',
  robots: { index: false, follow: false },
};

/** Component gallery for the revamp. Development only: production builds return 404. */
export default function DesignSystemPage() {
  if (process.env.NODE_ENV === 'production') notFound();
  return <Gallery />;
}
