'use client';

import { Bookmark, BookmarkCheck, Eye, MoreHorizontal, RotateCcw } from 'lucide-react';
import { type KeyboardEvent, useState } from 'react';

import { cx, focusRing } from '@/lib/design/styles';

import { Badge } from './Badge';
import { Button } from './Button';
import { IconButton } from './IconButton';
import { Menu, type MenuEntry } from './Menu';
import { Tooltip } from './Tooltip';
import { WorkingText } from './WorkingText';

export interface VersionSummary {
  id: string;
  name: string;
  /** "You" or "Clipnera". */
  author: string;
  /** Relative time ("6 min ago") and the exact one for the tooltip. */
  time: string;
  exactTime: string;
  poster?: string;
  current?: boolean;
  bookmarked?: boolean;
  exported?: boolean;
  /** Made by restoring another version. */
  restored?: boolean;
}

export interface VersionItemProps {
  version: VersionSummary;
  viewing?: boolean;
  restoring?: boolean;
  onView: () => void;
  onRestore: () => void;
  onToggleBookmark: () => void;
  onRename: (name: string) => void;
  onCompare?: () => void;
  /** Scrolls the conversation to the prompt that made it. */
  onJumpToMessage?: () => void;
}

/**
 * One row of version history (02 §4.10, editor §10). Render inside an `<ol>`.
 * States: default, hover, current (amber edge), viewing (amber border),
 * restoring, renaming inline.
 */
export function VersionItem({ version, viewing = false, restoring = false, onView, onRestore, onToggleBookmark, onRename, onCompare, onJumpToMessage }: VersionItemProps) {
  const [renaming, setRenaming] = useState(false);
  const [draft, setDraft] = useState(version.name);

  const onKey = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'Enter') {
      onRename(draft.trim() || version.name);
      setRenaming(false);
    } else if (event.key === 'Escape') {
      event.stopPropagation();
      setDraft(version.name);
      setRenaming(false);
    }
  };

  const menu: MenuEntry[] = [
    {
      id: 'rename',
      label: 'Rename',
      onSelect: () => {
        setDraft(version.name);
        setRenaming(true);
      },
    },
    ...(onCompare && !version.current ? [{ id: 'compare', label: 'Compare with current', onSelect: onCompare }] : []),
    ...(onJumpToMessage ? [{ id: 'jump', label: 'Jump to message', onSelect: onJumpToMessage }] : []),
  ];

  return (
    <li
      className={cx(
        'relative flex gap-3 rounded-cn-md border p-2.5 transition-colors duration-cn-fast hover:bg-cn-surface-hover',
        viewing ? 'border-cn-accent-border' : 'border-transparent',
        version.current && 'before:absolute before:inset-y-2 before:left-0 before:w-0.5 before:rounded-cn-full before:bg-cn-accent',
      )}
    >
      <div className="cn-media-edge flex h-9 w-16 shrink-0 justify-center overflow-hidden rounded-cn-xs bg-cn-stage">
        {version.poster && <img src={version.poster} alt="" className="h-full object-contain" />}
      </div>
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
          <Tooltip content={version.exactTime}>
            <span tabIndex={0} className={cx('rounded-cn-xs font-cn-mono tabular-nums', focusRing)}>
              {version.time}
            </span>
          </Tooltip>
          {version.current && <Badge tone="accent">Current</Badge>}
          {version.bookmarked && <Badge>Bookmarked</Badge>}
          {version.exported && <Badge>Exported</Badge>}
          {version.restored && <Badge>Restored</Badge>}
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
        <Menu align="end" trigger={(props) => <IconButton {...props} size="sm" label={`More for ${version.name}`} icon={<MoreHorizontal />} />} items={menu} />
      </div>
    </li>
  );
}
