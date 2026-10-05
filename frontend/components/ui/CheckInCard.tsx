'use client';

import { CirclePause, Coins } from 'lucide-react';
import { useId } from 'react';

import { cx } from '@/lib/design/styles';

import { Button } from './Button';

export type CheckInDecision = 'continue' | 'finish' | 'add_credits';

/** The `run.paused` payload (events.md §3), plus the decision once made. */
export interface CheckIn {
  reason: 'credits' | 'approval';
  credits: { estimate: number; spent: number };
  /** Credits still needed to finish, when the run stopped for lack of them. */
  needed?: number;
  /** What needs approval, in plain words: "This removes 54% of the clip." */
  approval?: { text: string };
  options: ReadonlyArray<CheckInDecision>;
  /** Set after the person chose; the card stays as a record. */
  decided?: CheckInDecision;
}

export interface CheckInCardProps {
  checkIn: CheckIn;
  onDecide: (decision: CheckInDecision) => void;
  className?: string;
}

const DECIDED: Record<CheckIn['reason'], Record<CheckInDecision, string>> = {
  approval: { continue: 'You said go ahead.', add_credits: 'Credits added. Carrying on.', finish: 'You said not now.' },
  credits: { continue: 'Carrying on.', add_credits: 'Credits added. Carrying on.', finish: 'Finishing with what’s done.' },
};

/**
 * The card a run pauses on. Two kinds share one shape: approval ("Go ahead?")
 * and credits (ran out, or a spend check-in). The cost is stated before it is
 * spent (01 §3.10). After a decision it stays in the thread as a record.
 */
export function CheckInCard({ checkIn, onDecide, className }: CheckInCardProps) {
  const id = useId();
  const { reason, credits, needed, approval, options, decided } = checkIn;
  const isApproval = reason === 'approval';
  const title = isApproval
    ? 'Go ahead with this edit?'
    : needed
      ? 'I paused because you’re out of credits.'
      : `This edit has used ${credits.spent} credits so far.`;
  const body = isApproval
    ? `${approval?.text ?? ''} Nothing has changed yet. Uses about ${credits.estimate} credits.`.trim()
    : needed
      ? `The steps already done are kept. About ${needed} more credits finish it.`
      : 'Continue, or finish with what’s done.';

  return (
    <section aria-labelledby={`${id}-title`} className={cx('flex flex-col gap-3 rounded-cn-lg border border-cn-border-strong bg-cn-surface p-3', className)}>
      <div className="flex items-start gap-2.5">
        <span aria-hidden className="mt-0.5 inline-flex text-cn-accent-text [&_svg]:size-4">
          {isApproval ? <CirclePause /> : <Coins />}
        </span>
        <div className="min-w-0 space-y-1">
          <h3 id={`${id}-title`} className="text-cn-label font-semibold text-cn-fg">
            {title}
          </h3>
          <p className="text-cn-label text-cn-fg-secondary">{body}</p>
        </div>
      </div>
      {decided ? (
        <p className="ml-6 text-cn-caption text-cn-fg-muted">{DECIDED[reason][decided]}</p>
      ) : (
        <div className="ml-6 flex flex-wrap gap-2">
          {isApproval ? (
            <>
              <Button size="sm" onClick={() => onDecide('continue')}>
                Go ahead · {credits.estimate} credits
              </Button>
              <Button size="sm" variant="secondary" onClick={() => onDecide('finish')}>
                Not now
              </Button>
            </>
          ) : (
            <>
              {options.includes('add_credits') && (
                <Button size="sm" onClick={() => onDecide('add_credits')}>
                  Add credits and continue
                </Button>
              )}
              {options.includes('continue') && !options.includes('add_credits') && (
                <Button size="sm" onClick={() => onDecide('continue')}>
                  Continue
                </Button>
              )}
              <Button size="sm" variant="secondary" onClick={() => onDecide('finish')}>
                Finish with what’s done
              </Button>
            </>
          )}
        </div>
      )}
    </section>
  );
}
