import type { ReactNode } from 'react';

import { SiteFooter } from '@/components/marketing/SiteFooter';
import { SiteHeader } from '@/components/marketing/SiteHeader';

/** Marketing chrome for `/` and `/editor`: skip link, sticky header, footer. */
export default function MarketingLayout({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-dvh flex-col bg-cn-bg font-cn-sans text-cn-fg">
      <a
        href="#landing-main"
        className="fixed left-4 top-2 z-cn-skiplink -translate-y-16 rounded-cn-md bg-cn-accent px-3 py-2 text-cn-label font-semibold text-cn-accent-fg focus:translate-y-0"
      >
        Skip to content
      </a>
      <SiteHeader />
      {children}
      <SiteFooter />
    </div>
  );
}
