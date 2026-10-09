import type { ReactNode } from 'react';

import { SettingsFrame } from '@/components/settings/frame';

/** Every `/dashboard/settings/*` page sits in the settings frame (screens/03 §9.1). */
export default function SettingsLayout({ children }: { children: ReactNode }) {
  return <SettingsFrame>{children}</SettingsFrame>;
}
