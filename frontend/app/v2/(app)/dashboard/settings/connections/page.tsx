import type { Metadata } from 'next';

import { SectionMoving } from '@/components/settings/frame';

export const metadata: Metadata = { title: 'Connected accounts' };

/** Hand-over page until U4 replaces it; links to the same controls in the classic design. */
export default function ConnectionsSettingsPage() {
  return <SectionMoving id="connections" />;
}
