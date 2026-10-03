'use client';

import { Bookmark, BookmarkCheck, Eye, MoreHorizontal, RotateCcw } from 'lucide-react';
import { type KeyboardEvent, useState } from 'react';

import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { IconButton } from '@/components/ui/IconButton';
import { Menu } from '@/components/ui/Menu';
import { SegmentedControl } from '@/components/ui/SegmentedControl';
import { Tooltip } from '@/components/ui/Tooltip';
import { WorkingText } from '@/components/ui/WorkingText';
import { cx, focusRing } from '@/lib/design/styles';

import { Poster } from './MediaCard';
import type { VersionRow } from './sample';

export interface VersionItemProps {
  version: VersionRow;
  index: number;
  viewing: boolean;
  restoring: boolean;
  onView: () => void;
  onRestore: () => void;
  onToggleBookmark: () => void;
  onRename: (name: string) => void;
}

/**
 * Design-system addition (02 §4.10): one row of version history. States:
 * default, hover, current (amber left edge), viewing (amber border),
 * restoring (working text).
 */
export function VersionItem({ version, index, viewing, restoring, onView, onRestore, onToggleBookmark, onRename }: VersionItemProps) {
  const [renaming, setRenaming] = useState(false);
  const [draft, setDraft] = useState(version.name);
  const onKey = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'Enter') {
      onRename(draft.trim() || version.name);
      setRenaming(false);
    } else if (event.key === 'Escape') {
      event.stopPropagation();
      setRenaming(false);
    }
  };
  return (
    <li
      className={cx(
        'relative flex gap-3 rounded-cn-md border p-2.5 hover:bg-cn-surface-hover',
        viewing ? 'border-cn-accent-border' : 'border-transparent',
        version.current && 'before:absolute before:inset-y-2 before:left-0 before:w-0.5 before:rounded-cn-full before:bg-cn-accent',
      )}
    >
      <Poster tone={index} aspect="9:16" className="w-9 shrink-0 rounded-cn-xs" />
      <div className="min-w-0 flex-1 space-y-1">
        {renaming ? (
          <input
            autoFocus
            aria-label="Version name"
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={onKey}
            onBlur={() => setRenaming(false)}
            className={cx('h-7 w-full rounded-cn-sm border border-cn-control-border bg-cn-field px-2 text-cn-label', focusRing)}
          />
        ) : (
          <p className="truncate text-cn-label font-semibold text-cn-fg">{version.name}</p>
        )}
        <p className="flex flex-wrap items-center gap-1.5 text-cn-caption text-cn-fg-muted">
          <span>{version.author}</span>·
          <Tooltip content={version.exact}>
            <span tabIndex={0} className={cx('rounded-cn-xs font-cn-mono tabular-nums', focusRing)}>
              {version.time}
            </span>
          </Tooltip>
          {version.current && <Badge tone="accent">Current</Badge>}
          {version.bookmarked && <Badge>Bookmarked</Badge>}
        </p>
        {restoring ? (
          <p className="text-cn-caption">
            <WorkingText>Restoring</WorkingText>
          </p>
        ) : (
          <div className="flex flex-wrap items-center gap-1">
            <Button size="sm" variant="ghost" leadingIcon={<Eye />} onClick={onView} aria-pressed={viewing}>
              {viewing ? 'Viewing' : 'View'}
            </Button>
            {!version.current && (
              <Button size="sm" variant="ghost" leadingIcon={<RotateCcw />} onClick={onRestore}>
                Restore
              </Button>
            )}
          </div>
        )}
      </div>
      <div className="flex shrink-0 flex-col items-center gap-1">
        <IconButton
          size="sm"
          label={version.bookmarked ? 'Remove bookmark' : 'Bookmark this version'}
          pressed={version.bookmarked}
          icon={version.bookmarked ? <BookmarkCheck /> : <Bookmark />}
          onClick={onToggleBookmark}
        />
        <Menu
          align="end"
          trigger={(props) => <IconButton {...props} size="sm" label={`More for ${version.name}`} icon={<MoreHorizontal />} />}
          items={[
            { id: 'rename', label: 'Rename', onSelect: () => setRenaming(true) },
            { id: 'compare', label: 'Compare with current', onSelect: onView },
          ]}
        />
      </div>
    </li>
  );
}

/** The history list with its All / Bookmarked filter and the stated limits (01 §7). */
export function VersionHistoryList({
  versions,
  viewingId,
  restoringId,
  onView,
  onRestore,
  onToggleBookmark,
  onRename,
}: {
  versions: ReadonlyArray<VersionRow>;
  viewingId: string | null;
  restoringId: string | null;
  onView: (id: string) => void;
  onRestore: (id: string) => void;
  onToggleBookmark: (id: string) => void;
  onRename: (id: string, name: string) => void;
}) {
  const [filter, setFilter] = useState<'all' | 'bookmarked'>('all');
  const shown = filter === 'all' ? versions : versions.filter((version) => version.bookmarked);
  return (
    <div className="flex flex-col gap-3">
      <SegmentedControl
        label="Show"
        size="sm"
        value={filter}
        onValueChange={setFilter}
        options={[
          { value: 'all', label: `All · ${versions.length}` },
          { value: 'bookmarked', label: `Bookmarked · ${versions.filter((version) => version.bookmarked).length}` },
        ]}
      />
      {shown.length === 0 ? (
        <p className="text-cn-label text-cn-fg-muted">No bookmarks yet. Bookmark a version before a big change to find it fast.</p>
      ) : (
        <ol aria-label="Versions, newest first" className="flex flex-col gap-1">
          {shown.map((version, index) => (
            <VersionItem
              key={version.id}
              version={version}
              index={index}
              viewing={viewingId === version.id}
              restoring={restoringId === version.id}
              onView={() => onView(version.id)}
              onRestore={() => onRestore(version.id)}
              onToggleBookmark={() => onToggleBookmark(version.id)}
              onRename={(name) => onRename(version.id, name)}
            />
          ))}
        </ol>
      )}
      <p className="text-cn-caption text-cn-fg-muted">Restoring doesn’t unpublish posted clips or return credits. Nothing is deleted: later versions stay here.</p>
    </div>
  );
}
