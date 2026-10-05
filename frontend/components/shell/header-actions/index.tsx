'use client';

import { NotificationBell } from '@/components/shell/notifications/NotificationBell';

import { ActivityIndicator } from './ActivityIndicator';
import { CreditsPopover } from './CreditsPopover';

/**
 * The top bar's right side (screens/01 §5.2–5.4, 07 §5.2): live work, credits
 * and the inbox. New video lives in the sidebar and the phone tab bar, so the
 * page keeps its one amber action; on phones credits move to the More drawer,
 * leaving the bell and the activity dot beside the avatar.
 */
export function HeaderActions() {
  return (
    <div className="flex items-center gap-1 sm:gap-2">
      <ActivityIndicator />
      <CreditsPopover className="hidden md:inline-flex" />
      <NotificationBell />
    </div>
  );
}
