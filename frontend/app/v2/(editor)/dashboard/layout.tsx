import type { ReactNode } from 'react';

/** Full screen, no shell. Area 4 adds the editor fonts and caption CSS here. */
export default function EditorLayout({ children }: { children: ReactNode }) {
  return (
    <div className="flex h-dvh flex-col overflow-hidden bg-cn-bg font-cn-sans text-cn-fg">
      <main id="main" className="flex min-h-0 flex-1 flex-col">
        {children}
      </main>
    </div>
  );
}
