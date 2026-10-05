import type { Metadata } from 'next';
import { notFound } from 'next/navigation';

import { Workspace } from './Workspace';

export const metadata: Metadata = { title: 'Editor · Screens · Clipnera', robots: { index: false, follow: false } };

/** Editor workspace mockup. Development only: production builds return 404. */
export default function EditorWorkspacePage() {
  if (process.env.NODE_ENV === 'production') notFound();
  return <Workspace />;
}
