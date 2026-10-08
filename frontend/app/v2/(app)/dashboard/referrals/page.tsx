import type { Metadata } from 'next';

import { ReferralsScreen } from '@/components/referrals-v2/ReferralsScreen';

export const metadata: Metadata = { title: 'Refer and earn' };

/** Refer and earn. Data loads on the client: the token is not visible to the server yet. */
export default function ReferralsPage() {
  return <ReferralsScreen />;
}
