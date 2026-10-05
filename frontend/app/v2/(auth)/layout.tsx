import Link from 'next/link';
import type { ReactNode } from 'react';

import { Wordmark } from '@/components/ui';
import { cx, focusRing } from '@/lib/design/styles';

const LEGAL_LINKS = [
  ['Privacy', '/privacy'],
  ['Terms', '/terms'],
  ['Refunds', '/refunds'],
  ['Cookies', '/cookies'],
] as const;

/** Sign-in frame (screens/01 §3): one wordmark, a centred card, the legal links. No showcase column (R12). */
export default function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-dvh flex-col items-center justify-center gap-10 bg-cn-bg px-4 py-12 font-cn-sans text-cn-fg sm:py-16">
      <Link href="/" aria-label="Clipnera home" className={cx('rounded-cn-sm', focusRing)}>
        <Wordmark />
      </Link>
      <main id="main" className="w-full max-w-sm rounded-cn-xl border border-cn-border bg-cn-surface p-6 sm:p-8">
        {children}
      </main>
      <nav aria-label="Legal" className="flex flex-wrap justify-center gap-4 text-cn-caption">
        {LEGAL_LINKS.map(([label, href]) => (
          <Link key={href} href={href} className={cx('rounded-cn-xs text-cn-fg-muted hover:text-cn-fg', focusRing)}>
            {label}
          </Link>
        ))}
      </nav>
    </div>
  );
}
