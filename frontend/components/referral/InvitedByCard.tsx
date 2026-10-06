'use client';

import { useEffect, useState } from 'react';
import { Check, Gift } from 'lucide-react';
import { referralApi } from '@/lib/api';
import { OPEN_REFERRAL_STATUSES, REFERRAL_FAIL_LABELS, isUrgent, shortDate, timeLeft } from '@/lib/referral';
import type { InvitedByResponse } from '@/lib/types';
import { parseApiDate } from '@/lib/utils/dates';

// An ended referral's outcome stays on Home this long, unless dismissed.
const SHOW_OUTCOME_MS = 7 * 24 * 3_600_000;
const DISMISSED_KEY = 'clipnera_referral_card_dismissed';

function dismissed(): boolean {
  try {
    return localStorage.getItem(DISMISSED_KEY) === '1';
  } catch {
    return false;
  }
}

/**
 * For someone who joined with a referral code: what they get for buying Pro
 * and how long is left, then how it turned out. Never shows the referrer's
 * own rewards.
 */
export function InvitedByCard({ onGetPro }: { onGetPro: () => void }) {
  const [referral, setReferral] = useState<InvitedByResponse | null>(null);
  const [hidden, setHidden] = useState(true);
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    setHidden(dismissed());
    referralApi.invitedBy().then(setReferral).catch(() => setReferral(null));
    const id = window.setInterval(() => setNow(Date.now()), 30_000);
    return () => window.clearInterval(id);
  }, []);

  if (!referral) return null;
  const open = OPEN_REFERRAL_STATUSES.includes(referral.status);
  const endedAt = referral.reward?.granted_at ?? referral.pro_deadline_at;
  if (!open && (hidden || now - parseApiDate(endedAt).getTime() > SHOW_OUTCOME_MS)) return null;

  const dismiss = () => {
    try {
      localStorage.setItem(DISMISSED_KEY, '1');
    } catch {
      // Hidden for this visit only.
    }
    setHidden(true);
  };

  let badge: React.ReactNode;
  let title: string;
  let body: React.ReactNode;
  let action: React.ReactNode = (
    <button type="button" onClick={dismiss} className="h-9 px-3.5 rounded-xl border border-neutral-700 bg-neutral-900 text-sm font-semibold text-white">
      Dismiss
    </button>
  );

  if (referral.reward) {
    badge = <span className="px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-emerald-500/10 text-emerald-400">Bonus earned</span>;
    title = `+${referral.reward.credits} bonus credits added`;
    body = <>Thanks for joining through {referral.referrer_name}&apos;s invite. Your bonus credits expire on {shortDate(referral.reward.expires_at)}.</>;
  } else if (referral.status === 'pending_pro') {
    const left = timeLeft(referral.pro_deadline_at, now);
    badge = <span className="px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-amber-500/10 text-amber-300">Invited by {referral.referrer_name}</span>;
    title = `Get ${referral.bonus_credits} bonus credits with Pro`;
    body = (
      <>
        Buy Pro within{' '}
        <b className={`font-jetbrains ${isUrgent(referral.pro_deadline_at, now) ? 'text-rose-400' : 'text-amber-300'}`}>{left ?? 'the next few minutes'}</b>{' '}
        and {referral.bonus_credits} bonus credits are added to your account.
      </>
    );
    action = (
      <button type="button" onClick={onGetPro} className="h-9 px-4 rounded-xl bg-amber-500 hover:bg-amber-400 text-neutral-950 text-sm font-bold">
        Get Pro
      </button>
    );
  } else if (referral.status === 'awaiting_approval') {
    badge = <span className="px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-amber-500/10 text-amber-300">Invited by {referral.referrer_name}</span>;
    title = 'Payment received, waiting for approval';
    body = <>You paid in time, so your {referral.bonus_credits} bonus credits arrive as soon as the payment is approved.</>;
    action = null;
  } else if (referral.pro_activated_at && referral.status !== 'failed' && referral.status !== 'void') {
    badge = <span className="px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-amber-500/10 text-amber-300">Invited by {referral.referrer_name}</span>;
    title = 'Your bonus is on its way';
    body = <>You bought Pro in time. Your {referral.bonus_credits} bonus credits are being processed and will appear soon.</>;
    action = null;
  } else {
    badge = <span className="px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-rose-500/10 text-rose-400">Referral ended</span>;
    title = 'The bonus window has closed';
    body = (
      <>
        {referral.fail_reason ? REFERRAL_FAIL_LABELS[referral.fail_reason] : 'This referral has ended'}, so the bonus credits
        weren&apos;t added. You can still buy Pro any time.
      </>
    );
  }

  return (
    <section className="rounded-2xl border border-amber-500/25 bg-neutral-900/80 p-4 sm:p-5 grid sm:grid-cols-[1fr_auto] gap-4 items-center" aria-label="Referral bonus">
      <div className="min-w-0 space-y-1.5">
        <div className="flex items-center gap-2">
          <Gift className="w-4 h-4 text-amber-400" />
          {badge}
        </div>
        <h2 className="text-base font-bold text-white">{title}</h2>
        <p className="text-sm text-neutral-400">{body}</p>
        {open && (
          <div className="flex flex-wrap gap-x-4 gap-y-1 pt-1 text-[13px]">
            <span className="inline-flex items-center gap-1.5 text-emerald-400"><Check className="w-3.5 h-3.5" /> Signed up with a code</span>
            <span className={referral.status === 'awaiting_approval' ? 'inline-flex items-center gap-1.5 text-emerald-400' : 'font-semibold text-amber-300'}>
              {referral.status === 'awaiting_approval' ? <><Check className="w-3.5 h-3.5" /> Paid for Pro in time</> : '● Buy Pro'}
            </span>
          </div>
        )}
      </div>
      {action}
    </section>
  );
}
