'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { Check, Copy, Gift, Loader2, X } from 'lucide-react';
import { referralApi } from '@/lib/api';
import {
  OPEN_REFERRAL_STATUSES,
  REFERRAL_FAIL_LABELS,
  REFERRAL_STATUS_LABELS,
  isUrgent,
  shortDate,
  timeLeft,
} from '@/lib/referral';
import type { MyReferralsResponse, ReferralItem, ReferralRules } from '@/lib/types';

type Filter = 'all' | 'open' | 'done' | 'failed';

const FILTERS: { id: Filter; label: string }[] = [
  { id: 'all', label: 'All' },
  { id: 'open', label: 'In progress' },
  { id: 'done', label: 'Completed' },
  { id: 'failed', label: 'Failed' },
];

function group(item: ReferralItem): Exclude<Filter, 'all'> {
  if (OPEN_REFERRAL_STATUSES.includes(item.status)) return 'open';
  return item.status === 'succeeded' || item.status === 'partial' ? 'done' : 'failed';
}

function useNow(intervalMs = 30_000): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), intervalMs);
    return () => window.clearInterval(id);
  }, [intervalMs]);
  return now;
}

function CopyButton({ text, label, primary = false }: { text: string; label: string; primary?: boolean }) {
  const [copied, setCopied] = useState(false);
  const copy = () => {
    navigator.clipboard?.writeText(text).then(
      () => {
        setCopied(true);
        window.setTimeout(() => setCopied(false), 1500);
      },
      () => setCopied(false),
    );
  };
  return (
    <button
      type="button"
      onClick={copy}
      className={`inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-sm font-bold border transition-colors ${
        primary
          ? 'bg-amber-500 border-amber-500 text-neutral-950 hover:bg-amber-400'
          : 'bg-neutral-900 border-neutral-800 text-neutral-200 hover:border-neutral-700'
      }`}
    >
      {copied ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
      {copied ? 'Copied' : label}
    </button>
  );
}

/** One milestone dot on a referral's track. */
function Stop({ state, label, gain }: { state: 'done' | 'live' | 'miss' | 'todo'; label: string; gain?: string }) {
  const dot = {
    done: 'bg-emerald-400 border-emerald-400 text-emerald-950',
    live: 'border-amber-500 text-amber-400',
    miss: 'border-rose-400 bg-rose-500/10 text-rose-400',
    todo: 'border-neutral-800 text-neutral-600',
  }[state];
  return (
    <div className="flex flex-col items-center gap-0.5 text-[11px] text-neutral-500 text-center">
      <span className={`w-[22px] h-[22px] rounded-full border-2 grid place-items-center ${dot}`}>
        {state === 'done' && <Check className="w-3 h-3" strokeWidth={3} />}
        {state === 'miss' && <X className="w-3 h-3" strokeWidth={3} />}
      </span>
      <span>{label}</span>
      {gain && <span className={`font-jetbrains text-[10px] ${state === 'done' ? 'text-emerald-400' : 'text-amber-400'}`}>{gain}</span>}
    </div>
  );
}

function Track({ item }: { item: ReferralItem }) {
  const pro = item.pro_activated_at ? 'done' : item.status === 'failed' || item.status === 'void' ? 'miss' : 'live';
  const video =
    item.status === 'succeeded' ? 'done'
      : item.status === 'pending_video' ? 'live'
        : item.status === 'partial' ? 'miss'
          : 'todo';
  const proGain = pro === 'miss' ? undefined : `+${item.rules.referrer_pro_credits}`;
  const videoGain = video === 'miss' || pro === 'miss' ? undefined : `+${item.rules.referrer_video_credits}`;
  const line = (on: boolean) => <span className={`h-0.5 rounded ${on ? 'bg-emerald-400' : 'bg-neutral-800'}`} />;
  return (
    <div className="grid grid-cols-[auto_minmax(16px,1fr)_auto_minmax(16px,1fr)_auto] items-center gap-1.5 min-w-0">
      <Stop state="done" label="Signed up" />
      {line(pro === 'done')}
      <Stop state={pro} label="Pro" gain={proGain} />
      {line(video === 'done')}
      <Stop state={video} label="Video" gain={videoGain} />
    </div>
  );
}

function Outcome({ item, now }: { item: ReferralItem; now: number }) {
  const earned = item.rewards.reduce((sum, r) => sum + r.credits, 0);
  const deadline = item.status === 'pending_video' ? item.video_deadline_at : item.pro_deadline_at;
  if (OPEN_REFERRAL_STATUSES.includes(item.status)) {
    const left = item.status === 'awaiting_approval' ? null : timeLeft(deadline, now);
    return (
      <div className="flex flex-col items-start sm:items-end gap-1">
        <span className="px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-amber-500/10 text-amber-300">
          {REFERRAL_STATUS_LABELS[item.status]}
        </span>
        {left && <span className={`font-jetbrains text-xs ${isUrgent(deadline, now) ? 'text-rose-400' : 'text-amber-300'}`}>{left}</span>}
        {item.on_hold && <span className="text-xs text-neutral-500">Rewards on hold for a review</span>}
      </div>
    );
  }
  const tone =
    item.status === 'succeeded' ? 'bg-emerald-500/10 text-emerald-400'
      : item.status === 'partial' ? 'bg-neutral-800 text-neutral-300'
        : 'bg-rose-500/10 text-rose-400';
  return (
    <div className="flex flex-col items-start sm:items-end gap-1">
      <span className={`px-2.5 py-0.5 rounded-full text-[11px] font-bold ${tone}`}>{REFERRAL_STATUS_LABELS[item.status]}</span>
      <span className="text-xs text-neutral-500">
        {item.fail_reason ? REFERRAL_FAIL_LABELS[item.fail_reason] : ''}
        {earned > 0 ? `${item.fail_reason ? ' · ' : ''}+${earned} credits` : ''}
      </span>
    </div>
  );
}

function Rules({ rules }: { rules: ReferralRules }) {
  const minutes = Math.max(1, Math.round(rules.min_video_seconds / 60));
  return (
    <details className="rounded-2xl border border-neutral-800 bg-neutral-900/70 group" open>
      <summary className="px-4 py-3.5 font-bold cursor-pointer list-none flex justify-between">
        Referral rules
        <span className="text-xs font-semibold text-neutral-500 group-open:hidden">Show</span>
        <span className="text-xs font-semibold text-neutral-500 hidden group-open:inline">Hide</span>
      </summary>
      <div className="px-4 pb-4 grid md:grid-cols-2 gap-5 text-sm text-neutral-400">
        <div className="space-y-2">
          <h3 className="text-[11px] font-semibold uppercase tracking-wider text-neutral-500">How rewards are earned</h3>
          <ul className="list-disc pl-4 space-y-1.5">
            <li>Your friend must enter your code when they <b className="text-neutral-200">create a new account</b>. Existing accounts can&apos;t be referred.</li>
            <li>They must buy Pro within <b className="text-neutral-200">{rules.pro_window_hours} hours</b> of signing up. A payment made in time counts once it&apos;s approved, if approval comes within {rules.approval_wait_days} days.</li>
            <li>They must start processing a video of at least <b className="text-neutral-200">{minutes} minute{minutes > 1 ? 's' : ''}</b> within <b className="text-neutral-200">{rules.video_window_hours} hours</b> of their Pro starting. It counts once it finishes successfully.</li>
            <li>You get <b className="text-neutral-200">{rules.referrer_pro_credits} + {rules.referrer_video_credits}</b> credits; your friend gets <b className="text-neutral-200">{rules.referee_pro_credits}</b> when they buy Pro. If they never process a video, you keep the first {rules.referrer_pro_credits}.</li>
            <li>Referral credits <b className="text-neutral-200">expire {rules.bonus_expiry_days} days</b> after you get them, and are used first when they&apos;d run out before your other credits.</li>
            <li>You can bring in up to <b className="text-neutral-200">{rules.monthly_cap} people a month</b>.</li>
          </ul>
        </div>
        <div className="space-y-2">
          <h3 className="text-[11px] font-semibold uppercase tracking-wider text-neutral-500">Why a referral can fail</h3>
          <ul className="list-disc pl-4 space-y-1.5">
            <li><b className="text-neutral-200">Pro not bought in time:</b> no Pro payment within {rules.pro_window_hours} hours of sign-up.</li>
            <li><b className="text-neutral-200">Payment rejected</b>, or <b className="text-neutral-200">not approved in time</b>.</li>
            <li><b className="text-neutral-200">No video in time:</b> no video started within {rules.video_window_hours} hours of Pro. Your first reward stays.</li>
            <li><b className="text-neutral-200">Payment reversed:</b> the Pro payment was refunded, so unspent reward credits are taken back.</li>
            <li><b className="text-neutral-200">Under review:</b> sign-ups that look like your own second account wait for a manual check before anything is paid.</li>
            <li>Using your own code, or an email that was referred before, isn&apos;t allowed. Credits have no cash value.</li>
          </ul>
        </div>
      </div>
    </details>
  );
}

/** Refer & earn: the user's code, how it works, and everyone they referred. */
export function ReferralsView() {
  const [data, setData] = useState<MyReferralsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<Filter>('all');
  const now = useNow();

  const load = useCallback(() => {
    referralApi.mine().then(setData).catch((err) => setError(err instanceof Error ? err.message : 'Could not load referrals.'));
  }, []);
  useEffect(load, [load]);

  const shown = useMemo(
    () => (data?.referrals ?? []).filter((item) => filter === 'all' || group(item) === filter),
    [data, filter],
  );

  if (error) return <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-sm">{error}</div>;
  if (!data) {
    return (
      <div className="flex items-center gap-2 text-neutral-500 text-sm p-6">
        <Loader2 className="w-4 h-4 animate-spin" /> Loading referrals…
      </div>
    );
  }

  const { rules, stats } = data;
  const total = rules.referrer_pro_credits + rules.referrer_video_credits;
  const shareText = data.code && data.share_url ? `Try Clipnera with my code ${data.code}: ${data.share_url}` : '';
  const capPercent = rules.monthly_cap ? Math.min(100, (data.used_this_month / rules.monthly_cap) * 100) : 100;

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <div className="grid lg:grid-cols-[1.3fr_1fr] gap-4">
        <section className="rounded-2xl border border-amber-500/20 bg-gradient-to-br from-[#1b1407] to-neutral-900 p-5 space-y-4">
          <p className="text-[11px] font-semibold uppercase tracking-wider text-amber-400 inline-flex items-center gap-1.5">
            <Gift className="w-3.5 h-3.5" /> Refer &amp; earn
          </p>
          <h1 className="font-syne text-2xl sm:text-[26px] font-bold leading-tight text-white">
            Earn <span className="text-amber-400">{total} credits</span> for every friend who goes Pro and makes their first clips
          </h1>
          <p className="text-neutral-400">Your friend gets {rules.referee_pro_credits} bonus credits when they buy Pro.</p>

          {data.enabled && data.code && data.share_url ? (
            <>
              <div className="flex items-center gap-2 rounded-xl border border-dashed border-amber-500/45 bg-neutral-950 pl-3.5 pr-2 py-2">
                <span className="flex-1 min-w-0 truncate font-jetbrains text-lg font-bold tracking-widest text-amber-400">{data.code}</span>
                <CopyButton text={data.code} label="Copy code" primary />
              </div>
              <p className="font-jetbrains text-xs text-neutral-500 break-all">{data.share_url}</p>
              <div className="flex flex-wrap gap-2">
                <CopyButton text={data.share_url} label="Copy link" />
                <a
                  href={`https://wa.me/?text=${encodeURIComponent(shareText)}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="px-3.5 py-2 rounded-xl text-sm font-bold border border-neutral-800 bg-neutral-900 text-neutral-200 hover:border-neutral-700"
                >
                  WhatsApp
                </a>
                <a
                  href={`https://x.com/intent/post?text=${encodeURIComponent(shareText)}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="px-3.5 py-2 rounded-xl text-sm font-bold border border-neutral-800 bg-neutral-900 text-neutral-200 hover:border-neutral-700"
                >
                  Post on X
                </a>
              </div>
              <div className="space-y-1.5 text-xs text-neutral-400">
                <div className="flex justify-between">
                  <span>Referrals used this month</span>
                  <b className="text-white tabular-nums">{data.used_this_month} of {rules.monthly_cap}</b>
                </div>
                <div className="h-1.5 rounded-full bg-neutral-800 overflow-hidden">
                  <div className="h-full bg-amber-500" style={{ width: `${capPercent}%` }} />
                </div>
              </div>
            </>
          ) : (
            <p className="rounded-xl border border-neutral-800 bg-neutral-950 px-3.5 py-3 text-sm text-neutral-400">
              Referrals are paused right now. Referrals already in progress still finish and pay out.
            </p>
          )}
        </section>

        <section className="rounded-2xl border border-neutral-800 bg-neutral-900/70 p-5 space-y-3">
          <h2 className="text-sm font-bold text-white">How it works</h2>
          <ol className="space-y-3">
            {[
              ['Your friend signs up with your code', 'They enter it on the welcome form, or open your link.', ''],
              [`They buy Pro within ${rules.pro_window_hours} hours`, 'Counted from when they sign up.', `you +${rules.referrer_pro_credits}\nthem +${rules.referee_pro_credits}`],
              [`They process a video within ${rules.video_window_hours} hours of Pro`, 'Paid when that video finishes processing.', `you +${rules.referrer_video_credits}`],
            ].map(([title, sub, earn], i) => (
              <li key={title} className="grid grid-cols-[28px_1fr_auto] gap-2.5 items-start">
                <span className="w-7 h-7 rounded-full border border-neutral-800 grid place-items-center text-xs font-bold text-neutral-400">{i + 1}</span>
                <div>
                  <p className="font-semibold text-neutral-100 text-sm">{title}</p>
                  <p className="text-xs text-neutral-500">{sub}</p>
                </div>
                <span className="font-jetbrains text-xs text-amber-400 whitespace-pre text-right">{earn}</span>
              </li>
            ))}
          </ol>
          <p className="text-xs text-neutral-500">Bonus credits expire {rules.bonus_expiry_days} days after you get them.</p>
        </section>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-5 rounded-2xl border border-neutral-800 overflow-hidden tabular-nums">
        {[
          ['Invited', stats.invited],
          ['In progress', stats.in_progress],
          ['Succeeded', stats.succeeded + stats.partial],
          ['Failed', stats.failed],
        ].map(([label, value]) => (
          <div key={label} className="bg-neutral-900 p-4 border-r border-b md:border-b-0 border-neutral-800">
            <p className="text-2xl font-extrabold text-white">{value}</p>
            <p className="text-[11px] font-semibold uppercase tracking-wider text-neutral-500">{label}</p>
          </div>
        ))}
        <div className="bg-neutral-900 p-4 col-span-2 md:col-span-1">
          <p className="text-2xl font-extrabold text-amber-400">{stats.credits_earned}</p>
          <p className="text-[11px] font-semibold uppercase tracking-wider text-neutral-500">Credits earned</p>
        </div>
      </div>

      <section className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-sm font-bold text-white">Your referrals</h2>
          <div className="flex flex-wrap gap-1.5">
            {FILTERS.map((f) => (
              <button
                key={f.id}
                type="button"
                aria-pressed={filter === f.id}
                onClick={() => setFilter(f.id)}
                className={`px-3 py-1 rounded-full text-xs font-semibold border ${
                  filter === f.id ? 'bg-white text-neutral-950 border-white' : 'border-neutral-800 text-neutral-400 hover:text-white'
                }`}
              >
                {f.label}
              </button>
            ))}
          </div>
        </div>
        {shown.length === 0 ? (
          <p className="rounded-2xl border border-dashed border-neutral-800 p-6 text-sm text-neutral-500 text-center">
            {data.referrals.length === 0
              ? 'No one has joined with your code yet. Share it and they’ll show up here.'
              : 'No referrals match this filter.'}
          </p>
        ) : (
          <div className="rounded-2xl border border-neutral-800 overflow-hidden divide-y divide-neutral-800">
            {shown.map((item) => (
              <div key={item.id} className="grid sm:grid-cols-[minmax(140px,1.1fr)_minmax(0,2fr)_minmax(140px,auto)] gap-3 sm:gap-4 items-center bg-neutral-900 px-4 py-3.5">
                <div className="min-w-0">
                  <p className="font-semibold text-white truncate">{item.name}</p>
                  <p className="text-xs text-neutral-500 truncate">{item.email_masked} · joined {shortDate(item.signed_up_at)}</p>
                </div>
                <Track item={item} />
                <Outcome item={item} now={now} />
              </div>
            ))}
          </div>
        )}
      </section>

      <Rules rules={rules} />
    </div>
  );
}
