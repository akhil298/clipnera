import type { ReactNode } from 'react';

/** PLACEHOLDER (Phase 0). Area 2 builds the site header and footer here. */
export default function MarketingLayout({ children }: { children: ReactNode }) {
  return <div className="flex min-h-dvh flex-col bg-cn-bg font-cn-sans text-cn-fg">{children}</div>;
}
