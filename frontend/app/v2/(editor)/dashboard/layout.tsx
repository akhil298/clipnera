import type { ReactNode } from 'react';

import { ToastProvider } from '@/components/ui/Toast';

/** Full screen, no shell. The editor has no app shell, so it mounts its own toasts for every editor unit. */
export default function EditorLayout({ children }: { children: ReactNode }) {
  return (
    <ToastProvider>
      <div className="flex h-dvh flex-col overflow-hidden bg-cn-bg font-cn-sans text-cn-fg">
        <main id="main" className="flex min-h-0 flex-1 flex-col">
          {children}
        </main>
      </div>
    </ToastProvider>
  );
}
