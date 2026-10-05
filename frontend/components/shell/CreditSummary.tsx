'use client';

import { ChevronRight, Coins } from 'lucide-react';
import Link from 'next/link';

import { buttonClasses, Popover, ProgressBar, Skeleton, useSidebarCollapsed } from '@/components/ui';
import { formatDate } from '@/lib/utils/dates';
import { cx, focusRing } from '@/lib/design/styles';

import { BILLING_HREF } from './nav';
import { planName, useMe } from './useAccount';

const formatCount = (value: number) => value.toLocaleString('en-IN');

/**
 * The compact credit meter above the account menu: balance in mono and the
 * plan name, opening a popover with the detail. Hidden in the collapsed rail.
 * Errors stay quiet here: the account menu below already says the account didn't load.
 */
export function CreditSummary() {
  const collapsed = useSidebarCollapsed();
  const me = useMe();
  if (collapsed || me.isError) return null;
  if (me.isPending) return <Skeleton className="h-9 w-full" />;

  const { plan, plan_expires_at: endsAt, ai_credits_minutes_remaining: balance, ai_credits_total: total } = me.data;
  const name = `${planName(plan)} plan`;

  return (
    <Popover
      title="Credits"
      side="top"
      align="start"
      trigger={(props) => (
        <button
          type="button"
          {...props}
          aria-label={`${formatCount(balance)} credits, ${name}`}
          className={cx(
            'flex h-9 w-full items-center gap-2 rounded-cn-md px-2.5 text-left text-cn-label transition-colors duration-cn-fast',
            'hover:bg-cn-surface-hover active:bg-cn-surface-active aria-expanded:bg-cn-surface-hover',
            focusRing,
          )}
        >
          <Coins aria-hidden className="size-4 shrink-0 text-cn-fg-muted" />
          <span className="font-cn-mono tabular-nums text-cn-fg">{formatCount(balance)}</span>
          <span className="min-w-0 flex-1 truncate text-cn-fg-muted">credits</span>
          <span className="shrink-0 text-cn-caption text-cn-fg-secondary">{planName(plan)}</span>
        </button>
      )}
    >
      {(close) => (
        <div className="flex w-64 max-w-full flex-col gap-3">
          {total > 0 && balance <= total ? (
            <ProgressBar label="Credits left" value={balance} max={total} valueText={`${formatCount(balance)} of ${formatCount(total)}`} size="sm" />
          ) : (
            <p className="text-cn-body">
              <span className="font-cn-mono tabular-nums">{formatCount(balance)}</span> credits left
            </p>
          )}
          <p className="text-cn-caption text-cn-fg-secondary">
            {endsAt ? `${name} · paid access ends ${formatDate(endsAt)}. Pro doesn’t renew on its own.` : name}
          </p>
          <Link
            href={BILLING_HREF}
            onClick={close}
            className={buttonClasses({ variant: 'secondary', size: 'sm' })}
          >
            Add credits or change plan
            <ChevronRight aria-hidden className="size-4" />
          </Link>
        </div>
      )}
    </Popover>
  );
}
