'use client';

import { Check, Minus, RotateCcw } from 'lucide-react';
import Link from 'next/link';
import { useState } from 'react';

import { Badge, Button, InlineAlert, SegmentedControl, Skeleton, SkeletonGroup, buttonClasses } from '@/components/ui';
import type { BillingPeriod, PlanOfferResponse } from '@/lib/api';
import { cx } from '@/lib/design/styles';
import { focusHeroPrompt } from '@/lib/marketing/heroFocus';
import { usePublicPlans, yearlySaving } from '@/lib/marketing/plans';
import { useSignedIn } from '@/lib/marketing/useSignedIn';
import { comparisonRows, formatAmount } from '@/lib/utils/payments';

const BILLING_PATH = '/dashboard/settings?tab=billing';
const PERIOD_SUFFIX: Record<BillingPeriod, string> = { monthly: 'a month', yearly: 'a year' };

/** Free plus every plan on sale, as the legacy page shows them. */
const shownPlans = (plans: PlanOfferResponse[]) => plans.filter((plan) => plan.slug === 'free' || plan.prices.length > 0);

function PlanCard({ plan, period }: { plan: PlanOfferResponse; period: BillingPeriod }) {
  const signedIn = useSignedIn();
  const paid = plan.prices.length > 0;
  const price = plan.prices.find((p) => p.plan_type === period) ?? plan.prices[0];
  const rows = comparisonRows(plan.capabilities, false);

  return (
    <article
      aria-labelledby={`plan-${plan.slug}`}
      className={cx('flex h-full flex-col gap-5 rounded-cn-lg border bg-cn-surface p-6', paid ? 'border-cn-accent-border' : 'border-cn-border')}
    >
      <div className="flex flex-col gap-2">
        <h3 id={`plan-${plan.slug}`} className="text-cn-title-sm font-semibold text-cn-fg">
          {plan.name}
        </h3>
        <p className="flex items-baseline gap-1.5">
          <span className="font-cn-mono text-cn-title-lg font-semibold tabular-nums text-cn-fg">{formatAmount(price?.amount ?? 0, price?.currency ?? 'INR')}</span>
          {price && <span className="text-cn-label text-cn-fg-secondary">{PERIOD_SUFFIX[price.plan_type]}</span>}
        </p>
      </div>
      <ul className="flex flex-col gap-2 text-cn-body">
        {rows.map((row) => (
          <li key={row.label} className={cx('flex items-start gap-2', row.included ? 'text-cn-fg' : 'text-cn-fg-muted')}>
            {row.included ? (
              <Check aria-hidden className="mt-0.5 size-4 shrink-0 text-cn-success-text" />
            ) : (
              <Minus aria-hidden className="mt-0.5 size-4 shrink-0 text-cn-fg-muted" />
            )}
            <span>
              <span className="sr-only">{row.included ? 'Included: ' : 'Not included: '}</span>
              {row.label}
            </span>
          </li>
        ))}
      </ul>
      <div className="mt-auto">
        {paid ? (
          <Link href={signedIn ? BILLING_PATH : `/login?next=${encodeURIComponent(BILLING_PATH)}`} className={buttonClasses({ variant: 'primary', fullWidth: true })}>
            Get {plan.name}
          </Link>
        ) : (
          <Button variant="secondary" fullWidth onClick={focusHeroPrompt}>
            Start free
          </Button>
        )}
      </div>
    </article>
  );
}

/** Plans, prices and limits from `GET /subscription/plans`: the same rules the app enforces. */
export function Pricing() {
  const { data, isPending, isError, refetch, isRefetching } = usePublicPlans();
  const [period, setPeriod] = useState<BillingPeriod>('monthly');

  if (isPending) {
    return (
      <SkeletonGroup label="Loading plans" className="mx-auto grid max-w-3xl gap-4 md:grid-cols-2">
        <Skeleton className="h-96 rounded-cn-lg" />
        <Skeleton className="h-96 rounded-cn-lg" />
      </SkeletonGroup>
    );
  }

  if (isError) {
    return (
      <InlineAlert
        tone="danger"
        live="alert"
        className="mx-auto max-w-3xl"
        title="Prices didn’t load"
        action={
          <Button variant="secondary" size="sm" leadingIcon={<RotateCcw />} loading={isRefetching} onClick={() => refetch()}>
            Try again
          </Button>
        }
      >
        The Free plan needs no card, so you can start now either way.
      </InlineAlert>
    );
  }

  const plans = shownPlans(data.plans);
  if (plans.length === 0) {
    return (
      <InlineAlert className="mx-auto max-w-3xl" title="Plans are being updated">
        The Free plan needs no card, so you can start now and see prices in the app.
      </InlineAlert>
    );
  }

  const periods = [...new Set(plans.flatMap((plan) => plan.prices.map((p) => p.plan_type)))];
  const sample = plans.find((plan) => plan.prices.length > 1)?.prices;
  const monthly = sample?.find((p) => p.plan_type === 'monthly')?.amount;
  const yearly = sample?.find((p) => p.plan_type === 'yearly')?.amount;
  const saving = monthly && yearly ? yearlySaving(monthly, yearly) : null;

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      {periods.length > 1 && (
        <div className="flex flex-wrap items-center justify-center gap-3">
          <SegmentedControl
            label="Billing period"
            options={[
              { value: 'monthly', label: 'Monthly' },
              { value: 'yearly', label: 'Yearly' },
            ]}
            value={period}
            onValueChange={setPeriod}
          />
          {saving && <Badge tone="success">Save {saving}% yearly</Badge>}
        </div>
      )}
      <ul className={cx('grid gap-4', plans.length > 1 && 'md:grid-cols-2')}>
        {plans.map((plan) => (
          <li key={plan.slug}>
            <PlanCard plan={plan} period={period} />
          </li>
        ))}
      </ul>
      {data.credit_packs.length > 0 && (
        <p className="text-center text-cn-label text-cn-fg-secondary">
          Need more? One-time credit packs that never expire:{' '}
          {data.credit_packs.map((pack) => `${pack.credits} credits for ${formatAmount(pack.amount, pack.currency)}`).join(' · ')}. See the{' '}
          <Link href="/refunds" className="text-cn-accent-text underline underline-offset-2">
            Refund Policy
          </Link>
          .
        </p>
      )}
    </div>
  );
}
