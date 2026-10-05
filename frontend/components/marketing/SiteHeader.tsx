'use client';

import { Menu as MenuIcon } from 'lucide-react';
import Link from 'next/link';
import { useState } from 'react';

import { Button, Drawer, IconButton, Wordmark, buttonClasses } from '@/components/ui';
import { SECTION_LINKS, SIGN_IN_HREF } from '@/lib/marketing/content';
import { focusHeroPrompt } from '@/lib/marketing/heroFocus';
import { useSignedIn } from '@/lib/marketing/useSignedIn';
import { cx, focusRing } from '@/lib/design/styles';

/** Sticky navbar: wordmark, the five section links, and Sign in / Open Clipnera. Phones get a menu drawer. */
export function SiteHeader() {
  const signedIn = useSignedIn();
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <header className="sticky top-0 z-cn-sticky border-b border-cn-border bg-cn-bg">
      <div className="mx-auto flex h-16 max-w-screen-2xl items-center gap-4 px-4 sm:px-8">
        <Link href="/" aria-label="Clipnera home" className={cx('rounded-cn-sm', focusRing)}>
          <Wordmark />
        </Link>

        <nav aria-label="Sections" className="hidden flex-1 justify-center md:flex">
          <ul className="flex gap-1">
            {SECTION_LINKS.map((link) => (
              <li key={link.href}>
                <a href={link.href} className={buttonClasses({ variant: 'ghost', size: 'sm' })}>
                  {link.label}
                </a>
              </li>
            ))}
          </ul>
        </nav>
        <span className="flex-1 md:hidden" />

        <div className="flex items-center gap-2">
          {signedIn ? (
            <Link href="/dashboard" className={buttonClasses({ variant: 'secondary', size: 'sm' })}>
              Open Clipnera
            </Link>
          ) : (
            <>
              <Link href={SIGN_IN_HREF} className={cx(buttonClasses({ variant: 'ghost', size: 'sm' }), 'hidden sm:inline-flex')}>
                Sign in
              </Link>
              <Button variant="secondary" size="sm" onClick={focusHeroPrompt}>
                Start free
              </Button>
            </>
          )}
          <IconButton label="Menu" icon={<MenuIcon />} className="md:hidden" onClick={() => setMenuOpen(true)} />
        </div>
      </div>

      <Drawer open={menuOpen} onOpenChange={setMenuOpen} title="Menu" side="right" size="sm">
        <nav aria-label="Sections" className="flex flex-col gap-1">
          {SECTION_LINKS.map((link) => (
            <a
              key={link.href}
              href={link.href}
              onClick={() => setMenuOpen(false)}
              className={cx(buttonClasses({ variant: 'ghost', size: 'lg', fullWidth: true }), 'justify-start')}
            >
              {link.label}
            </a>
          ))}
          <div className="mt-4 border-t border-cn-border pt-4">
            <Link href={signedIn ? '/dashboard' : SIGN_IN_HREF} className={buttonClasses({ variant: 'secondary', size: 'lg', fullWidth: true })}>
              {signedIn ? 'Open Clipnera' : 'Sign in'}
            </Link>
          </div>
        </nav>
      </Drawer>
    </header>
  );
}
