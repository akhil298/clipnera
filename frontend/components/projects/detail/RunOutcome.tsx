'use client';

import { Play, RotateCcw } from 'lucide-react';

import { InlineAlert } from '@/components/ui/Alert';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { ResultMessage } from '@/components/ui/ResultMessage';
import { WorkingText } from '@/components/ui/WorkingText';
import type { ProjectClip } from '@/lib/api/clips';
import { isApiError, isPlanError } from '@/lib/api/errors';
import type { PipelineStepLog, ProjectCredits } from '@/lib/api/jobs';
import { formatTimecode } from '@/lib/design/timecode';
import { stepWords } from '@/lib/projects/run';

import { formatTagOf } from './moments';
import { elapsedSeconds, type Phase, runSteps } from './run';

export interface RunOutcomeProps {
  phase: Extract<Phase, 'done' | 'failed' | 'stopped' | 'not_started'>;
  title: string;
  steps: readonly PipelineStepLog[];
  /** Undefined while the clips are still loading. */
  clips?: readonly ProjectClip[];
  sourceSeconds: number;
  credits?: ProjectCredits;
  onRetry: () => void;
  retrying: boolean;
  retryError: unknown;
  onStart: () => void;
  starting: boolean;
  startError: unknown;
}

const plural = (count: number, word: string) => `${count} ${word}${count === 1 ? '' : 's'}`;

function ActionError({ error }: { error: unknown }) {
  if (!error) return null;
  // Plan errors open the upgrade dialog on their own; say so in place too.
  const text = isPlanError(error)
    ? `${error.message} Add credits or change your plan, then try again.`
    : isApiError(error)
      ? `${error.message} Nothing was charged for this attempt.`
      : 'That didn’t go through. Nothing was charged for this attempt.';
  return (
    <InlineAlert tone="danger" live="alert">
      {text}
    </InlineAlert>
  );
}

/** Counted summary lines for a finished run: real numbers only. */
function doneChanges(steps: readonly PipelineStepLog[], clips: readonly ProjectClip[] | undefined): string[] {
  const lines: string[] = [];
  const took = elapsedSeconds(steps, Date.now());
  if (steps.length) lines.push(took !== null ? `Ran ${plural(steps.length, 'step')} in ${formatTimecode(took)}` : `Ran ${plural(steps.length, 'step')}`);
  if (clips?.length) {
    const scores = clips.map((clip) => clip.score).filter((score): score is number => typeof score === 'number');
    if (scores.length) lines.push(`Best score ${Math.round(Math.max(...scores))}, ${plural(scores.filter((score) => score >= 85).length, 'clip')} at 85 or more`);
    const formats = new Set(clips.map(formatTagOf).filter(Boolean));
    if (formats.size) lines.push(`${plural(formats.size, 'format')}: ${Array.from(formats).join(', ')}`);
  }
  return lines;
}

/** How a run ended, or the nudge to start one: what happened, what is safe, one action. */
export function RunOutcome(props: RunOutcomeProps) {
  const { phase, steps, clips, credits } = props;

  if (phase === 'not_started') {
    return (
      <Card padding="lg" className="flex flex-col gap-3">
        <h2 className="text-cn-title-sm font-semibold text-cn-fg">Your video is in</h2>
        <p className="text-cn-body text-cn-fg-secondary">
          Making clips hasn’t started yet{props.sourceSeconds > 0 ? ` for this ${formatTimecode(props.sourceSeconds)} video` : ''}. Starting charges credits for its length; if it fails, they come back on their own.
        </p>
        <ActionError error={props.startError} />
        <div>
          <Button leadingIcon={<Play />} loading={props.starting} loadingLabel="Starting" onClick={props.onStart}>
            Make clips
          </Button>
        </div>
      </Card>
    );
  }

  if (phase === 'done') {
    const count = clips?.length;
    const length = props.sourceSeconds > 0 ? ` from ${formatTimecode(props.sourceSeconds)} of video` : '';
    return (
      <ResultMessage
        status="done"
        summary={count === undefined ? `Done${length}.` : `Done — ${plural(count, 'clip')}${length}. Each clip is separate, so you can trim or swap any of them.`}
        changes={doneChanges(steps, clips)}
        details={steps.length ? { steps: runSteps(steps), operations: [] } : undefined}
      />
    );
  }

  const failedStep = steps.find((log) => log.status === 'failed') ?? steps.find((log) => log.status === 'running');
  const doneCount = steps.filter((log) => log.status === 'completed' || log.status === 'skipped').length;
  const returned = credits && credits.returned > 0 ? ` and the ${credits.returned} credits are back in your balance` : '';

  if (phase === 'failed') {
    return (
      <div className="flex flex-col gap-3">
        <ResultMessage
          status="failed"
          summary={`${failedStep ? stepWords(failedStep.step) : 'Making clips for'} ${props.title} didn’t finish.`}
          notDone={failedStep?.message ? [{ label: stepWords(failedStep.step), reason: failedStep.message }] : undefined}
          safeNote={`Your video is safe${returned}. Trying again runs the same steps, skips the ${plural(doneCount, 'step')} already done and charges this video’s credits again.`}
          onRetry={props.retrying ? undefined : props.onRetry}
        />
        {props.retrying && <WorkingText className="text-cn-label">Starting again</WorkingText>}
        <ActionError error={props.retryError} />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      <ResultMessage
        status="stopped"
        summary={failedStep ? `Stopped while ${stepWords(failedStep.step).toLowerCase()}.` : 'Stopped.'}
        changes={doneCount ? [`${plural(doneCount, 'step')} of ${steps.length} done`] : undefined}
        safeNote="The steps done are kept. Starting again picks up from here and charges this video’s credits again."
      />
      <ActionError error={props.retryError} />
      <div className="ml-7">
        <Button variant="secondary" leadingIcon={<RotateCcw />} loading={props.retrying} loadingLabel="Starting again" onClick={props.onRetry}>
          Start again
        </Button>
      </div>
    </div>
  );
}
