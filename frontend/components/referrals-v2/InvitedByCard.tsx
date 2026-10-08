'use client';

import { useQuery } from '@tanstack/react-query';
import { Check, Gift } from 'lucide-react';
import Link from 'next/link';
import { type ReactNode, useEffect, useState } from 'react';

import { BILLING_HREF } from '@/components/shell/nav';
import { Badge, Button, buttonClasses, Card } from '@/components/ui';
import { getInvitedBy } from '@/lib/api/referrals';
import { cx } from '@/lib/design/styles';
import { referralKeys } from '@/lib/query/keys/referrals';
import { isUrgent, OPEN_REFERRAL_STATUSES, REFERRAL_FAIL_LABELS, shortDate, timeLeft } from '@/lib/referral';
import type { InvitedByResponse } from '@/lib/types';
import { parseApiDate } from '@/lib/utils/dates';

import { useMinuteClock } from './useMinuteClock';

/** An ended referral's outcome stays on Home this long, unless dismissed. */
const SHOW_OUTCOME_MS = 7 * 24 * 3_600_000;
/** Same key as the legacy card, so a dismissal holds in both UIs. */
const DISMISSED_KEY = 'clipnera_referral_card_dismissed';

function readDismissed(): boolean {
  try {
    return localStorage.getItem(DISMISSED_KEY) === '1';
  } catch {
    return false;
  }
}

interface CardCopy {
  badge: ReactNode;
  title: string;
  body: ReactNode;
  /** The Pro offer is still open. */
  offer?: boolean;
  /** The referral has ended, so the card can be put away. */
  ended?: boolean;
}

function copyFor(referral: InvitedByResponse, now: number): CardCopy {
  const invited = <Badge tone="accent">Invited by {referral.referrer_name}</Badge>;
  if (referral.reward) {
    return {
      badge: <Badge tone="success">Bonus earned</Badge>,
      title: `+${referral.reward.credits} bonus credits added`,
      body: `Thanks for joining through ${referral.referrer_name}’s invite. Your bonus credits expire on ${shortDate(referral.reward.expires_at)}.`,
      ended: true,
    };
  }
  if (referral.status === 'pending_pro') {
    const urgent = isUrgent(referral.pro_deadline_at, now);
    return {
      badge: invited,
      title: `Get ${referral.bonus_credits} bonus credits with Pro`,
      body: (
        <>
          Buy Pro within{' '}
          <b className={cx('font-cn-mono font-semibold', urgent ? 'text-cn-danger-text' : 'text-cn-accent-text')}>
            {timeLeft(referral.pro_deadline_at, now) ?? 'the next few minutes'}
          </b>{' '}
          and {referral.bonus_credits} bonus credits are added to your account.
        </>
      ),
      offer: true,
    };
  }
  if (referral.status === 'awaiting_approval') {
    return {
      badge: invited,
      title: 'Payment received, waiting for approval',
      body: `You paid in time, so your ${referral.bonus_credits} bonus credits arrive as soon as the payment is approved.`,
    };
  }
  if (referral.pro_activated_at && referral.status !== 'failed' && referral.status !== 'void') {
    return {
      badge: invited,
      title: 'Your bonus is on its way',
      body: `You bought Pro in time. Your ${referral.bonus_credits} bonus credits are being processed and will appear soon.`,
    };
  }
  return {
    badge: <Badge tone="danger">Referral ended</Badge>,
    title: 'The bonus window has closed',
    body: `${referral.fail_reason ? REFERRAL_FAIL_LABELS[referral.fail_reason] : 'This referral has ended'}, so the bonus credits weren’t added. You can still buy Pro any time.`,
    ended: true,
  };
}

/**
 * For someone who joined with a referral code (parity with the legacy
 * InvitedByCard): what buying Pro in time earns and how long is left, then how
 * it turned out. Never shows the referrer's own rewards.
 */
export function InvitedByCard() {
  const invitedBy = useQuery({ queryKey: referralKeys.invitedBy(), queryFn: ({ signal }) => getInvitedBy(signal), staleTime: 5 * 60_000 });
  const [dismissed, setDismissed] = useState(true);
  const now = useMinuteClock();
  useEffect(() => setDismissed(readDismissed()), []);

  const referral = invitedBy.data;
  if (!referral) return null;
  const open = OPEN_REFERRAL_STATUSES.includes(referral.status);
  const endedAt = referral.reward?.granted_at ?? referral.pro_deadline_at;
  if (!open && (dismissed || now - parseApiDate(endedAt).getTime() > SHOW_OUTCOME_MS)) return null;

  const dismiss = () => {
    try {
      localStorage.setItem(DISMISSED_KEY, '1');
    } catch {
      // Hidden for this visit only.
    }
    setDismissed(true);
  };

  const { badge, title, body, offer, ended } = copyFor(referral, now);
  return (
    <Card padding="lg" className="grid items-center gap-4 border-cn-accent/30 sm:grid-cols-[1fr_auto]">
      <section aria-label="Referral bonus" className="flex min-w-0 flex-col gap-1.5">
        <div className="flex items-center gap-2">
          <Gift aria-hidden className="size-4 text-cn-accent-text" />
          {badge}
        </div>
        <h2 className="text-cn-body-lg font-semibold text-cn-fg">{title}</h2>
        <p className="text-cn-body text-cn-fg-secondary">{body}</p>
        {open && (
          <ul className="flex flex-wrap gap-x-4 gap-y-1 pt-1 text-cn-caption">
            <li className="inline-flex items-center gap-1.5 text-cn-success-text">
              <Check aria-hidden className="size-3.5" /> Signed up with a code
            </li>
            {referral.status === 'awaiting_approval' ? (
              <li className="inline-flex items-center gap-1.5 text-cn-success-text">
                <Check aria-hidden className="size-3.5" /> Paid for Pro in time
              </li>
            ) : (
              <li className="font-semibold text-cn-accent-text">Next: buy Pro</li>
            )}
          </ul>
        )}
      </section>
      {offer && (
        <Link href={BILLING_HREF} className={buttonClasses({ variant: 'primary' })}>
          Get Pro
        </Link>
      )}
      {ended && (
        <Button variant="secondary" onClick={dismiss}>
          Dismiss
        </Button>
      )}
    </Card>
  );
}
