import type { Metadata } from 'next';
import { notFound } from 'next/navigation';

import { ExportShare } from './ExportShare';

export const metadata: Metadata = { title: 'Export and share · Screens · Clipnera', robots: { index: false, follow: false } };

/** Export and share mockup. Development only: production builds return 404. */
export default function ExportPage() {
  if (process.env.NODE_ENV === 'production') notFound();
  return <ExportShare />;
}
