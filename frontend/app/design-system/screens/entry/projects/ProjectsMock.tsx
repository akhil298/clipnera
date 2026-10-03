'use client';

import { ArrowUpDown, CircleAlert, Download, Folder, FolderInput, FolderOpen, FolderPlus, LayoutGrid, List, MoreHorizontal, Pencil, Plus, RotateCcw, Search, Square, Trash2 } from 'lucide-react';
import Link from 'next/link';
import { useState } from 'react';

import { Button } from '@/components/ui/Button';
import { Card, cardLinkOverlay } from '@/components/ui/Card';
import { Checkbox } from '@/components/ui/Checkbox';
import { Chip } from '@/components/ui/Chip';
import { Dialog } from '@/components/ui/Dialog';
import { EmptyState } from '@/components/ui/EmptyState';
import { IconButton } from '@/components/ui/IconButton';
import { Input } from '@/components/ui/Input';
import { Menu, type MenuEntry } from '@/components/ui/Menu';
import { SegmentedControl } from '@/components/ui/SegmentedControl';
import { Skeleton, SkeletonGroup } from '@/components/ui/Skeleton';
import { cx, focusRing } from '@/lib/design/styles';

import { AppShell, LiveStatus } from '../_mock/AppShell';
import { ENTRY_BASE, folders, projects, type SampleProject } from '../_mock/data';
import { ScreenFrame } from '../_mock/ScreenFrame';
import { FolderBadge, Poster } from '../_mock/StandIns';
import { SCREENS } from '../_mock/states';

const STATUS = [
  { value: 'all', label: 'All 6' },
  { value: 'processing', label: 'In progress 2' },
  { value: 'ready', label: 'Ready 3' },
  { value: 'failed', label: 'Failed 1' },
] as const;

const VIEW = [
  { value: 'grid', label: <LayoutGrid aria-hidden />, ariaLabel: 'Grid' },
  { value: 'list', label: <List aria-hidden />, ariaLabel: 'List' },
] as const;

function projectHref(project: SampleProject) {
  return project.state === 'ready' ? '#clips' : `${ENTRY_BASE}/progress?state=${project.state === 'uploading' ? 'uploading' : project.state === 'failed' ? 'failed' : 'running'}`;
}

function projectMenu(project: SampleProject, onMove: () => void, onDelete: () => void): MenuEntry[] {
  const running = project.state === 'processing' || project.state === 'uploading';
  return [
    { id: 'rename', label: 'Rename', icon: <Pencil />, onSelect: () => undefined },
    { id: 'move', label: 'Move to folder…', icon: <FolderInput />, onSelect: onMove },
    ...(project.state === 'ready' ? [{ id: 'dl', label: 'Download all clips', icon: <Download />, onSelect: () => undefined }] : []),
    ...(project.state === 'failed' ? [{ id: 'retry', label: 'Try again', icon: <RotateCcw />, onSelect: () => undefined }] : []),
    ...(running ? [{ id: 'stop', label: 'Stop', icon: <Square />, onSelect: () => undefined }] : []),
    { type: 'separator', id: 'sep' },
    { id: 'delete', label: 'Delete project', icon: <Trash2 />, danger: true, onSelect: onDelete },
  ];
}

export function ProjectsMock({ state, theme }: { state: string; theme?: string }) {
  const [view, setView] = useState<'grid' | 'list'>(state === 'list' ? 'list' : 'grid');
  const [status, setStatus] = useState<string>('all');
  const [moveOpen, setMoveOpen] = useState(state === 'move');
  const [newFolderOpen, setNewFolderOpen] = useState(state === 'new-folder');
  const [deleteOpen, setDeleteOpen] = useState(state === 'delete');
  const [selected, setSelected] = useState<string[]>(state === 'selecting' || state === 'move' ? ['p3', 'p6'] : []);
  const inFolder = state === 'folder';
  const selecting = selected.length > 0;

  const list = (inFolder ? projects.filter((p) => p.folderId === 'f1') : projects).filter((p) =>
    status === 'all' ? true : status === 'processing' ? p.state === 'processing' || p.state === 'uploading' : p.state === status,
  );
  const toggle = (id: string) => setSelected((cur) => (cur.includes(id) ? cur.filter((x) => x !== id) : [...cur, id]));

  const crumbs = inFolder ? [{ label: 'Projects', href: `${ENTRY_BASE}/projects` }, { label: folders[0].name }] : [{ label: 'Projects' }];

  return (
    <ScreenFrame
      screen={SCREENS.projects.title}
      states={SCREENS.projects.states}
      state={state}
      theme={theme}
      note="Folders are real server objects (pending owner confirmation). Filters, folder and view live in the URL so Back and links keep them."
    >
      <AppShell active="projects" crumbs={crumbs}>
        <div className="flex flex-col gap-6">
          <div className="flex flex-wrap items-end justify-between gap-4">
            <div className="space-y-1">
              <h1 className="text-cn-title-lg font-bold">{inFolder ? folders[0].name : 'Projects'}</h1>
              <p className="text-cn-body text-cn-fg-secondary">
                {inFolder ? '6 projects · 52 clips' : 'One project per long video. 6 projects · 26 clips · 4 h 41 min of video.'}
              </p>
            </div>
            <div className="flex gap-2">
              {inFolder ? (
                <Menu
                  align="end"
                  items={[
                    { id: 'rn', label: 'Rename folder', icon: <Pencil />, onSelect: () => undefined },
                    { type: 'separator', id: 's' },
                    { id: 'del', label: 'Delete folder', icon: <Trash2 />, danger: true, onSelect: () => undefined },
                  ]}
                  trigger={(props) => <Button {...props} variant="secondary" leadingIcon={<MoreHorizontal />}>Folder</Button>}
                />
              ) : (
                <Button variant="secondary" leadingIcon={<FolderPlus />} onClick={() => setNewFolderOpen(true)}>
                  New folder
                </Button>
              )}
              <Button leadingIcon={<Plus />}>New video</Button>
            </div>
          </div>

          {!inFolder && state !== 'empty' && (
            <section aria-label="Folders">
              <ul className="flex gap-3 overflow-x-auto pb-1">
                {folders.map((folder) => (
                  <li key={folder.id} className="w-56 shrink-0">
                    <Card interactive padding="sm" className="flex items-center gap-3">
                      <Folder aria-hidden className="size-5 shrink-0 text-cn-fg-secondary" />
                      <div className="min-w-0">
                        <Link href={`${ENTRY_BASE}/projects?state=folder`} className={cx(cardLinkOverlay, 'block truncate text-cn-label font-semibold text-cn-fg')}>
                          {folder.name}
                        </Link>
                        <span className="text-cn-caption text-cn-fg-muted">{folder.count} projects</span>
                      </div>
                    </Card>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {state !== 'empty' && (
            <div className="flex flex-col gap-3">
              <div className="flex flex-wrap items-center gap-2">
                <Input
                  aria-label="Search projects"
                  placeholder="Search by title or channel"
                  leading={<Search />}
                  className="w-full sm:w-72"
                  defaultValue={state === 'no-results' ? 'wedding' : undefined}
                />
                <SegmentedControl label="Status" options={STATUS} value={status} onValueChange={setStatus} />
                <span className="flex-1" />
                <Menu
                  align="end"
                  items={[
                    { id: 'new', label: 'Newest first', checked: true, onSelect: () => undefined },
                    { id: 'old', label: 'Oldest first', onSelect: () => undefined },
                    { id: 'name', label: 'Name', onSelect: () => undefined },
                  ]}
                  trigger={(props) => <Button {...props} variant="ghost" size="sm" leadingIcon={<ArrowUpDown />}>Newest</Button>}
                />
                <SegmentedControl label="View" size="sm" options={VIEW} value={view} onValueChange={setView} />
              </div>
              <div role="group" aria-label="Source" className="flex flex-wrap gap-1.5">
                <Chip size="sm" selected>All sources</Chip>
                <Chip size="sm" selected={false}>YouTube</Chip>
                <Chip size="sm" selected={false}>Uploads</Chip>
              </div>
            </div>
          )}

          {selecting && (
            <div role="region" aria-label="Selection" className="sticky top-16 z-cn-raised flex flex-wrap items-center gap-2 rounded-cn-lg border border-cn-border-strong bg-cn-surface-raised p-2 shadow-cn-2">
              <span className="px-2 text-cn-label font-semibold">{selected.length} selected</span>
              <span className="flex-1" />
              <Button size="sm" variant="secondary" leadingIcon={<FolderInput />} onClick={() => setMoveOpen(true)}>Move to folder</Button>
              <Button size="sm" variant="secondary" leadingIcon={<Download />}>Download clips</Button>
              <Button size="sm" variant="ghost" onClick={() => setSelected([])}>Clear</Button>
            </div>
          )}

          <Results state={state} view={view} list={list} selected={selected} toggle={toggle} onMove={() => setMoveOpen(true)} onDelete={() => setDeleteOpen(true)} />
        </div>

        <Dialog
          open={moveOpen}
          onOpenChange={setMoveOpen}
          title={`Move ${selected.length || 1} project${selected.length > 1 ? 's' : ''}`}
          description="A project lives in one folder at a time. Its clips move with it."
          size="sm"
          footer={
            <>
              <Button variant="ghost" onClick={() => setMoveOpen(false)}>Cancel</Button>
              <Button onClick={() => setMoveOpen(false)}>Move</Button>
            </>
          }
        >
          <ul role="radiogroup" aria-label="Folder" className="flex flex-col gap-1">
            {['No folder', ...folders.map((f) => f.name)].map((name, index) => (
              <li key={name}>
                <button
                  type="button"
                  role="radio"
                  aria-checked={index === 1}
                  className={cx(
                    'flex w-full items-center gap-2 rounded-cn-md border px-3 py-2 text-left text-cn-body',
                    index === 1 ? 'border-cn-accent-border bg-cn-accent-subtle text-cn-accent-text' : 'border-transparent text-cn-fg hover:bg-cn-surface-hover',
                    focusRing,
                  )}
                >
                  {index === 0 ? <FolderOpen aria-hidden className="size-4" /> : <Folder aria-hidden className="size-4" />}
                  {name}
                </button>
              </li>
            ))}
          </ul>
          <Button variant="ghost" size="sm" leadingIcon={<FolderPlus />} className="mt-2">New folder</Button>
        </Dialog>

        <Dialog
          open={newFolderOpen}
          onOpenChange={setNewFolderOpen}
          title="New folder"
          description="Group projects by show, client or series. Folders are saved to your workspace."
          size="sm"
          footer={
            <>
              <Button variant="ghost" onClick={() => setNewFolderOpen(false)}>Cancel</Button>
              <Button onClick={() => setNewFolderOpen(false)}>Create folder</Button>
            </>
          }
        >
          <Input label="Name" placeholder="For example, Founder Podcast season 3" data-autofocus maxLength={80} required />
        </Dialog>

        <Dialog
          open={deleteOpen}
          onOpenChange={setDeleteOpen}
          role="alertdialog"
          size="sm"
          title="Delete this project?"
          description="Episode 40 and its 9 clips are deleted for good. Clips already posted to YouTube or Instagram stay posted."
          footer={
            <>
              <Button variant="secondary" data-autofocus onClick={() => setDeleteOpen(false)}>Keep project</Button>
              <Button variant="danger" onClick={() => setDeleteOpen(false)}>Delete project</Button>
            </>
          }
        />
      </AppShell>
    </ScreenFrame>
  );
}

function Results({
  state,
  view,
  list,
  selected,
  toggle,
  onMove,
  onDelete,
}: {
  state: string;
  view: 'grid' | 'list';
  list: SampleProject[];
  selected: string[];
  toggle: (id: string) => void;
  onMove: () => void;
  onDelete: () => void;
}) {
  if (state === 'loading') {
    return (
      <SkeletonGroup label="Loading projects" className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {[0, 1, 2, 3, 4, 5].map((i) => (
          <div key={i} className="flex flex-col gap-2 rounded-cn-lg border border-cn-border p-3">
            <Skeleton className="aspect-video w-full" />
            <Skeleton className="h-4 w-3/4" />
            <Skeleton className="h-3 w-1/2" />
          </div>
        ))}
      </SkeletonGroup>
    );
  }
  if (state === 'error') {
    return (
      <Card>
        <EmptyState
          icon={<CircleAlert />}
          title="I couldn’t load your projects"
          description="Your projects and clips are safe. This is usually a connection problem."
          action={<Button variant="secondary" leadingIcon={<RotateCcw />}>Try again</Button>}
        />
      </Card>
    );
  }
  if (state === 'empty') {
    return (
      <Card>
        <EmptyState
          icon={<FolderOpen />}
          title="No projects yet"
          description="Add a video or paste a YouTube link and Clipnera finds the best moments. Each video becomes a project with its clips inside."
          action={<Button leadingIcon={<Plus />}>Add a video</Button>}
        />
      </Card>
    );
  }
  if (state === 'no-results') {
    return (
      <Card>
        <EmptyState
          icon={<Search />}
          title="No projects match “wedding”"
          description="Try another word, or clear the search and filters."
          action={<Button variant="secondary">Clear filters</Button>}
        />
      </Card>
    );
  }
  if (view === 'list') {
    return (
      <ul className="flex flex-col divide-y divide-cn-border rounded-cn-lg border border-cn-border bg-cn-surface">
        {list.map((project) => (
          <li key={project.id} className="relative flex items-center gap-3 p-3 hover:bg-cn-surface-hover">
            <Poster className="w-24 shrink-0" duration={project.duration} dim={project.state === 'failed'} />
            <div className="min-w-0 flex-1">
              <Link href={projectHref(project)} className={cx(cardLinkOverlay, 'block truncate text-cn-body font-semibold text-cn-fg', focusRing)}>
                {project.title}
              </Link>
              <div className="mt-1 flex flex-wrap items-center gap-2 text-cn-caption text-cn-fg-muted">
                <LiveStatus state={project.state} step={project.step} />
                {project.clips ? `${project.clips} clips · ` : ''}
                {project.updated}
              </div>
            </div>
            <div className="relative z-cn-raised">
              <Menu align="end" items={projectMenu(project, onMove, onDelete)} trigger={(props) => <IconButton {...props} label={`More for ${project.title}`} icon={<MoreHorizontal />} size="sm" />} />
            </div>
          </li>
        ))}
      </ul>
    );
  }
  return (
    <ul className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
      {list.map((project) => {
        const isSelected = selected.includes(project.id);
        return (
          <li key={project.id}>
            <Card interactive selected={isSelected} padding="sm" className="flex h-full flex-col gap-2.5">
              <Poster duration={project.duration} dim={project.state === 'failed' || project.state === 'processing'}>
                <span className="absolute left-2 top-2 z-cn-raised rounded-cn-xs bg-cn-bg/80 p-1">
                  <Checkbox label={<span className="sr-only">Select {project.title}</span>} checked={isSelected} onChange={() => toggle(project.id)} />
                </span>
              </Poster>
              <div className="flex items-start gap-2">
                <Link href={projectHref(project)} className={cx(cardLinkOverlay, 'line-clamp-2 flex-1 text-cn-body font-semibold text-cn-fg')}>
                  {project.title}
                </Link>
                <div className="relative z-cn-raised">
                  <Menu align="end" items={projectMenu(project, onMove, onDelete)} trigger={(props) => <IconButton {...props} label={`More for ${project.title}`} icon={<MoreHorizontal />} size="sm" />} />
                </div>
              </div>
              <span className="text-cn-caption text-cn-fg-muted">
                {project.source === 'youtube' ? project.channel : 'Upload'} · {project.updated}
              </span>
              {project.reason && <p className="text-cn-caption text-cn-danger-text">{project.reason}</p>}
              <div className="mt-auto flex flex-wrap items-center gap-2">
                <LiveStatus state={project.state} step={project.step} />
                {project.clips > 0 && <span className="text-cn-caption text-cn-fg-muted">{project.clips} clips</span>}
                {project.folderId && state !== 'folder' && <FolderBadge name={folders.find((f) => f.id === project.folderId)?.name ?? ''} />}
              </div>
              {project.state === 'failed' && (
                <div className="relative z-cn-raised">
                  <Button size="sm" variant="secondary" leadingIcon={<RotateCcw />}>Try again</Button>
                </div>
              )}
            </Card>
          </li>
        );
      })}
    </ul>
  );
}
