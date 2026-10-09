import type { Metadata } from 'next';

import { SectionMoving } from '@/components/settings/frame';

export const metadata: Metadata = { title: 'Workspace and team' };

/** Hand-over page until U2 replaces it; links to the same controls in the classic design. */
export default function WorkspaceSettingsPage() {
  return <SectionMoving id="workspace" />;
}
