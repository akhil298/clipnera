import { Coins, Upload, Youtube } from 'lucide-react';
import type { ReactNode } from 'react';

import { Breadcrumbs } from '@/components/ui/Breadcrumbs';
import { type Status, StatusBadge } from '@/components/ui/Badge';
import { TimeCode } from '@/components/ui/TimeCode';
import type { ProjectRecord } from '@/lib/api/clips';
import type { ProjectCredits } from '@/lib/api/jobs';
import { cx, focusRing } from '@/lib/design/styles';

import type { Phase } from './run';

const BADGE: Record<Phase, Status> = {
  importing: 'processing',
  running: 'processing',
  not_started: 'draft',
  failed: 'failed',
  stopped: 'paused',
  done: 'ready',
};

const FALLBACK_WORD: Record<Phase, string> = {
  importing: 'Getting your video',
  running: 'Working',
  not_started: 'Not started',
  failed: 'Didn’t finish',
  stopped: 'Stopped',
  done: 'Ready',
};

export interface ProjectHeaderProps {
  project: ProjectRecord;
  phase: Phase;
  /** The live step or the count: "Transcribing", "9 clips ready". */
  statusWord?: string;
  credits?: ProjectCredits;
  actions?: ReactNode;
}

function creditsLine({ charged, returned }: ProjectCredits): string | null {
  if (charged === 0) return null;
  if (returned >= charged) return `${charged} credits · returned`;
  return returned > 0 ? `${charged - returned} credits charged (${returned} returned)` : `${charged} credits charged`;
}

/** Title, source, length, live status and what the project cost; the page's only h1. */
export function ProjectHeader({ project, phase, statusWord, credits, actions }: ProjectHeaderProps) {
  const upload = project.source_type === 'upload';
  const spent = credits ? creditsLine(credits) : null;
  return (
    <header className="flex flex-col gap-3">
      <Breadcrumbs items={[{ label: 'Projects', href: '/dashboard/projects' }, { label: project.title }]} />
      <div className="flex flex-wrap items-start gap-3">
        <h1 className="min-w-0 flex-1 break-words text-cn-title-lg font-semibold text-cn-fg">{project.title}</h1>
        {actions && <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>}
      </div>
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2 text-cn-label text-cn-fg-secondary">
        <StatusBadge status={BADGE[phase]}>{statusWord ?? FALLBACK_WORD[phase]}</StatusBadge>
        <span className="inline-flex min-w-0 items-center gap-1.5">
          {upload ? <Upload aria-hidden className="size-4 shrink-0" /> : <Youtube aria-hidden className="size-4 shrink-0" />}
          {upload || !project.source_url ? (
            <span>{upload ? 'Your upload' : 'YouTube'}</span>
          ) : (
            <a
              href={project.source_url}
              target="_blank"
              rel="noreferrer"
              className={cx('rounded-cn-xs underline decoration-cn-border-strong underline-offset-2 hover:text-cn-fg hover:decoration-cn-fg', focusRing)}
            >
              YouTube<span className="sr-only"> (opens the original video in a new tab)</span>
            </a>
          )}
        </span>
        {project.duration_seconds > 0 && <TimeCode seconds={project.duration_seconds} tone="inherit" />}
        {spent && (
          <span className="inline-flex items-center gap-1.5">
            <Coins aria-hidden className="size-4" />
            <span className="font-cn-mono tabular-nums">{spent}</span>
          </span>
        )}
      </div>
    </header>
  );
}
