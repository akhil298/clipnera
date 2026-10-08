'use client';

import { Coins } from 'lucide-react';
import { useState } from 'react';

import { CreditDetails, formatCredits } from '@/components/shell/CreditDetails';
import { Popover, Skeleton } from '@/components/ui';
import { cx, focusRing } from '@/lib/design/styles';

import { useCredits } from './useCredits';

/**
 * The credits popover (screens/01 §5.3): balance in mono on the trigger; inside,
 * the plan/pack split, renewal, a pending UPI payment, the packs on sale and the
 * way to buy more. The popover is its own view, so its Add credits is the amber action.
 */
export function CreditsPopover({ className }: { className?: string }) {
  const [open, setOpen] = useState(false);
  const { entitlements, packs, pending } = useCredits(open);
  const data = entitlements.data;

  if (entitlements.isPending) return <Skeleton className={cx('h-8 w-20', className)} />;
  // Errors stay quiet in the header: nothing to show is better than a wrong number.
  if (!data) return null;

  const balance = formatCredits(data.credit_minutes_remaining);
  return (
    <Popover
      title="Credits"
      align="end"
      open={open}
      onOpenChange={setOpen}
      className="w-80 max-w-full"
      trigger={(props) => (
        <button
          type="button"
          {...props}
          aria-label={`${balance} credits`}
          className={cx(
            'inline-flex h-8 items-center gap-1.5 rounded-cn-md px-2 text-cn-label text-cn-fg-secondary transition-colors duration-cn-fast',
            'hover:bg-cn-surface-hover hover:text-cn-fg active:bg-cn-surface-active aria-expanded:bg-cn-surface-hover',
            focusRing,
            className,
          )}
        >
          <Coins aria-hidden className="size-4" />
          <span className="font-cn-mono tabular-nums text-cn-fg">{balance}</span>
          {data.has_pending_payment && <span aria-hidden className="size-1.5 rounded-cn-full bg-cn-info" />}
        </button>
      )}
    >
      {(close) => <CreditDetails data={data} packs={packs.data} pending={pending} onNavigate={close} />}
    </Popover>
  );
}
