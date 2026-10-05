import type { ReactNode } from 'react';

import { AdminGate } from '@/components/admin/AdminGate';
import { LogoMark } from '@/components/ui/LogoMark';

/**
 * PLACEHOLDER admin chrome (Phase 0). Area 10 replaces it with a server role check and AdminShell
 * mounted once. Until then the legacy client gate keeps admin chrome from non-admins; the API enforces it.
 */
export default function AdminLayout({ children }: { children: ReactNode }) {
  return (
    <AdminGate>
      <div className="flex min-h-dvh flex-col bg-cn-bg font-cn-sans text-cn-fg">
        <header className="flex h-14 items-center gap-2 border-b border-cn-border px-4">
          <LogoMark size={24} />
          <span className="font-cn-display text-cn-body-lg font-bold">Clipnera admin</span>
          <span className="ml-auto text-cn-label text-cn-fg-muted">New UI preview</span>
        </header>
        <main id="main" className="flex min-w-0 flex-1 flex-col">
          {children}
        </main>
      </div>
    </AdminGate>
  );
}
