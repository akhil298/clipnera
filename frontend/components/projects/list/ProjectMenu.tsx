'use client';

import { Download, ExternalLink, MoreHorizontal, Pencil, Square, Trash2 } from 'lucide-react';

import { IconButton, Menu, type MenuEntry } from '@/components/ui';
import { cx } from '@/lib/design/styles';

import type { ProjectView } from './projectState';

/** Everything a card or row can do; the screen owns the state behind it. */
export interface ProjectActions {
  rename: (view: ProjectView) => void;
  download: (views: readonly ProjectView[]) => void;
  stop: (view: ProjectView) => void;
  remove: (views: readonly ProjectView[]) => void;
  /** The project whose clips are being packed, or that is stopping. */
  busyId: string | null;
  /** False while offline: writes are disabled, reading still works. */
  online: boolean;
}

export const canDownload = (view: ProjectView) => view.kind === 'ready' && view.clipCount > 0;

function entries(view: ProjectView, actions: ProjectActions): MenuEntry[] {
  const offline = !actions.online;
  const busy = actions.busyId === view.project.id;
  const items: MenuEntry[] = [{ id: 'rename', label: 'Rename', icon: <Pencil />, disabled: offline, onSelect: () => actions.rename(view) }];
  if (canDownload(view)) {
    items.push({ id: 'download', label: 'Download all clips', icon: <Download />, disabled: offline || busy, onSelect: () => actions.download([view]) });
  }
  if (view.kind === 'running') {
    items.push({ id: 'stop', label: 'Stop', icon: <Square />, disabled: offline || busy, onSelect: () => actions.stop(view) });
  }
  if (view.project.source_url) {
    const url = view.project.source_url;
    items.push({ id: 'source', label: 'Open the original video', icon: <ExternalLink />, onSelect: () => window.open(url, '_blank', 'noopener,noreferrer') });
  }
  items.push(
    { type: 'separator', id: 'sep' },
    { id: 'delete', label: 'Delete project', icon: <Trash2 />, danger: true, disabled: offline, onSelect: () => actions.remove([view]) },
  );
  return items;
}

/** The ⋯ menu: on hover or focus with a pointer, always on touch (07 §5.5). */
export function ProjectMenu({ view, actions, className }: { view: ProjectView; actions: ProjectActions; className?: string }) {
  return (
    <div
      className={cx(
        'relative z-cn-raised shrink-0 transition-opacity duration-cn-fast',
        '[@media(hover:hover)]:opacity-0 [@media(hover:hover)]:group-hover:opacity-100 [@media(hover:hover)]:group-focus-within:opacity-100 [@media(hover:hover)]:has-[[aria-expanded=true]]:opacity-100',
        className,
      )}
    >
      <Menu
        align="end"
        items={entries(view, actions)}
        trigger={(props) => <IconButton {...props} label={`More for ${view.project.title}`} icon={<MoreHorizontal />} size="sm" />}
      />
    </div>
  );
}
