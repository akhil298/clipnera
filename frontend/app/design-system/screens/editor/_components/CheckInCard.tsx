'use client';

import { CirclePause, Coins } from 'lucide-react';
import { useId } from 'react';

import { Button } from '@/components/ui/Button';
import { cx } from '@/lib/design/styles';

import type { TurnView } from './run/useRunSimulator';

export type CheckInDecision = 'continue' | 'finish' | 'add_credits';

/**
 * Design-system addition: the card a run pauses on (`run.paused`). Two kinds
 * share one shape — approval ("Go ahead?") and credits (out of credits or a
 * check-in). The cost is always stated before it is spent (01 §3.10). After a
 * decision it stays in the conversation as a record.
 */
export function CheckInCard({
  pause,
  onDecide,
  className,
}: {
  pause: NonNullable<TurnView['pause']>;
  onDecide: (decision: CheckInDecision) => void;
  className?: string;
}) {
  const id = useId();
  const approval = pause.reason === 'approval';
  const decided = pause.decided;
  const title = approval
    ? 'Go ahead with this edit?'
    : pause.needed
      ? 'I paused because you’re out of credits.'
      : `This edit has used ${pause.credits.spent} credits so far.`;
  const body = approval
    ? `${pause.approval?.text ?? ''} Nothing has changed yet. Uses about ${pause.credits.estimate} credits.`.trim()
    : pause.needed
      ? `The steps already done are kept. About ${pause.needed} more credits finish it.`
      : 'Continue, or finish with what is done.';

  return (
    <section
      aria-labelledby={`${id}-title`}
      className={cx('flex flex-col gap-3 rounded-cn-lg border border-cn-border-strong bg-cn-surface p-3.5', className)}
    >
      <div className="flex items-start gap-2.5">
        <span aria-hidden className="mt-0.5 inline-flex text-cn-accent-text [&_svg]:size-[18px]">
          {approval ? <CirclePause /> : <Coins />}
        </span>
        <div className="min-w-0 space-y-1">
          <h3 id={`${id}-title`} className="text-cn-body font-semibold text-cn-fg">
            {title}
          </h3>
          <p className="text-cn-label text-cn-fg-secondary">{body}</p>
        </div>
      </div>
      {decided ? (
        <p className="ml-7 text-cn-caption text-cn-fg-muted">
          {decided === 'continue' ? 'You said go ahead.' : decided === 'add_credits' ? 'Credits added. Carrying on.' : approval ? 'You said not now.' : 'Finishing with what is done.'}
        </p>
      ) : (
        <div className="ml-7 flex flex-wrap gap-2">
          {approval ? (
            <>
              <Button size="sm" onClick={() => onDecide('continue')}>
                Go ahead · {pause.credits.estimate} credits
              </Button>
              <Button size="sm" variant="secondary" onClick={() => onDecide('finish')}>
                Not now
              </Button>
            </>
          ) : (
            <>
              {pause.options.includes('add_credits') && (
                <Button size="sm" onClick={() => onDecide('add_credits')}>
                  Add credits and continue
                </Button>
              )}
              {pause.options.includes('continue') && (
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
