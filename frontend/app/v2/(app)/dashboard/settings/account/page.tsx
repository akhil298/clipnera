import type { Metadata } from 'next';

import { AccountScreen } from '@/components/settings/account';

export const metadata: Metadata = { title: 'Account and privacy' };

/** Data loads on the client: the token is not visible to the server yet. */
export default function AccountSettingsPage() {
  return <AccountScreen />;
}
