'use client';

import { Square } from 'lucide-react';
import { type ReactNode, useState } from 'react';

import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Dialog } from '@/components/ui/Dialog';
import { ProgressBar } from '@/components/ui/ProgressBar';
import { type ProgressStep, ProgressSteps } from '@/components/ui/ProgressSteps';
import { StepList } from '@/components/ui/StepList';
import { TimeCode } from '@/components/ui/TimeCode';
import { WorkingText } from '@/components/ui/WorkingText';
import type { DownloadProgress, PipelineStepLog } from '@/lib/api/jobs';
import { formatTimecode } from '@/lib/design/timecode';
import { stepWords } from '@/lib/projects/run';

import { elapsedSeconds, importLine, type Phase, parseUtc, runSteps, type StageView, stagesOf } from './run';
import { useNow } from './useProjectRun';

export interface RunProgressProps {
  phase: Phase;
  steps: readonly PipelineStepLog[];
  sourceType: string;
  sourceSeconds: number;
  download?: DownloadProgress;
  /** Clips already cut while the run goes on (a real count, or undefined). */
  clipsSoFar?: number;
  onStop: () => void;
  stopping: boolean;
  onRetryStep?: () => void;
}

const stageSeconds = (stage: StageView): number | null => {
  const starts = stage.logs.map((log) => parseUtc(log.started_at)).filter((time): time is number => time !== null);
  const ends = stage.logs.map((log) => parseUtc(log.finished_at)).filter((time): time is number => time !== null);
  return starts.length && ends.length ? Math.max(0, (Math.max(...ends) - Math.min(...starts)) / 1000) : null;
};

function ActiveDetail({ line, percent, label }: { line: string; percent?: number; label: string }) {
  return (
    <span className="flex w-72 max-w-full flex-col gap-1.5 pt-1">
      <WorkingText>{line}</WorkingText>
      {percent !== undefined && percent > 0 && <ProgressBar label={label} value={percent} hideLabel size="sm" />}
    </span>
  );
}

function stageDescription(stage: StageView, props: RunProgressProps): ReactNode {
  if (stage.status === 'active') {
    if (stage.id === 'import' && props.phase === 'importing') {
      const progress = props.download;
      return <ActiveDetail line={importLine(progress, props.sourceType)} percent={progress?.percent} label="Getting your video" />;
    }
    const log = stage.running;
    if (!log) return <WorkingText>Moving to the next step</WorkingText>;
    const count = stage.id === 'clips' && props.clipsSoFar ? ` · ${props.clipsSoFar} cut so far` : '';
    return <ActiveDetail line={`${stepWords(log.step)}${count}`} percent={log.progress_percent} label={stage.label} />;
  }
  if (stage.status === 'failed') return stage.failed?.message ?? (props.phase === 'stopped' ? 'Stopped here' : 'This step didn’t finish');
  if (stage.status === 'done') {
    if (stage.logs.length === 0) return props.sourceSeconds > 0 ? `Got ${formatTimecode(props.sourceSeconds)} of video` : 'Got your video';
    const took = stageSeconds(stage);
    const ran = `Ran ${stage.logs.length} step${stage.logs.length === 1 ? '' : 's'}`;
    return took !== null ? `${ran} · ${formatTimecode(took)}` : ran;
  }
  return undefined;
}

/** One sentence with real counts, before the steps (Cardboard's plan line). */
function planLine(steps: readonly PipelineStepLog[], sourceSeconds: number, phase: Phase): string {
  const length = sourceSeconds > 0 ? `this ${formatTimecode(sourceSeconds)} video` : 'this video';
  if (phase === 'importing' || steps.length === 0) return `I’m getting ${length} ready. The steps start as soon as it’s in.`;
  const first = stepWords(steps[0].step).toLowerCase();
  const last = stepWords(steps[steps.length - 1].step).toLowerCase();
  return `I’m making clips from ${length} in ${steps.length} steps, from ${first} to ${last}.`;
}

/**
 * The live run: plan line, five stages with the current one moving, the
 * detailed steps behind a disclosure, elapsed time, and Stop (screens/01 §10).
 */
export function RunProgress(props: RunProgressProps) {
  const { phase, steps, onStop, stopping, onRetryStep } = props;
  const [confirming, setConfirming] = useState(false);
  const running = phase === 'running' || phase === 'importing';
  const now = useNow(running);
  const elapsed = elapsedSeconds(steps, now);
  const stages = stagesOf(phase, steps);
  const progressSteps: ProgressStep[] = stages.map((stage) => ({
    id: stage.id,
    label: stage.label,
    status: stage.status,
    description: stageDescription(stage, props),
  }));
  const canStop = phase === 'running' && steps.length > 0;

  return (
    <Card padding="lg" className="flex flex-col gap-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex min-w-0 flex-1 flex-col gap-1">
          <h2 className="text-cn-title-sm font-semibold text-cn-fg">Steps</h2>
          <p className="text-cn-body text-cn-fg-secondary">{planLine(steps, props.sourceSeconds, phase)}</p>
        </div>
        <div className="flex items-center gap-3">
          {elapsed !== null && (
            <span className="text-cn-caption text-cn-fg-muted">
              <TimeCode seconds={elapsed} tone="muted" />
              <span aria-hidden> elapsed</span>
            </span>
          )}
          {canStop && (
            <Button variant="secondary" size="sm" leadingIcon={<Square />} loading={stopping} loadingLabel="Stopping" onClick={() => setConfirming(true)}>
              Stop
            </Button>
          )}
        </div>
      </div>

      <ProgressSteps label="Progress of this project" orientation="vertical" steps={progressSteps} />

      {steps.length > 0 && (
        <StepList steps={runSteps(steps)} elapsed={elapsed !== null ? formatTimecode(elapsed) : undefined} onRetryStep={onRetryStep ? () => onRetryStep() : undefined} />
      )}

      {running && (
        <p className="text-cn-caption text-cn-fg-muted">
          {phase === 'importing' && props.sourceType === 'upload'
            ? 'Keep this tab open until the upload finishes. After that you can close it; the rest happens on our side.'
            : 'You can close this tab. This keeps going on our side, and you’ll get a notification when the clips are ready.'}
        </p>
      )}

      <Dialog
        open={confirming}
        onOpenChange={setConfirming}
        role="alertdialog"
        size="sm"
        title="Stop making clips?"
        description="The steps already done are kept, so you can start again later from where it stopped. Stopping doesn’t return the credits for this run."
        footer={
          <>
            <Button variant="secondary" data-autofocus onClick={() => setConfirming(false)}>
              Keep going
            </Button>
            <Button
              variant="danger"
              onClick={() => {
                setConfirming(false);
                onStop();
              }}
            >
              Stop
            </Button>
          </>
        }
      />
    </Card>
  );
}
