import type { Metadata } from 'next';

import { SettingsIndex } from '@/components/settings/frame';

export const metadata: Metadata = { title: 'Settings' };

/** The section list on phones and tablets; opens Account on a desktop. */
export default function SettingsPage() {
  return <SettingsIndex />;
}
