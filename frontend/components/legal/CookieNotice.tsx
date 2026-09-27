'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { COOKIE_NOTICE_KEY } from './LegalPage';

/**
 * Tells visitors what the browser stores. Clipnera uses strictly necessary
 * storage only, so this is a notice with no consent choices to make; if a
 * tracking tool is ever added it must become an opt-in banner first.
 */
export function CookieNotice() {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    try {
      setVisible(localStorage.getItem(COOKIE_NOTICE_KEY) !== '1');
    } catch {
      setVisible(true);
    }
  }, []);

  if (!visible) return null;

  const dismiss = () => {
    try {
      localStorage.setItem(COOKIE_NOTICE_KEY, '1');
    } catch {
      // Storage blocked: the notice simply shows again next visit.
    }
    setVisible(false);
  };

  return (
    <section
      aria-label="Cookie notice"
      className="fixed bottom-4 inset-x-4 sm:left-auto sm:right-4 sm:max-w-sm z-[60] p-4 rounded-2xl bg-neutral-900 border border-neutral-700 shadow-2xl text-xs text-neutral-300 space-y-3 font-['Plus_Jakarta_Sans',sans-serif]"
    >
      <p>
        Clipnera uses no advertising or tracking cookies. Your browser only stores what keeps you signed in.{' '}
        <Link href="/cookies" className="text-amber-300 underline underline-offset-2">
          Cookie policy
        </Link>
      </p>
      <button
        type="button"
        onClick={dismiss}
        className="px-4 py-2 rounded-lg bg-amber-500 hover:bg-amber-400 text-neutral-950 font-bold"
      >
        OK
      </button>
    </section>
  );
}
