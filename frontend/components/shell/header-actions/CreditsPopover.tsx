'use client';

import { Coins } from 'lucide-react';
import Link from 'next/link';
import { useState } from 'react';

import { buttonClasses, InlineAlert, Popover, Skeleton } from '@/components/ui';
import { BILLING_HREF } from '@/components/shell/nav';
import { planName } from '@/components/shell/useAccount';
import type { CreditPack, Entitlements, Payment } from '@/lib/api/credits';
import { cx, focusRing } from '@/lib/design/styles';
import { formatDate } from '@/lib/utils/dates';

import { useCredits } from './useCredits';

const count = (value: number) => value.toLocaleString('en-IN');
const money = (amount: number, currency: string) =>
  new Intl.NumberFormat('en-IN', { style: 'currency', currency, maximumFractionDigits: 0 }).format(amount);

/** DS-4 meter: plan credits in amber, pack credits in neutral; the words beside it carry the meaning. */
function CreditMeter({ planLeft, packs }: { planLeft: number; packs: number }) {
  const total = planLeft + packs;
  if (total <= 0) return null;
  return (
    <div
      role="img"
      aria-label={`${count(planLeft)} plan credits and ${count(packs)} pack credits left`}
      className="flex h-1.5 w-full gap-0.5 overflow-hidden rounded-cn-full bg-cn-surface-active"
    >
      {planLeft > 0 && <span className="h-full rounded-cn-full bg-cn-accent" style={{ width: `${(planLeft / total) * 100}%` }} />}
      {packs > 0 && <span className="h-full rounded-cn-full bg-cn-fg-muted" style={{ width: `${(packs / total) * 100}%` }} />}
    </div>
  );
}

function pendingText(payment: Payment | null): string {
  if (payment?.credits) return `Your UPI payment for ${count(payment.credits)} credits is being checked. I’ll add them and let you know once it’s approved.`;
  if (payment?.plan_name) return `Your UPI payment for ${payment.plan_name} is being checked. I’ll switch it on and let you know once it’s approved.`;
  return 'Your UPI payment is being checked. I’ll let you know once it’s approved.';
}

function Details({ data, packs, pending, onNavigate }: { data: Entitlements; packs: CreditPack[] | undefined; pending: Payment | null; onNavigate: () => void }) {
  const balance = data.credit_minutes_remaining;
  const packLeft = Math.min(data.purchased_credits_remaining, balance);
  const minutes = data.credits_per_video_minute > 0 ? Math.floor(balance / data.credits_per_video_minute) : null;
  const free = data.plan === 'free';
  const rows: Array<[string, string]> = [
    ['Plan', data.plan_expires_at ? `${planName(data.plan)} · ends ${formatDate(data.plan_expires_at)}` : planName(data.plan)],
    ['Plan credits', count(balance - packLeft)],
    ...(data.next_credit_reset_at ? [['Plan credits renew', formatDate(data.next_credit_reset_at)] as [string, string]] : []),
    ['Pack credits', `${count(packLeft)} · never expire`],
  ];

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-col gap-1.5">
        <p className="flex items-baseline justify-between gap-3">
          <span className="font-cn-mono text-cn-title-sm tabular-nums text-cn-fg">{count(balance)}</span>
          {minutes !== null && <span className="text-cn-caption text-cn-fg-secondary">about {count(minutes)} min of video</span>}
        </p>
        <CreditMeter planLeft={balance - packLeft} packs={packLeft} />
      </div>
      <dl className="flex flex-col gap-1 text-cn-caption">
        {rows.map(([term, value]) => (
          <div key={term} className="flex justify-between gap-3">
            <dt className="text-cn-fg-secondary">{term}</dt>
            <dd className="text-right text-cn-fg">{value}</dd>
          </div>
        ))}
      </dl>
      {data.has_pending_payment && (
        <InlineAlert tone="info" live="status">
          {pendingText(pending)}
        </InlineAlert>
      )}
      {packs && packs.length > 0 && (
        <section aria-label="Credit packs" className="flex flex-col gap-1 border-t border-cn-border pt-3">
          <h3 className="text-cn-caption text-cn-fg-muted">Credit packs · never expire</h3>
          <ul className="flex flex-col gap-1 text-cn-caption">
            {packs.map((pack) => (
              <li key={pack.slug} className="flex justify-between gap-3">
                <span className="text-cn-fg">
                  {pack.name} · <span className="font-cn-mono tabular-nums">{count(pack.credits)}</span>
                </span>
                <span className="font-cn-mono tabular-nums text-cn-fg-secondary">{money(pack.amount, pack.currency)}</span>
              </li>
            ))}
          </ul>
        </section>
      )}
      <div className="flex gap-2">
        <Link href={BILLING_HREF} onClick={onNavigate} className={cx(buttonClasses({ variant: 'primary', size: 'sm' }), 'flex-1')}>
          Add credits
        </Link>
        <Link href={BILLING_HREF} onClick={onNavigate} className={buttonClasses({ variant: 'ghost', size: 'sm' })}>
          {free ? 'Upgrade to Pro' : 'See plans'}
        </Link>
      </div>
    </div>
  );
}

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

  const balance = count(data.credit_minutes_remaining);
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
      {(close) => <Details data={data} packs={packs.data} pending={pending} onNavigate={close} />}
    </Popover>
  );
}
