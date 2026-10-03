'use client';

import { Popover } from '@/components/ui/Popover';
import { ProgressBar } from '@/components/ui/ProgressBar';
import { WorkingText } from '@/components/ui/WorkingText';
import { cx, focusRing } from '@/lib/design/styles';

export interface ActivityJob {
  id: string;
  project: string;
  step: string;
  /** 0–100 when known. */
  percent?: number;
  failed?: boolean;
}

/**
 * Design-system addition (02 §4.8): server jobs across projects. Hidden when
 * idle. A pill with a live dot and a count; opens a popover with each job's
 * current step. Done jobs move to the inbox; failed ones show a rose dot
 * until seen. Driven by `activity.updated` plus `GET /jobs?status=active`.
 */
export function ActivityIndicator({ jobs }: { jobs: ReadonlyArray<ActivityJob> }) {
  if (jobs.length === 0) return null;
  const failed = jobs.some((job) => job.failed);
  const name = `${jobs.length} ${jobs.length === 1 ? 'job' : 'jobs'} running${failed ? ', one needs attention' : ''}`;
  return (
    <Popover
      title="Working on"
      trigger={(props) => (
        <button
          type="button"
          {...props}
          aria-label={name}
          className={cx('inline-flex h-8 items-center gap-1.5 rounded-cn-full border border-cn-border-strong bg-cn-surface px-2.5 font-cn-mono text-cn-caption tabular-nums text-cn-fg-secondary hover:bg-cn-surface-hover', focusRing)}
        >
          <span aria-hidden className={cx('size-2 rounded-cn-full', failed ? 'bg-cn-danger' : 'bg-cn-accent motion-safe:animate-cn-pulse')} />
          {jobs.length}
        </button>
      )}
    >
      <ul className="flex flex-col gap-3">
        {jobs.map((job) => (
          <li key={job.id} className="flex flex-col gap-1">
            <p className="text-cn-label font-semibold text-cn-fg">{job.project}</p>
            <p className="text-cn-caption">{job.failed ? <span className="text-cn-danger-text">{job.step}</span> : <WorkingText>{job.step}</WorkingText>}</p>
            {job.percent !== undefined && <ProgressBar label={`${job.project}: ${job.step}`} value={job.percent} hideLabel size="sm" tone={job.failed ? 'danger' : 'accent'} />}
          </li>
        ))}
      </ul>
    </Popover>
  );
}
