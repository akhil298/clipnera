'use client';

import Link from 'next/link';
import { type RefObject, useRef } from 'react';

import { Portal, Skeleton, SidebarSection, StatusBadge, useSidebarCollapsed, VideoThumb } from '@/components/ui';
import type { RecentProject } from '@/lib/api/account';
import { useAnchoredPosition } from '@/lib/design/useAnchoredPosition';
import { useHoverIntent } from '@/lib/design/useHoverIntent';
import { cx, floatingSurface, focusRing } from '@/lib/design/styles';
import { formatRelativeTime } from '@/lib/utils/dates';

import { isRunning, useRecentProjects } from './useAccount';

const SHOWN = 4;
const PEEK_DELAY_MS = 300;

export const projectHref = (id: string) => `/dashboard/projects/${id}`;

/** Status in words: no "processing" (screens/01 copy rules). */
export function ProjectStatusBadge({ project }: { project: RecentProject }) {
  if (project.status === 'completed') return <StatusBadge status="ready" />;
  if (project.status === 'failed') return <StatusBadge status="failed" />;
  return <StatusBadge status="processing">{project.status === 'pending' ? 'Queued' : 'Making clips'}</StatusBadge>;
}

/** "9 clips · added 2 h ago". */
export function projectMeta(project: RecentProject): string {
  const clips = project.clips.length;
  const parts = [clips ? `${clips} ${clips === 1 ? 'clip' : 'clips'}` : null, project.created_at ? `added ${formatRelativeTime(project.created_at)}` : null];
  return parts.filter(Boolean).join(' · ');
}

/** The hover peek: poster, title, status, meta. Decorative; the row's link already names the project. */
function Peek({ project, anchorRef }: { project: RecentProject; anchorRef: RefObject<HTMLElement | null> }) {
  const panelRef = useRef<HTMLDivElement>(null);
  const { style } = useAnchoredPosition(true, anchorRef, panelRef, { side: 'right', align: 'start', offset: 12 });
  const poster = project.clips.find((clip) => clip.poster_url)?.poster_url ?? undefined;
  return (
    <Portal>
      <div ref={panelRef} aria-hidden style={style} className={cx(floatingSurface, 'pointer-events-none z-cn-popover flex w-64 flex-col gap-2 p-2')}>
        <VideoThumb poster={poster} aspect="16:9" duration={project.duration_seconds || undefined} rounded="md" />
        <div className="flex flex-col gap-1 px-1 pb-1">
          <p className="line-clamp-2 text-cn-label font-semibold text-cn-fg">{project.title}</p>
          <div className="flex flex-wrap items-center gap-2">
            <ProjectStatusBadge project={project} />
            <span className="text-cn-caption text-cn-fg-muted">{projectMeta(project)}</span>
          </div>
        </div>
      </div>
    </Portal>
  );
}

function RecentRow({ project }: { project: RecentProject }) {
  const rowRef = useRef<HTMLAnchorElement>(null);
  const { active, handlers } = useHoverIntent(PEEK_DELAY_MS);
  const running = isRunning(project.status);
  return (
    <li>
      <Link
        ref={rowRef}
        href={projectHref(project.id)}
        {...handlers}
        className={cx(
          'flex min-h-8 items-center gap-2 rounded-cn-sm px-2.5 py-1 text-cn-label text-cn-fg-secondary transition-colors duration-cn-fast',
          'hover:bg-cn-surface-hover hover:text-cn-fg active:bg-cn-surface-active',
          focusRing,
        )}
      >
        <span className="min-w-0 flex-1 truncate">{project.title}</span>
        {running && (
          <span className="size-1.5 shrink-0 rounded-cn-full bg-cn-accent motion-safe:animate-cn-pulse">
            <span className="sr-only">, in progress</span>
          </span>
        )}
        {project.status === 'failed' && <span className="sr-only">, failed</span>}
      </Link>
      {active && <Peek project={project} anchorRef={rowRef} />}
    </li>
  );
}

/** The last four projects as plain rows with a live dot while running. Hidden in the rail, and when empty or unavailable. */
export function RecentProjects() {
  const collapsed = useSidebarCollapsed();
  const recent = useRecentProjects();
  if (collapsed || recent.isError || recent.data?.length === 0) return null;

  return (
    <SidebarSection title="Recent">
      {recent.isPending
        ? Array.from({ length: SHOWN }, (_, index) => (
            <li key={index} aria-hidden>
              <Skeleton className="my-1 h-6 w-full" />
            </li>
          ))
        : recent.data.slice(0, SHOWN).map((project) => <RecentRow key={project.id} project={project} />)}
    </SidebarSection>
  );
}
