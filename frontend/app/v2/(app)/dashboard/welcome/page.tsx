import type { Metadata } from 'next';

import { HomeScreen } from '@/components/home/HomeScreen';
import { WelcomeRoute } from '@/components/onboarding/WelcomeRoute';

export const metadata: Metadata = { title: 'Welcome' };

/** `/dashboard/welcome` loaded directly (reload, shared link): the welcome over Home. Client navigation gets the @modal version. */
export default function WelcomePage() {
  return (
    <>
      <HomeScreen />
      <WelcomeRoute fullPage />
    </>
  );
}
