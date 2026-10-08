import { Check, X } from 'lucide-react';

import { Badge, type BadgeTone } from '@/components/ui';
import { cx } from '@/lib/design/styles';
import { isUrgent, OPEN_REFERRAL_STATUSES, REFERRAL_FAIL_LABELS, REFERRAL_STATUS_LABELS, shortDate, timeLeft } from '@/lib/referral';
import type { ReferralItem } from '@/lib/types';

type StopState = 'done' | 'live' | 'miss' | 'todo';

const DOT: Record<StopState, string> = {
  done: 'border-cn-success bg-cn-success-subtle text-cn-success-text',
  live: 'border-cn-accent text-cn-accent-text',
  miss: 'border-cn-danger bg-cn-danger-subtle text-cn-danger-text',
  todo: 'border-cn-border text-cn-fg-muted',
};

/** One milestone on a referral's track; the words carry the state, the colour only repeats it. */
function Stop({ state, label, gain }: { state: StopState; label: string; gain?: string }) {
  const word = { done: 'done', live: 'in progress', miss: 'missed', todo: 'not yet' }[state];
  return (
    <div className="flex flex-col items-center gap-0.5 text-center text-cn-caption text-cn-fg-muted">
      <span aria-hidden className={cx('grid size-5 place-items-center rounded-cn-full border-2', DOT[state])}>
        {state === 'done' && <Check className="size-3" strokeWidth={3} />}
        {state === 'miss' && <X className="size-3" strokeWidth={3} />}
      </span>
      <span>
        {label}
        <span className="sr-only">: {word}</span>
      </span>
      {gain && <span className={cx('font-cn-mono', state === 'done' ? 'text-cn-success-text' : 'text-cn-accent-text')}>{gain}</span>}
    </div>
  );
}

function Track({ item }: { item: ReferralItem }) {
  const pro: StopState = item.pro_activated_at ? 'done' : item.status === 'failed' || item.status === 'void' ? 'miss' : 'live';
  const video: StopState =
    item.status === 'succeeded' ? 'done' : item.status === 'pending_video' ? 'live' : item.status === 'partial' ? 'miss' : 'todo';
  const line = (on: boolean) => <span aria-hidden className={cx('h-0.5 rounded-cn-full', on ? 'bg-cn-success' : 'bg-cn-border')} />;
  return (
    <div className="grid min-w-0 grid-cols-[auto_minmax(1rem,1fr)_auto_minmax(1rem,1fr)_auto] items-center gap-1.5">
      <Stop state="done" label="Signed up" />
      {line(pro === 'done')}
      <Stop state={pro} label="Pro" gain={pro === 'miss' ? undefined : `+${item.rules.referrer_pro_credits}`} />
      {line(video === 'done')}
      <Stop state={video} label="Video" gain={video === 'miss' || pro === 'miss' ? undefined : `+${item.rules.referrer_video_credits}`} />
    </div>
  );
}

function Outcome({ item, now }: { item: ReferralItem; now: number }) {
  if (OPEN_REFERRAL_STATUSES.includes(item.status)) {
    const deadline = item.status === 'pending_video' ? item.video_deadline_at : item.pro_deadline_at;
    const left = item.status === 'awaiting_approval' ? null : timeLeft(deadline, now);
    return (
      <div className="flex flex-col items-start gap-1 sm:items-end">
        <Badge tone="accent">{REFERRAL_STATUS_LABELS[item.status]}</Badge>
        {left && <span className={cx('font-cn-mono text-cn-caption', isUrgent(deadline, now) ? 'text-cn-danger-text' : 'text-cn-accent-text')}>{left}</span>}
        {item.on_hold && <span className="text-cn-caption text-cn-fg-muted">Rewards on hold for a review</span>}
      </div>
    );
  }
  const earned = item.rewards.reduce((sum, reward) => sum + reward.credits, 0);
  const tone: BadgeTone = item.status === 'succeeded' ? 'success' : item.status === 'partial' ? 'neutral' : 'danger';
  const detail = [item.fail_reason && REFERRAL_FAIL_LABELS[item.fail_reason], earned > 0 && `+${earned} credits`].filter(Boolean).join(' · ');
  return (
    <div className="flex flex-col items-start gap-1 sm:items-end">
      <Badge tone={tone}>{REFERRAL_STATUS_LABELS[item.status]}</Badge>
      {detail && <span className="text-cn-caption text-cn-fg-muted">{detail}</span>}
    </div>
  );
}

/** One person the caller referred: who, how far they got, and how it turned out. */
export function ReferralRow({ item, now }: { item: ReferralItem; now: number }) {
  return (
    <li className="grid items-center gap-3 px-4 py-3.5 sm:grid-cols-[minmax(8rem,1.1fr)_minmax(0,2fr)_minmax(8rem,auto)] sm:gap-4">
      <div className="min-w-0">
        <p className="truncate text-cn-body font-semibold text-cn-fg">{item.name}</p>
        <p className="truncate text-cn-caption text-cn-fg-muted">
          {item.email_masked} · joined {shortDate(item.signed_up_at)}
        </p>
      </div>
      <Track item={item} />
      <Outcome item={item} now={now} />
    </li>
  );
}
