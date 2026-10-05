'use client';

import './globals.css';

import { Button } from '@/components/ui/Button';
import { LogoMark } from '@/components/ui/LogoMark';

/** Last-resort boundary: replaces the root layout, so it renders its own <html>. */
export default function GlobalError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <html lang="en" className="dark">
      <body className="bg-cn-bg font-cn-sans text-cn-fg antialiased">
        <main id="main" className="flex min-h-dvh flex-col items-center justify-center gap-6 px-4 text-center">
          <LogoMark size={40} />
          <div className="flex flex-col gap-2">
            <h1 className="font-cn-display text-cn-display-sm font-bold">Clipnera hit a problem</h1>
            <p className="max-w-sm text-cn-body text-cn-fg-secondary">Reload the page to carry on. If it keeps happening, send us the report id.</p>
            {error.digest && <p className="font-cn-mono text-cn-label text-cn-fg-muted">Report id {error.digest}</p>}
          </div>
          <div className="flex flex-wrap items-center justify-center gap-2">
            <Button onClick={() => window.location.reload()}>Reload</Button>
            <Button variant="ghost" onClick={reset}>
              Try again
            </Button>
          </div>
        </main>
      </body>
    </html>
  );
}
