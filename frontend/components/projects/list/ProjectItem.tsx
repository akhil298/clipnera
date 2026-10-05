'use client';

import Link from 'next/link';
import type { MouseEvent } from 'react';

import { Badge, Checkbox, cardLinkOverlay, VideoThumb } from '@/components/ui';
import { cx } from '@/lib/design/styles';
import { formatRelativeTime } from '@/lib/utils/dates';

import { ProjectMenu, type ProjectActions } from './ProjectMenu';
import { plural, type ProjectView } from './projectState';
import { RenameField } from './RenameField';

export interface ProjectItemProps {
  view: ProjectView;
  actions: ProjectActions;
  selected: boolean;
  /** Something is selected: checkboxes stay visible on every item. */
  selecting: boolean;
  onToggle: (id: string, range: boolean) => void;
  renaming: boolean;
  onRenameSave: (title: string) => void;
  onRenameCancel: () => void;
}

/** One ring around the whole item when its title link has keyboard focus. */
const LINK_FOCUS =
  'has-[[data-card-link]:focus-visible]:outline has-[[data-card-link]:focus-visible]:outline-2 has-[[data-card-link]:focus-visible]:outline-offset-2 has-[[data-card-link]:focus-visible]:outline-cn-focus';

function meta(view: ProjectView): string {
  const when = view.project.created_at ? formatRelativeTime(view.project.created_at) : '';
  return [view.source, view.clipCount > 0 ? plural(view.clipCount, 'clip') : '', when].filter(Boolean).join(' · ');
}

function StatusBadgeFor({ view }: { view: ProjectView }) {
  const running = view.kind === 'running';
  return (
    <Badge tone={view.tone} dot={running} pulse={running} className="max-w-full">
      <span className="truncate">{view.label}</span>
    </Badge>
  );
}

function SelectBox({ view, selected, selecting, onToggle }: Pick<ProjectItemProps, 'view' | 'selected' | 'selecting' | 'onToggle'>) {
  return (
    <span
      className={cx(
        'relative z-cn-raised rounded-cn-sm bg-cn-surface-raised/90 px-1.5 py-1 transition-opacity duration-cn-fast',
        !selecting && !selected && '[@media(hover:hover)]:opacity-0 [@media(hover:hover)]:group-hover:opacity-100 [@media(hover:hover)]:group-focus-within:opacity-100',
      )}
    >
      <Checkbox
        label={<span className="sr-only">Select {view.project.title}</span>}
        checked={selected}
        onChange={() => undefined}
        onClick={(event: MouseEvent<HTMLInputElement>) => onToggle(view.project.id, event.shiftKey)}
      />
    </span>
  );
}

function Title({ view, renaming, onRenameSave, onRenameCancel, className }: Pick<ProjectItemProps, 'view' | 'renaming' | 'onRenameSave' | 'onRenameCancel'> & { className?: string }) {
  if (renaming) return <RenameField title={view.project.title} onSave={onRenameSave} onCancel={onRenameCancel} />;
  return (
    <Link href={view.href} data-card-link className={cx(cardLinkOverlay, 'text-cn-label font-medium text-cn-fg hover:text-cn-fg', className)}>
      {view.project.title}
    </Link>
  );
}

function FailedNote({ view }: { view: ProjectView }) {
  if (view.kind === 'failed') return <p className="text-cn-caption text-cn-danger-text">Clips weren’t finished. Your video is safe; open the project to see what happened.</p>;
  if (view.kind === 'stopped') return <p className="text-cn-caption text-cn-fg-muted">You stopped this run. Your video is kept.</p>;
  return null;
}

/** Grid tile: a chromeless 16:9 poster with the status on it, title and meta below (07 §5.5). */
export function ProjectTile(props: ProjectItemProps) {
  const { view, actions, selected } = props;
  const duration = view.project.duration_seconds;
  return (
    <li className={cx('group relative flex flex-col gap-2 rounded-cn-lg', LINK_FOCUS)}>
      <VideoThumb
        aspect="16:9"
        rounded="lg"
        poster={view.poster}
        duration={duration > 0 ? duration : undefined}
        dimmed={view.kind === 'running' || view.kind === 'failed'}
        selected={selected}
        topLeft={<StatusBadgeFor view={view} />}
        className="cn-media-edge"
      />
      {/* Outside VideoThumb: its slots sit in an isolated layer under the title link's whole-tile overlay. */}
      <div className="absolute right-1.5 top-1.5">
        <SelectBox {...props} />
      </div>
      <div className="flex items-start gap-1">
        <div className="flex min-w-0 flex-1 flex-col gap-0.5">
          <Title {...props} className="line-clamp-2" />
          <p className="truncate text-cn-caption text-cn-fg-muted">{meta(view)}</p>
          <FailedNote view={view} />
        </div>
        <ProjectMenu view={view} actions={actions} />
      </div>
    </li>
  );
}

/** List row: small poster, title, live status and meta, the same menu. */
export function ProjectRow(props: ProjectItemProps) {
  const { view, actions, selected } = props;
  return (
    <li
      className={cx(
        'group relative flex items-center gap-3 rounded-cn-lg p-2 transition-colors duration-cn-fast hover:bg-cn-surface-hover',
        selected && 'bg-cn-surface-active hover:bg-cn-surface-active',
        LINK_FOCUS,
      )}
    >
      <SelectBox {...props} />
      <VideoThumb
        aspect="16:9"
        rounded="md"
        poster={view.poster}
        duration={view.project.duration_seconds > 0 ? view.project.duration_seconds : undefined}
        selected={selected}
        className="cn-media-edge w-24 shrink-0"
      />
      <div className="flex min-w-0 flex-1 flex-col gap-1">
        <Title {...props} className="truncate" />
        <div className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1">
          <StatusBadgeFor view={view} />
          <span className={cx('truncate text-cn-caption', selected ? 'text-cn-fg-secondary' : 'text-cn-fg-muted')}>{meta(view)}</span>
        </div>
        <FailedNote view={view} />
      </div>
      <ProjectMenu view={view} actions={actions} />
    </li>
  );
}
