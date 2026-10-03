'use client';

import Link from 'next/link';

import { cx, focusRing } from '@/lib/design/styles';

import { ScreenFrame } from '../_mock/ScreenFrame';
import { CallbackCard, SignInPanel, type SignInVariant } from '../_mock/SignInPanel';
import { Wordmark } from '../_mock/StandIns';
import { SCREENS } from '../_mock/states';

const CALLBACK = ['callback', 'consent', 'cancelled', 'stale'] as const;
type CallbackVariant = (typeof CALLBACK)[number];

const FOOT_LINKS = [
  ['Privacy', '/privacy'],
  ['Terms', '/terms'],
  ['Refunds', '/refunds'],
  ['Cookies', '/cookies'],
] as const;

export function SignInMock({ state, theme }: { state: string; theme?: string }) {
  const isCallback = (CALLBACK as readonly string[]).includes(state);
  return (
    <ScreenFrame
      screen={SCREENS['sign-in'].title}
      states={SCREENS['sign-in'].states}
      state={state}
      theme={theme}
      note="/login and /signup render this same page; signed-in visitors are redirected to /dashboard (or ?next=). The landing page shows the same panel in a dialog."
    >
      <div className="flex flex-col items-center gap-10 px-4 py-12 sm:py-16">
        <Link href="/" aria-label="Clipnera home" className={cx('rounded-cn-sm', focusRing)}>
          <Wordmark />
        </Link>
        <main className="w-full max-w-sm rounded-cn-xl border border-cn-border bg-cn-surface p-6 shadow-cn-1 sm:p-8">
          {isCallback ? <CallbackCard variant={state as CallbackVariant} /> : <SignInPanel variant={state as SignInVariant} />}
        </main>
        <nav aria-label="Legal" className="flex flex-wrap justify-center gap-4 text-cn-caption">
          {FOOT_LINKS.map(([label, href]) => (
            <Link key={href} href={href} className={cx('rounded-cn-xs text-cn-fg-muted hover:text-cn-fg', focusRing)}>
              {label}
            </Link>
          ))}
        </nav>
      </div>
    </ScreenFrame>
  );
}
