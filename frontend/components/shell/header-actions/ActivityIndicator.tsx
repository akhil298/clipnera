'use client';

import Link from 'next/link';

import { Popover, ProgressBar, WorkingText } from '@/components/ui';
import { cx, focusRing } from '@/lib/design/styles';

import { type ActivityJob, useActivity } from './useActivity';

const projectHref = (projectId: string) => `/dashboard/projects/${projectId}`;

function JobRow({ job, onNavigate }: { job: ActivityJob; onNavigate: () => void }) {
  return (
    <li className="flex flex-col gap-1.5">
      <Link
        href={projectHref(job.projectId)}
        onClick={onNavigate}
        className={cx('flex min-w-0 items-center gap-2 rounded-cn-xs text-cn-label font-semibold text-cn-fg hover:underline', focusRing)}
      >
        {job.failed && <span aria-hidden className="size-1.5 shrink-0 rounded-cn-full bg-cn-danger" />}
        <span className="truncate">{job.title}</span>
      </Link>
      {job.failed ? (
        <p className="text-cn-caption text-cn-danger-text">{job.step}</p>
      ) : (
        <WorkingText className="text-cn-caption">{job.step}</WorkingText>
      )}
      {job.percent !== null && <ProgressBar label={`${job.title}: ${job.step}`} value={job.percent} hideLabel size="sm" />}
    </li>
  );
}

/**
 * DS-5 activity pill (screens/01 §5.4): hidden when idle, a live amber dot and
 * a count while work runs, a rose dot when a run failed while you were away.
 * Each row links to that project's progress page.
 */
export function ActivityIndicator() {
  const { live, failed, acknowledgeFailures } = useActivity();
  if (live.length === 0 && failed.length === 0) return null;

  const attention = failed.length > 0;
  const name = [live.length > 0 && `${live.length} in progress`, attention && `${failed.length} ${failed.length === 1 ? 'needs' : 'need'} attention`]
    .filter(Boolean)
    .join(', ');

  return (
    <Popover
      title="In progress"
      align="end"
      className="w-80 max-w-full"
      onOpenChange={(open) => !open && acknowledgeFailures()}
      trigger={(props) => (
        <button
          type="button"
          {...props}
          aria-label={name}
          className={cx(
            'inline-flex h-8 items-center gap-1.5 rounded-cn-full border border-cn-border-strong px-2.5 text-cn-label font-semibold text-cn-fg-secondary transition-colors duration-cn-fast',
            'hover:bg-cn-surface-hover hover:text-cn-fg active:bg-cn-surface-active aria-expanded:bg-cn-surface-hover',
            focusRing,
          )}
        >
          <span aria-hidden className={cx('size-1.5 rounded-cn-full', attention ? 'bg-cn-danger' : 'bg-cn-accent motion-safe:animate-cn-pulse')} />
          <span aria-hidden className="font-cn-mono tabular-nums">
            {live.length + failed.length}
          </span>
        </button>
      )}
    >
      {(close) => (
        <>
          <ul className="flex flex-col gap-3">
            {[...failed, ...live].map((job) => (
              <JobRow key={job.projectId} job={job} onNavigate={close} />
            ))}
          </ul>
          <p className="mt-3 border-t border-cn-border pt-3 text-cn-caption text-cn-fg-muted">
            These keep going if you close the tab. Finished work moves to notifications.
          </p>
        </>
      )}
    </Popover>
  );
}
