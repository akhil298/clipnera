import type { Metadata } from 'next';

import { SectionMoving } from '@/components/settings/frame';

export const metadata: Metadata = { title: 'Notifications' };

/** Hand-over page until U3 replaces it; links to the same controls in the classic design. */
export default function NotificationsSettingsPage() {
  return <SectionMoving id="notifications" />;
}
