import type { Metadata } from 'next';

import { BrandKitScreen } from '@/components/settings/brand/form/BrandKitScreen';

export const metadata: Metadata = { title: 'Brand kit' };

/** Brand kit (screens/03 §16). Data loads on the client: the token is not visible to the server yet. */
export default function BrandKitPage() {
  return <BrandKitScreen />;
}
