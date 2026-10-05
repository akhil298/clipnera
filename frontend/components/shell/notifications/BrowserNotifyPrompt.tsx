'use client';

import { BellRing } from 'lucide-react';
import { useEffect, useState } from 'react';

import { Button } from '@/components/ui';
import { usePersistentState } from '@/lib/design/usePersistentState';

/**
 * Asks once for browser notifications (screens/01 §5.2). Shown only where the
 * browser supports them and the user hasn't answered or dismissed it yet.
 */
export function BrowserNotifyPrompt() {
  const [dismissed, setDismissed] = usePersistentState('cn_browser_notify_prompt', false);
  const [permission, setPermission] = useState<NotificationPermission | 'unsupported'>('unsupported');
  const [asking, setAsking] = useState(false);

  useEffect(() => {
    setPermission(typeof Notification === 'undefined' ? 'unsupported' : Notification.permission);
  }, []);

  if (dismissed || permission !== 'default') return null;

  const turnOn = async () => {
    setAsking(true);
    try {
      setPermission(await Notification.requestPermission());
    } finally {
      setAsking(false);
      setDismissed(true);
    }
  };

  return (
    <div className="flex items-start gap-3 rounded-cn-lg border border-cn-border bg-cn-surface p-3">
      <BellRing aria-hidden className="mt-0.5 size-4 shrink-0 text-cn-fg-secondary" />
      <div className="flex-1 space-y-2">
        <p className="text-cn-label text-cn-fg">Get a browser notification when clips are ready, even with this tab closed.</p>
        <div className="flex gap-2">
          <Button size="sm" variant="secondary" loading={asking} loadingLabel="Asking your browser" onClick={turnOn}>
            Turn on
          </Button>
          <Button size="sm" variant="ghost" onClick={() => setDismissed(true)}>
            Not now
          </Button>
        </div>
      </div>
    </div>
  );
}
