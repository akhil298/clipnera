import Link from 'next/link';

import { buttonClasses } from '@/components/ui/Button';
import { LogoMark } from '@/components/ui/LogoMark';

/** Branded 404 for any URL with no route, including direct /v2 requests. */
export default function NotFound() {
  return (
    <main id="main" className="flex min-h-dvh flex-col items-center justify-center gap-6 bg-cn-bg px-4 text-center font-cn-sans text-cn-fg">
      <LogoMark size={40} />
      <div className="flex flex-col gap-2">
        <p className="font-cn-mono text-cn-label text-cn-accent-text">404</p>
        <h1 className="font-cn-display text-cn-display-sm font-bold">This page doesn&apos;t exist</h1>
        <p className="max-w-sm text-cn-body text-cn-fg-secondary">The link may be old, or the page has moved.</p>
      </div>
      <div className="flex flex-wrap items-center justify-center gap-2">
        <Link href="/dashboard" className={buttonClasses()}>
          Go to dashboard
        </Link>
        <Link href="/" className={buttonClasses({ variant: 'ghost' })}>
          Clipnera home
        </Link>
      </div>
    </main>
  );
}
