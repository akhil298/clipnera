'use client';

import { useMutation } from '@tanstack/react-query';
import { ArrowRight, CircleAlert, Clapperboard, Plus, RotateCw } from 'lucide-react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { type ReactNode, useState } from 'react';

import { Button, Card, EmptyState, SearchField, Skeleton, SkeletonGroup, Tab, TabList, TabPanel, Tabs, cardLinkOverlay } from '@/components/ui';
import { homeApi } from '@/lib/api/home';
import { cx, focusRing } from '@/lib/design/styles';
import { useFlag } from '@/lib/flags/useFlag';

import { ProjectCard } from './ProjectCard';
import { STARTERS } from './starters';
import type { ProjectWithRun } from './useHomeData';

const PROJECTS_PATH = '/dashboard/projects';
const PROJECTS_SHOWN = 12;
const GRID = 'grid gap-4 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4';

type SheetTab = 'recent' | 'projects' | 'templates';

export interface ProjectSheetProps {
  items: readonly ProjectWithRun[] | undefined;
  loading: boolean;
  failed: boolean;
  onRetry: () => void;
  /** A template fills the composer, like a suggestion chip. */
  onUseTemplate: (prompt: string) => void;
}

/** The sheet under the hero: Recent | Projects | Templates (Lovable rec. 8). */
export function ProjectSheet({ items, loading, failed, onRetry, onUseTemplate }: ProjectSheetProps) {
  const [tab, setTab] = useState<SheetTab>('recent');
  const [query, setQuery] = useState('');

  const body = (content: (list: readonly ProjectWithRun[]) => ReactNode) => {
    if (loading) return <ProjectsSkeleton />;
    if (failed || !items) return <ProjectsFailed onRetry={onRetry} />;
    return content(items);
  };

  return (
    <section aria-label="Your work" className="rounded-t-cn-2xl border-x border-t border-cn-border bg-cn-surface px-4 pb-10 pt-3 sm:px-6">
      <Tabs value={tab} defaultValue="recent" onValueChange={(next) => setTab(next as SheetTab)}>
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2 border-b border-cn-border">
          <TabList label="Your work" className="border-b-0">
            <Tab value="recent">Recent</Tab>
            <Tab value="projects">Projects</Tab>
            <Tab value="templates">Templates</Tab>
          </TabList>
          <span className="flex-1" />
          {tab === 'projects' && (
            <SearchField value={query} onValueChange={setQuery} aria-label="Search projects" placeholder="Search projects" size="sm" className="w-full pb-2 sm:w-60" />
          )}
          <Link
            href={PROJECTS_PATH}
            className={cx('mb-2 inline-flex items-center gap-1 rounded-cn-xs text-cn-label text-cn-accent-text hover:underline', focusRing)}
          >
            All projects
            <ArrowRight aria-hidden className="size-3.5" />
          </Link>
        </div>

        <TabPanel value="recent" className="pt-5">
          {body((list) => <RecentPanel items={list} />)}
        </TabPanel>
        <TabPanel value="projects" className="pt-5">
          {body((list) => <ProjectsPanel items={list} query={query} />)}
        </TabPanel>
        <TabPanel value="templates" className="pt-5">
          <ul className={GRID}>
            {STARTERS.map((starter) => (
              <li key={starter.id}>
                <Card interactive className="flex h-full flex-col gap-1.5">
                  <button type="button" onClick={() => onUseTemplate(starter.prompt)} className={cx(cardLinkOverlay, 'text-left text-cn-body font-semibold text-cn-fg')}>
                    {starter.title}
                  </button>
                  <p className="text-cn-label text-cn-fg-secondary">{starter.prompt}</p>
                </Card>
              </li>
            ))}
          </ul>
        </TabPanel>
      </Tabs>
    </section>
  );
}

/** "Start empty" first (when the editor is on), then the newest projects: 2 / 3 / 4 across. */
function RecentPanel({ items }: { items: readonly ProjectWithRun[] }) {
  const editorOn = useFlag('agent_editor');
  const recent = items.slice(0, editorOn ? 3 : 4);
  if (recent.length === 0 && !editorOn) return <FirstProject />;
  return (
    <div className="flex flex-col gap-6">
      <ul className={GRID}>
        {editorOn && (
          <li>
            <StartEmptyCard />
          </li>
        )}
        {recent.map((item, index) => (
          // The fourth cell only shows where four fit, so rows stay whole.
          <li key={item.project.id} className={cx(index + (editorOn ? 1 : 0) === 3 && 'lg:hidden 2xl:block')}>
            <ProjectCard item={item} />
          </li>
        ))}
      </ul>
      {recent.length === 0 && <FirstProject />}
    </div>
  );
}

function ProjectsPanel({ items, query }: { items: readonly ProjectWithRun[]; query: string }) {
  const q = query.trim().toLowerCase();
  if (items.length === 0) return <FirstProject />;
  const matches = q ? items.filter(({ project }) => project.title.toLowerCase().includes(q)) : items;
  if (matches.length === 0) {
    return <EmptyState size="compact" level={3} title={`No project matches “${query.trim()}”`} description="Try another word from its title." />;
  }
  return (
    <div className="flex flex-col gap-4">
      <ul className={GRID}>
        {matches.slice(0, PROJECTS_SHOWN).map((item) => (
          <li key={item.project.id}>
            <ProjectCard item={item} />
          </li>
        ))}
      </ul>
      {matches.length > PROJECTS_SHOWN && (
        <Link href={PROJECTS_PATH} className={cx('self-start rounded-cn-xs text-cn-label text-cn-accent-text hover:underline', focusRing)}>
          See all {matches.length} projects
        </Link>
      )}
    </div>
  );
}

/** A blank editor project: footage, music and captions come later (Cardboard rec. 21). */
function StartEmptyCard() {
  const router = useRouter();
  const create = useMutation({
    mutationFn: homeApi.createEmptyEdit,
    onSuccess: (project) => router.push(`/dashboard/editor/${project.id}`),
  });
  return (
    <Card interactive padding="sm" className="flex h-full flex-col gap-2.5">
      <div aria-hidden className="flex aspect-video items-center justify-center rounded-cn-md border border-dashed border-cn-border-strong text-cn-fg-muted">
        <Plus className="size-6" />
      </div>
      <button
        type="button"
        onClick={() => create.mutate()}
        disabled={create.isPending}
        aria-describedby={create.isError ? 'home-start-empty-error' : undefined}
        className={cx(cardLinkOverlay, 'text-left text-cn-body font-semibold text-cn-fg disabled:cursor-wait')}
      >
        {create.isPending ? 'Opening the editor…' : 'Start empty'}
      </button>
      {create.isError ? (
        <p id="home-start-empty-error" role="alert" className="text-cn-caption text-cn-danger-text">
          I couldn’t open a new edit. Try again.
        </p>
      ) : (
        <p className="text-cn-caption text-cn-fg-muted">Open the editor and add footage as you go</p>
      )}
    </Card>
  );
}

function FirstProject() {
  return (
    <EmptyState
      size="compact"
      level={3}
      icon={<Clapperboard />}
      title="Your first project starts here"
      description="Paste a YouTube link or drop a video into the box above. Each video becomes a project with its clips."
    />
  );
}

function ProjectsSkeleton() {
  return (
    <SkeletonGroup label="Loading your projects" className={GRID}>
      {[0, 1, 2].map((index) => (
        <div key={index} className="flex flex-col gap-2">
          <Skeleton className="aspect-video w-full" />
          <Skeleton className="h-4 w-3/4" />
          <Skeleton className="h-3 w-1/2" />
        </div>
      ))}
    </SkeletonGroup>
  );
}

function ProjectsFailed({ onRetry }: { onRetry: () => void }) {
  return (
    <EmptyState
      size="compact"
      level={3}
      icon={<CircleAlert />}
      title="I couldn’t load your projects"
      description="Your projects are safe. Everything above still works."
      action={
        <Button size="sm" variant="secondary" leadingIcon={<RotateCw />} onClick={onRetry}>
          Try again
        </Button>
      }
    />
  );
}
