'use client';

import { useSyncExternalStore } from 'react';

import { Banner } from '@/components/ui';

function subscribe(onChange: () => void) {
  window.addEventListener('online', onChange);
  window.addEventListener('offline', onChange);
  return () => {
    window.removeEventListener('online', onChange);
    window.removeEventListener('offline', onChange);
  };
}

/** The strip under the top bar while the browser is offline (screens/01 §5.7). */
export function OfflineBanner() {
  const online = useSyncExternalStore(
    subscribe,
    () => navigator.onLine,
    () => true,
  );
  if (online) return null;
  return (
    <Banner tone="neutral" live="status">
      You’re offline. Work already started keeps going on our side; this page catches up when you’re back.
    </Banner>
  );
}
