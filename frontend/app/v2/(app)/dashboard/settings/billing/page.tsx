import type { Metadata } from 'next';

import { SectionMoving } from '@/components/settings/frame';

export const metadata: Metadata = { title: 'Plan and billing' };

/** Hand-over page until U5 replaces it; links to the same controls in the classic design. */
export default function BillingSettingsPage() {
  return <SectionMoving id="billing" />;
}
