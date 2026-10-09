'use client';

import { useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';

export const PLANS_PATH = '/dashboard/plans';

/**
 * Guards unsaved edits. Closing or reloading the tab gets the browser's own
 * prompt (`beforeunload`); an in-app link click is held and returned as
 * `pendingHref`, so the page can ask first. The App Router has no navigation
 * events, so links are caught in the capture phase before Next handles them.
 */
export function useLeaveGuard(active: boolean) {
  const router = useRouter();
  const [pendingHref, setPendingHref] = useState<string | null>(null);

  useEffect(() => {
    if (!active) return;
    const onBeforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault();
    };
    const onClick = (event: MouseEvent) => {
      if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      const anchor = (event.target as Element | null)?.closest?.('a[href]');
      if (!(anchor instanceof HTMLAnchorElement) || anchor.target === '_blank' || anchor.hasAttribute('download')) return;
      const url = new URL(anchor.href, window.location.href);
      if (url.origin !== window.location.origin || url.pathname === window.location.pathname) return;
      // Plans opens as a dialog over this page (@modal), so the edits stay.
      if (url.pathname.startsWith(PLANS_PATH)) return;
      event.preventDefault();
      event.stopPropagation();
      setPendingHref(`${url.pathname}${url.search}${url.hash}`);
    };
    window.addEventListener('beforeunload', onBeforeUnload);
    document.addEventListener('click', onClick, true);
    return () => {
      window.removeEventListener('beforeunload', onBeforeUnload);
      document.removeEventListener('click', onClick, true);
    };
  }, [active]);

  return {
    pendingHref,
    stay: () => setPendingHref(null),
    leave: () => {
      if (pendingHref) router.push(pendingHref);
      setPendingHref(null);
    },
  };
}
