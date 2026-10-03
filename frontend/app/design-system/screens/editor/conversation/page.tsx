import type { Metadata } from 'next';
import { notFound } from 'next/navigation';

import { ConversationStates } from './ConversationStates';

export const metadata: Metadata = { title: 'Conversation panel · Screens · Clipnera', robots: { index: false, follow: false } };

/** Conversation panel states. Development only: production builds return 404. */
export default function ConversationPage() {
  if (process.env.NODE_ENV === 'production') notFound();
  return <ConversationStates />;
}
