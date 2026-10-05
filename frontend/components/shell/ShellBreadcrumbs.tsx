'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';

import { Breadcrumbs, type Crumb, Wordmark } from '@/components/ui';
import type { RecentProject } from '@/lib/api/account';
import { cx, focusRing } from '@/lib/design/styles';

import { dashboardSegments, HOME_HREF } from './nav';
import { useShell } from './ShellContext';
import { useRecentProjects } from './useAccount';

const LABELS: Record<string, string> = {
  projects: 'Projects',
  folders: 'Projects',
  library: 'Library',
  mine: 'My uploads',
  'brand-kit': 'Brand kit',
  scheduler: 'Publish',
  analytics: 'Analytics',
  reels: 'Reels',
  footage: 'Footage',
  settings: 'Settings',
  account: 'Account',
  billing: 'Plan & billing',
  social: 'Connected accounts',
  team: 'Team',
  upload: 'New video',
  editor: 'Editor',
};

/** Segments with no page of their own: shown, not linked. */
const NO_PAGE = new Set(['footage']);

/** Names for an id segment, by the segment before it. */
const ID_LABELS: Record<string, string> = { projects: 'Project', reels: 'Reel', footage: 'Edit' };

function labelFor(segment: string, previous: string | undefined, projects: ReadonlyArray<RecentProject> | undefined): string {
  if (LABELS[segment] && previous !== 'projects') return LABELS[segment];
  if (previous === 'projects') return projects?.find((project) => project.id === segment)?.title || ID_LABELS.projects;
  return (previous && ID_LABELS[previous]) ?? segment;
}

/** The URL as a trail: Projects / Episode 40. Home alone on /dashboard. */
export function crumbsFor(pathname: string, projects: ReadonlyArray<RecentProject> | undefined, override: string | null): Crumb[] {
  const segments = dashboardSegments(pathname) ?? [];
  const crumbs: Crumb[] =
    segments.length === 0
      ? [{ label: 'Home' }]
      : segments.map((segment, index) => ({
          label: labelFor(segment, segments[index - 1], projects),
          href: index < segments.length - 1 && !NO_PAGE.has(segment) ? `${HOME_HREF}/${segments.slice(0, index + 1).join('/')}` : undefined,
        }));
  if (override) crumbs[crumbs.length - 1] = { label: override };
  return crumbs;
}

/**
 * Left of the top bar. Desktop: the trail. Phone: the wordmark on a top-level
 * page, a back link to the parent on a nested one.
 */
export function ShellBreadcrumbs() {
  const pathname = usePathname();
  const { crumbLabel } = useShell();
  const projects = useRecentProjects().data;
  const crumbs = crumbsFor(pathname, projects, crumbLabel);
  const nested = crumbs.length > 1;

  return (
    <>
      {!nested && (
        <Link href={HOME_HREF} aria-label="Clipnera home" className={cx('rounded-cn-sm md:hidden', focusRing)}>
          <Wordmark size="sm" />
        </Link>
      )}
      <Breadcrumbs items={crumbs} className={nested ? undefined : 'hidden md:block'} />
    </>
  );
}
