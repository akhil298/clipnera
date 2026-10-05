'use client';

import Link from 'next/link';

import { Card, StatusBadge, VideoThumb, cardLinkOverlay } from '@/components/ui';
import { cx } from '@/lib/design/styles';
import { formatRelativeTime } from '@/lib/utils/dates';

import { posterOf, projectHref } from './projectState';
import type { ProjectWithRun } from './useHomeData';

const STATUS = { running: 'processing', ready: 'ready', failed: 'failed' } as const;

/** Poster, title, live status and "3 h ago · 9 clips". One link covers the card. */
export function ProjectCard({ item }: { item: ProjectWithRun }) {
  const { project, run } = item;
  const clips = project.clips.length;
  const meta = [project.created_at ? formatRelativeTime(project.created_at) : '', clips > 0 ? `${clips} clip${clips === 1 ? '' : 's'}` : '']
    .filter(Boolean)
    .join(' · ');

  return (
    <Card interactive padding="sm" className="flex h-full flex-col gap-2.5">
      <VideoThumb
        aspect="16:9"
        poster={posterOf(project)}
        duration={project.duration_seconds || undefined}
        dimmed={run.kind === 'failed'}
        topLeft={run.kind === 'ready' ? undefined : <StatusBadge status={STATUS[run.kind]} />}
      />
      <Link href={projectHref(project.id)} className={cx(cardLinkOverlay, 'line-clamp-2 text-cn-body font-semibold text-cn-fg')}>
        {project.title}
      </Link>
      <p className="mt-auto truncate text-cn-caption text-cn-fg-muted">{run.kind === 'running' ? run.step : meta}</p>
    </Card>
  );
}
