import type { ReactNode } from 'react';

import { ToastProvider } from '@/components/ui/Toast';

/** Every editor mockup reads `useToast` above its ScreenShell, so the provider sits here. */
export default function EditorMockupsLayout({ children }: { children: ReactNode }) {
  return <ToastProvider>{children}</ToastProvider>;
}
