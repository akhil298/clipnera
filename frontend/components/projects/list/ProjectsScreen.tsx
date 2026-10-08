'use client';

import { CircleAlert, Plus, RotateCcw, Search } from 'lucide-react';
import Link from 'next/link';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import { useCallback, useEffect, useMemo, useRef, useState, type KeyboardEvent } from 'react';

import { Button, buttonClasses, EmptyState, InlineAlert, useToast } from '@/components/ui';
import { usePersistentState } from '@/lib/design/usePersistentState';

import { DeleteProjectsDialog } from './DeleteProjectsDialog';
import { clearedFilters, filterProjects, hasNarrowing, readFilters, writeFilters, type ProjectFilters, type ViewMode } from './filters';
import { FirstProject } from './FirstProject';
import { ProjectRow, ProjectTile } from './ProjectItem';
import type { ProjectActions } from './ProjectMenu';
import { plural, spokenLength, type ProjectView } from './projectState';
import { GRID_CLASS, ProjectsSkeleton } from './ProjectsSkeleton';
import { ProjectsToolbar } from './ProjectsToolbar';
import { SelectionBar } from './SelectionBar';
import { useDeleteProjects, useDownloadClips, useOnline, useProjectViews, useRenameProject, useStopProject } from './useProjects';

const NEW_VIDEO = '/dashboard/upload';

/** Filters live in the URL; the grid/list choice also persists per browser. */
function useFilters(): [ProjectFilters, (patch: Partial<ProjectFilters>) => void] {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const [savedView, saveView] = usePersistentState<ViewMode>('clipnera.projects.view', 'grid');
  const filters = useMemo(() => {
    const read = readFilters(new URLSearchParams(params.toString()));
    return params.has('view') ? read : { ...read, view: savedView };
  }, [params, savedView]);
  const update = useCallback(
    (patch: Partial<ProjectFilters>) => {
      if (patch.view) saveView(patch.view);
      router.replace(`${pathname}${writeFilters({ ...filters, ...patch })}`, { scroll: false });
    },
    [filters, pathname, router, saveView],
  );
  return [filters, update];
}

/** Click toggles; Shift-click selects the range from the last clicked item. */
function useSelection(ordered: readonly ProjectView[]) {
  const [ids, setIds] = useState<ReadonlySet<string>>(new Set());
  const anchor = useRef<string | null>(null);
  const toggle = useCallback(
    (id: string, range: boolean) => {
      setIds((current) => {
        const next = new Set(current);
        const order = ordered.map((v) => v.project.id);
        const from = anchor.current ? order.indexOf(anchor.current) : -1;
        const to = order.indexOf(id);
        if (range && from >= 0 && to >= 0) {
          order.slice(Math.min(from, to), Math.max(from, to) + 1).forEach((rangeId) => next.add(rangeId));
        } else if (next.has(id)) next.delete(id);
        else next.add(id);
        return next;
      });
      anchor.current = id;
    },
    [ordered],
  );
  const set = useCallback((next: Iterable<string>) => setIds(new Set(next)), []);
  return { ids, toggle, set };
}

function summary(views: readonly ProjectView[]): string {
  const clips = views.reduce((sum, v) => sum + v.clipCount, 0);
  const seconds = views.reduce((sum, v) => sum + v.project.duration_seconds, 0);
  return [plural(views.length, 'project'), plural(clips, 'clip'), seconds > 0 ? `${spokenLength(seconds)} of video` : ''].filter(Boolean).join(' · ');
}

export function ProjectsScreen() {
  const toast = useToast();
  const online = useOnline();
  const [filters, setFilters] = useFilters();
  const { list, views } = useProjectViews();
  const { items, counts } = useMemo(() => filterProjects(views, filters), [views, filters]);
  const selection = useSelection(items);
  const selected = useMemo(() => views.filter((v) => selection.ids.has(v.project.id)), [views, selection.ids]);

  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [deleteTargets, setDeleteTargets] = useState<readonly ProjectView[]>([]);
  const [busyId, setBusyId] = useState<string | null>(null);

  const rename = useRenameProject();
  const remove = useDeleteProjects();
  const stop = useStopProject();
  const download = useDownloadClips();

  const actions: ProjectActions = {
    online,
    busyId,
    rename: (view) => setRenamingId(view.project.id),
    remove: (targets) => setDeleteTargets(targets),
    stop: (view) => {
      setBusyId(view.project.id);
      stop.mutate(view.project.id, {
        onSuccess: () => toast.show({ title: 'Stopped', description: 'Your video is kept. Open the project to start again.', tone: 'success' }),
        onError: () => toast.show({ title: 'I couldn’t stop it', description: 'It’s still running. Try again in a moment.', tone: 'danger' }),
        onSettled: () => setBusyId(null),
      });
    },
    download: (targets) => {
      if (targets.length === 1) setBusyId(targets[0].project.id);
      toast.show({
        title: targets.length === 1 ? 'Packing your clips' : `Packing clips from ${plural(targets.length, 'project')}`,
        description: 'Each ZIP downloads when it’s ready. You can keep working.',
      });
      download.mutate(targets, {
        onSuccess: ({ failed }) => {
          if (failed > 0) {
            toast.show({
              title: failed === targets.length ? 'I couldn’t pack the clips' : `${plural(failed, 'project')} didn’t download`,
              description: 'Your clips are safe. Try again from the project’s menu.',
              tone: 'danger',
            });
          }
        },
        onSettled: () => setBusyId(null),
      });
    },
  };

  const saveRename = (view: ProjectView, title: string) => {
    setRenamingId(null);
    rename.mutate(
      { id: view.project.id, title },
      { onError: () => toast.show({ title: 'I couldn’t save the new name', description: `It’s still called “${view.project.title}”.`, tone: 'danger' }) },
    );
  };

  const confirmDelete = () => {
    remove.mutate(deleteTargets, {
      onSuccess: ({ deleted, failed }) => {
        selection.set([...selection.ids].filter((id) => !deleted.includes(id)));
        setDeleteTargets([]);
        if (deleted.length > 0) toast.show({ title: deleted.length === 1 ? 'Project deleted' : `${deleted.length} projects deleted`, tone: 'success' });
        if (failed > 0) {
          toast.show({ title: `I couldn’t delete ${plural(failed, 'project')}`, description: 'They’re still in your list. Try again in a moment.', tone: 'danger' });
        }
      },
    });
  };

  // Escape clears the selection unless a dialog or a rename field is handling it.
  const hasSelection = selection.ids.size > 0;
  const setSelection = selection.set;
  useEffect(() => {
    if (!hasSelection || deleteTargets.length > 0) return;
    const onKey = (event: globalThis.KeyboardEvent) => {
      if (event.key === 'Escape' && !event.defaultPrevented) setSelection([]);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [hasSelection, deleteTargets.length, setSelection]);

  const onResultsKeyDown = (event: KeyboardEvent<HTMLElement>) => {
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'a' && !(event.target as HTMLElement).closest('input:not([type=checkbox]), textarea')) {
      event.preventDefault();
      selection.set(items.map((v) => v.project.id));
    }
  };

  const loaded = list.data !== undefined;
  const empty = loaded && views.length === 0;

  return (
    <div className="mx-auto flex w-full max-w-screen-2xl flex-col gap-6 px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div className="flex min-w-0 flex-col gap-1">
          <h1 className="text-cn-title-lg font-semibold text-cn-fg">Projects</h1>
          <p className="text-cn-body text-cn-fg-secondary">
            One project per long video.{loaded && views.length > 0 && <span className="font-cn-mono tabular-nums"> {summary(views)}.</span>}
          </p>
        </div>
        {!empty && (
          <Link href={NEW_VIDEO} className={buttonClasses({ variant: 'primary', size: 'md' })}>
            <Plus aria-hidden className="size-4" />
            New video
          </Link>
        )}
      </header>

      {!online && (
        <InlineAlert tone="info" title="You’re offline" live="status">
          You can still browse your projects. Renaming, downloading and deleting come back when you reconnect.
        </InlineAlert>
      )}

      {list.isPending ? (
        <ProjectsSkeleton />
      ) : !loaded ? (
        <EmptyState
          icon={<CircleAlert />}
          title="I couldn’t load your projects"
          description="Your projects and clips are safe. This is usually a connection problem."
          action={
            <Button variant="secondary" leadingIcon={<RotateCcw />} loading={list.isFetching} loadingLabel="Trying again" onClick={() => void list.refetch()}>
              Try again
            </Button>
          }
        />
      ) : empty ? (
        <FirstProject />
      ) : (
        <>
          {list.isError && (
            <InlineAlert
              tone="warning"
              title="This list may be out of date"
              action={
                <Button size="sm" variant="secondary" loading={list.isFetching} onClick={() => void list.refetch()}>
                  Refresh
                </Button>
              }
            >
              I couldn’t reach Clipnera just now, so you’re seeing the last list I loaded.
            </InlineAlert>
          )}
          <ProjectsToolbar filters={filters} counts={counts} onChange={setFilters} />
          <section aria-label="Projects" onKeyDown={onResultsKeyDown} className="flex flex-col gap-4">
            {items.length === 0 ? (
              <EmptyState
                icon={<Search />}
                title={filters.q.trim() ? `No projects match “${filters.q.trim()}”` : 'No projects match these filters'}
                description="Try another word, or clear the search and filters."
                action={
                  hasNarrowing(filters) && (
                    <Button variant="secondary" onClick={() => setFilters(clearedFilters(filters))}>
                      Clear filters
                    </Button>
                  )
                }
              />
            ) : (
              <ul className={filters.view === 'grid' ? GRID_CLASS : 'flex flex-col gap-1'}>
                {items.map((view) => {
                  const Item = filters.view === 'grid' ? ProjectTile : ProjectRow;
                  return (
                    <Item
                      key={view.project.id}
                      view={view}
                      actions={actions}
                      selected={selection.ids.has(view.project.id)}
                      selecting={hasSelection}
                      onToggle={selection.toggle}
                      renaming={renamingId === view.project.id}
                      onRenameSave={(title) => saveRename(view, title)}
                      onRenameCancel={() => setRenamingId(null)}
                    />
                  );
                })}
              </ul>
            )}
            {selected.length > 0 && (
              <SelectionBar selected={selected} actions={actions} downloading={download.isPending && busyId === null} onClear={() => selection.set([])} />
            )}
          </section>
        </>
      )}

      <DeleteProjectsDialog targets={deleteTargets} deleting={remove.isPending} onConfirm={confirmDelete} onClose={() => setDeleteTargets([])} />
    </div>
  );
}
