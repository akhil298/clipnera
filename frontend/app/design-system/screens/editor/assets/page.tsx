import type { Metadata } from 'next';
import { notFound } from 'next/navigation';

import { AssetSidebar } from './AssetSidebar';

export const metadata: Metadata = { title: 'Assets and B-roll · Screens · Clipnera', robots: { index: false, follow: false } };

/** Assets and B-roll mockup. Development only: production builds return 404. */
export default function AssetsPage() {
  if (process.env.NODE_ENV === 'production') notFound();
  return <AssetSidebar />;
}
