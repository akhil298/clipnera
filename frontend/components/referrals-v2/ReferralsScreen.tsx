'use client';

import { useQuery } from '@tanstack/react-query';
import { RotateCcw, Users } from 'lucide-react';
import { useState } from 'react';

import { Button, Card, EmptyState, InlineAlert, SegmentedControl, Skeleton, SkeletonGroup, StatCard } from '@/components/ui';
import { getMyReferrals } from '@/lib/api/referrals';
import { referralKeys } from '@/lib/query/keys/referrals';
import { OPEN_REFERRAL_STATUSES } from '@/lib/referral';
import type { ReferralItem } from '@/lib/types';

import { HowItWorks } from './HowItWorks';
import { ReferralRow } from './ReferralRow';
import { ReferralRules } from './ReferralRules';
import { ShareCard } from './ShareCard';
import { useMinuteClock } from './useMinuteClock';

type Filter = 'all' | 'open' | 'done' | 'failed';

const FILTERS: ReadonlyArray<{ value: Filter; label: string }> = [
  { value: 'all', label: 'All' },
  { value: 'open', label: 'In progress' },
  { value: 'done', label: 'Completed' },
  { value: 'failed', label: 'Failed' },
];

function groupOf(item: ReferralItem): Exclude<Filter, 'all'> {
  if (OPEN_REFERRAL_STATUSES.includes(item.status)) return 'open';
  return item.status === 'succeeded' || item.status === 'partial' ? 'done' : 'failed';
}

const PAGE = 'mx-auto flex w-full max-w-6xl flex-col gap-6 px-4 py-6 sm:px-6 lg:px-8 lg:py-8';

function ReferralsSkeleton() {
  return (
    <SkeletonGroup label="Loading your referrals" className={PAGE}>
      <div className="grid gap-4 lg:grid-cols-[1.3fr_1fr]">
        <Skeleton className="h-80" />
        <Skeleton className="h-80" />
      </div>
      <Skeleton className="h-24" />
      <Skeleton className="h-48" />
    </SkeletonGroup>
  );
}

/** Refer and earn (parity with the legacy ReferralsView): the code, how it works, stats, everyone referred, and the rules. */
export function ReferralsScreen() {
  const referrals = useQuery({ queryKey: referralKeys.mine(), queryFn: ({ signal }) => getMyReferrals(signal) });
  const [filter, setFilter] = useState<Filter>('all');
  const now = useMinuteClock();

  if (referrals.isPending) return <ReferralsSkeleton />;
  if (referrals.isError) {
    return (
      <div className={PAGE}>
        <InlineAlert
          tone="danger"
          title="I couldn’t load your referrals"
          action={
            <Button variant="secondary" size="sm" leadingIcon={<RotateCcw />} onClick={() => void referrals.refetch()}>
              Try again
            </Button>
          }
        >
          {referrals.error.message}
        </InlineAlert>
      </div>
    );
  }

  const data = referrals.data;
  const { stats } = data;
  const shown = data.referrals.filter((item) => filter === 'all' || groupOf(item) === filter);

  return (
    <div className={PAGE}>
      <div className="grid gap-4 lg:grid-cols-[1.3fr_1fr]">
        <ShareCard data={data} />
        <HowItWorks rules={data.rules} />
      </div>

      <section aria-label="Your referral numbers" className="grid grid-cols-2 gap-3 md:grid-cols-5">
        <StatCard label="Invited" value={stats.invited} />
        <StatCard label="In progress" value={stats.in_progress} />
        <StatCard label="Succeeded" value={stats.succeeded + stats.partial} />
        <StatCard label="Failed" value={stats.failed} />
        <StatCard label="Credits earned" value={stats.credits_earned} tone="accent" className="col-span-2 md:col-span-1" />
      </section>

      <section aria-labelledby="referrals-list" className="flex flex-col gap-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 id="referrals-list" className="text-cn-title-sm font-semibold text-cn-fg">
            Your referrals
          </h2>
          {data.referrals.length > 0 && <SegmentedControl label="Show" options={FILTERS} value={filter} onValueChange={setFilter} size="sm" />}
        </div>
        {shown.length === 0 ? (
          <EmptyState
            size="compact"
            icon={<Users />}
            title={data.referrals.length === 0 ? 'No one has joined with your code yet' : 'No referrals match this filter'}
            description={data.referrals.length === 0 ? 'Share it and they’ll show up here.' : undefined}
            action={
              data.referrals.length > 0 ? (
                <Button variant="secondary" size="sm" onClick={() => setFilter('all')}>
                  Show all
                </Button>
              ) : undefined
            }
          />
        ) : (
          <Card padding="none">
            <ul className="divide-y divide-cn-border">
              {shown.map((item) => (
                <ReferralRow key={item.id} item={item} now={now} />
              ))}
            </ul>
          </Card>
        )}
      </section>

      <ReferralRules rules={data.rules} />
    </div>
  );
}
