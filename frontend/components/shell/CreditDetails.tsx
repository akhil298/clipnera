'use client';

import Link from 'next/link';

import { buttonClasses, InlineAlert } from '@/components/ui';
import { BILLING_HREF } from '@/components/shell/nav';
import { planName } from '@/components/shell/useAccount';
import { creditSplit, type CreditPack, type Entitlements, type Payment } from '@/lib/api/credits';
import { cx } from '@/lib/design/styles';
import { formatDate } from '@/lib/utils/dates';

export const formatCredits = (value: number) => value.toLocaleString('en-IN');
const money = (amount: number, currency: string) =>
  new Intl.NumberFormat('en-IN', { style: 'currency', currency, maximumFractionDigits: 0 }).format(amount);

/** DS-4 meter: plan credits in amber, expiring bonus credits in sky (time-bound), pack credits in neutral; the words beside it carry the meaning. */
function CreditMeter({ plan, bonus, bought }: ReturnType<typeof creditSplit>) {
  const total = plan + bonus + bought;
  if (total <= 0) return null;
  const parts = [
    [plan, 'bg-cn-accent'],
    [bonus, 'bg-cn-info'],
    [bought, 'bg-cn-fg-muted'],
  ] as const;
  return (
    <div
      role="img"
      aria-label={`${formatCredits(plan)} plan credits, ${bonus > 0 ? `${formatCredits(bonus)} bonus credits, ` : ''}${formatCredits(bought)} pack credits left`}
      className="flex h-1.5 w-full gap-0.5 overflow-hidden rounded-cn-full bg-cn-surface-active"
    >
      {parts.map(([value, color]) => value > 0 && <span key={color} className={cx('h-full rounded-cn-full', color)} style={{ width: `${(value / total) * 100}%` }} />)}
    </div>
  );
}

function pendingText(payment: Payment | null): string {
  if (payment?.credits) return `Your UPI payment for ${formatCredits(payment.credits)} credits is being checked. I’ll add them and let you know once it’s approved.`;
  if (payment?.plan_name) return `Your UPI payment for ${payment.plan_name} is being checked. I’ll switch it on and let you know once it’s approved.`;
  return 'Your UPI payment is being checked. I’ll let you know once it’s approved.';
}

export interface CreditDetailsProps {
  data: Entitlements;
  packs: CreditPack[] | undefined;
  pending: Payment | null;
  /** Closes the popover the details sit in when a link is followed. */
  onNavigate: () => void;
}

/** The credits detail shared by the header popover and the sidebar meter, so there is one credits view. */
export function CreditDetails({ data, packs, pending, onNavigate }: CreditDetailsProps) {
  const balance = data.credit_minutes_remaining;
  const split = creditSplit(data);
  const minutes = data.credits_per_video_minute > 0 ? Math.floor(balance / data.credits_per_video_minute) : null;
  const free = data.plan === 'free';
  const rows: Array<[string, string]> = [
    ['Plan', data.plan_expires_at ? `${planName(data.plan)} · ends ${formatDate(data.plan_expires_at)}` : planName(data.plan)],
    ['Plan credits', formatCredits(split.plan)],
    ...(data.next_credit_reset_at ? [['Plan credits renew', formatDate(data.next_credit_reset_at)] as [string, string]] : []),
    ...(split.bonus > 0 ? [['Bonus credits', formatCredits(split.bonus)] as [string, string]] : []),
    ['Pack credits', `${formatCredits(split.bought)} · never expire`],
  ];

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-col gap-1.5">
        <p className="flex items-baseline justify-between gap-3">
          <span className="font-cn-mono text-cn-title-sm tabular-nums text-cn-fg">{formatCredits(balance)}</span>
          {minutes !== null && <span className="text-cn-caption text-cn-fg-secondary">about {formatCredits(minutes)} min of video</span>}
        </p>
        <CreditMeter {...split} />
      </div>
      <dl className="flex flex-col gap-1 text-cn-caption">
        {rows.map(([term, value]) => (
          <div key={term} className="flex justify-between gap-3">
            <dt className="text-cn-fg-secondary">{term}</dt>
            <dd className="text-right text-cn-fg">{value}</dd>
          </div>
        ))}
      </dl>
      {split.bonus > 0 && (
        <p className="text-cn-caption text-cn-fg-secondary">
          {data.bonus_credits_expiring_at
            ? `${formatCredits(data.bonus_credits_expiring)} bonus credits expire on ${formatDate(data.bonus_credits_expiring_at)}. `
            : ''}
          Bonus credits are used first when they’d expire before your plan credits.
        </p>
      )}
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
                  {pack.name} · <span className="font-cn-mono tabular-nums">{formatCredits(pack.credits)}</span>
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
