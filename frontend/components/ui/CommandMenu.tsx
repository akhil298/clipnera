'use client';

import { Search } from 'lucide-react';
import { type ReactNode, useEffect, useId, useRef } from 'react';

import { cx } from '@/lib/design/styles';
import { useControllableState } from '@/lib/design/useControllableState';
import { useListNavigation } from '@/lib/design/useListNavigation';

import { Kbd } from './Kbd';
import { ModalLayer } from './ModalLayer';
import { WorkingText } from './WorkingText';

export interface CommandItem {
  id: string;
  label: string;
  /** One line under or beside the label. */
  description?: string;
  icon?: ReactNode;
  /** Display only, e.g. `['G', 'P']`. */
  shortcut?: readonly string[];
  /** Right-aligned extra: a status, a count, "/captions". */
  meta?: ReactNode;
  /** Extra words that should match the filter ("billing" for Plans). */
  keywords?: ReadonlyArray<string>;
  disabled?: boolean;
  /** Runs on choose, after `onSelect` on the list. */
  onSelect?: () => void;
}

export interface CommandGroup {
  id: string;
  /** "Go to", "Recent projects", "Ask Clipnera". */
  label?: string;
  items: ReadonlyArray<CommandItem>;
}

/** Case-insensitive match on label, description and keywords. Empty groups drop out. */
export function filterCommandGroups(groups: ReadonlyArray<CommandGroup>, query: string): CommandGroup[] {
  const q = query.trim().toLowerCase();
  if (!q) return groups.filter((group) => group.items.length > 0);
  return groups
    .map((group) => ({
      ...group,
      items: group.items.filter((item) => [item.label, item.description ?? '', ...(item.keywords ?? [])].some((text) => text.toLowerCase().includes(q))),
    }))
    .filter((group) => group.items.length > 0);
}

export const commandOptionId = (listId: string, itemId: string) => `${listId}-option-${itemId}`;

/**
 * Filtering plus keyboard state for a combobox over CommandGroups. Use with
 * CommandList when the input is your own (the PromptBar slash menu), or use
 * CommandMenu for the ⌘K dialog.
 */
export function useCommandList(groups: ReadonlyArray<CommandGroup>, query: string, onSelect: (item: CommandItem) => void, filter = true) {
  const shown = filter ? filterCommandGroups(groups, query) : groups.filter((group) => group.items.length > 0);
  const enabled = shown.flatMap((group) => group.items).filter((item) => !item.disabled);
  const select = (item: CommandItem) => {
    if (item.disabled) return;
    onSelect(item);
    item.onSelect?.();
  };
  const navigation = useListNavigation(
    enabled.map((item) => item.id),
    (id) => {
      const item = enabled.find((candidate) => candidate.id === id);
      if (item) select(item);
    },
  );
  return { groups: shown, select, ...navigation };
}

function Highlight({ text, query }: { text: string; query: string }) {
  const q = query.trim();
  const at = q ? text.toLowerCase().indexOf(q.toLowerCase()) : -1;
  if (at < 0) return <>{text}</>;
  return (
    <>
      {text.slice(0, at)}
      <span className="font-semibold text-cn-fg">{text.slice(at, at + q.length)}</span>
      {text.slice(at + q.length)}
    </>
  );
}

export interface CommandListProps {
  /** The listbox id; point the input's `aria-controls` at it. */
  id: string;
  /** Accessible name: "Commands", "Go to". */
  label: string;
  groups: ReadonlyArray<CommandGroup>;
  activeId: string | null;
  onActiveChange: (id: string) => void;
  onChoose: (item: CommandItem) => void;
  /** Bolds the matched part of each label. */
  query?: string;
  /** Results are on their way (server search). */
  loading?: boolean;
  emptyText?: ReactNode;
  className?: string;
}

/** The listbox half of a combobox: grouped options, an active row, empty and loading states. */
export function CommandList({ id, label, groups, activeId, onActiveChange, onChoose, query = '', loading = false, emptyText = 'Nothing matches', className }: CommandListProps) {
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!activeId) return;
    listRef.current?.querySelector(`#${CSS.escape(commandOptionId(id, activeId))}`)?.scrollIntoView({ block: 'nearest' });
  }, [activeId, id]);

  const empty = groups.length === 0;

  return (
    <div ref={listRef} className={cx('overflow-y-auto p-1', className)}>
      <div id={id} role="listbox" aria-label={label} aria-busy={loading || undefined}>
        {groups.map((group) => (
          <div key={group.id} role="group" aria-labelledby={group.label ? `${id}-group-${group.id}` : undefined}>
            {group.label && (
              <div id={`${id}-group-${group.id}`} role="presentation" className="px-2.5 pb-1 pt-2 text-cn-caption font-semibold text-cn-fg-muted">
                {group.label}
              </div>
            )}
            {group.items.map((item) => {
              const active = item.id === activeId;
              return (
                <div
                  key={item.id}
                  id={commandOptionId(id, item.id)}
                  role="option"
                  aria-selected={active}
                  aria-disabled={item.disabled || undefined}
                  onPointerDown={(event) => event.preventDefault()}
                  onPointerMove={() => !item.disabled && !active && onActiveChange(item.id)}
                  onClick={() => onChoose(item)}
                  className={cx(
                    'flex min-h-9 items-center gap-2.5 rounded-cn-sm px-2.5 py-1.5 text-cn-body [&_svg]:size-4',
                    item.disabled ? 'cursor-not-allowed text-cn-fg-disabled' : 'cursor-pointer text-cn-fg-secondary',
                    active && 'bg-cn-surface-hover text-cn-fg',
                  )}
                >
                  {item.icon && (
                    <span aria-hidden className={cx('inline-flex shrink-0', active ? 'text-cn-accent-text' : 'text-cn-fg-muted')}>
                      {item.icon}
                    </span>
                  )}
                  <span className="flex min-w-0 flex-1 flex-col sm:flex-row sm:items-baseline sm:gap-2">
                    <span className="truncate text-cn-fg">
                      <Highlight text={item.label} query={query} />
                    </span>
                    {item.description && <span className="truncate text-cn-label text-cn-fg-muted">{item.description}</span>}
                  </span>
                  {item.meta && <span className="shrink-0 text-cn-caption text-cn-fg-muted">{item.meta}</span>}
                  {item.shortcut && (
                    <span aria-hidden className="hidden shrink-0 sm:inline-flex">
                      <Kbd keys={item.shortcut} />
                    </span>
                  )}
                </div>
              );
            })}
          </div>
        ))}
      </div>
      {loading && <WorkingText className="block px-2.5 py-2 text-cn-label">Searching</WorkingText>}
      {empty && !loading && <p className="px-2.5 py-6 text-center text-cn-label text-cn-fg-muted">{emptyText}</p>}
      <span role="status" className="sr-only">
        {loading ? '' : empty ? String(emptyText) : `${groups.reduce((n, group) => n + group.items.length, 0)} results`}
      </span>
    </div>
  );
}

export interface CommandMenuProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  groups: ReadonlyArray<CommandGroup>;
  /** Called with the chosen item; the menu closes unless `keepOpen` is set. */
  onSelect: (item: CommandItem) => void;
  /** Control the text when results come from the server; leave out to filter `groups` locally. */
  query?: string;
  onQueryChange?: (query: string) => void;
  /** Local filtering on (default) or off (server already filtered). */
  filter?: boolean;
  loading?: boolean;
  placeholder?: string;
  /** Dialog name, read on open. */
  label?: string;
  emptyText?: ReactNode;
  /** Something above the list, e.g. "Ask Clipnera: <query>" as a first action. */
  header?: ReactNode;
  keepOpen?: boolean;
}

/**
 * The ⌘K palette: one field that goes anywhere or asks Clipnera. A modal
 * combobox: focus stays in the field, ↑↓ move, Enter chooses, Escape closes and
 * returns focus. Bind ⌘K/Ctrl+K at the shell; this component does not.
 */
export function CommandMenu({
  open,
  onOpenChange,
  groups,
  onSelect,
  query,
  onQueryChange,
  filter = true,
  loading = false,
  placeholder = 'Ask Clipnera, or type / to go',
  label = 'Command menu',
  emptyText,
  header,
  keepOpen = false,
}: CommandMenuProps) {
  const id = useId();
  const listId = `${id}-list`;
  const [text, setText] = useControllableState(query, '', onQueryChange);
  const list = useCommandList(groups, text, (item) => {
    onSelect(item);
    if (!keepOpen) onOpenChange(false);
  }, filter);

  useEffect(() => {
    if (open && query === undefined) setText('');
    // Reset the uncontrolled text each time the menu opens.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  return (
    <ModalLayer
      open={open}
      onClose={() => onOpenChange(false)}
      labelledBy={`${id}-title`}
      layer="dialog"
      motion="pop"
      placement="items-start justify-center px-4 pt-16 sm:pt-24"
      panelClassName="w-full max-w-xl overflow-hidden rounded-cn-xl"
    >
      <h2 id={`${id}-title`} className="sr-only">
        {label}
      </h2>
      <div className="flex items-center gap-2.5 border-b border-cn-border px-4">
        <Search aria-hidden className="size-4 shrink-0 text-cn-fg-muted" />
        <input
          data-autofocus
          role="combobox"
          aria-expanded
          aria-controls={listId}
          aria-autocomplete="list"
          aria-activedescendant={list.activeId ? commandOptionId(listId, list.activeId) : undefined}
          aria-label={label}
          value={text}
          onChange={(event) => setText(event.target.value)}
          onKeyDown={list.onKeyDown}
          placeholder={placeholder}
          className="h-12 min-w-0 flex-1 bg-transparent text-cn-body-lg text-cn-fg placeholder:text-cn-fg-muted focus-visible:outline-none"
        />
      </div>
      {header}
      <CommandList
        id={listId}
        label={label}
        groups={list.groups}
        activeId={list.activeId}
        onActiveChange={list.setActiveId}
        onChoose={list.select}
        query={text}
        loading={loading}
        emptyText={emptyText}
        className="max-h-80"
      />
      <div aria-hidden className="hidden items-center gap-4 border-t border-cn-border px-4 py-2 text-cn-caption text-cn-fg-muted sm:flex">
        <span className="inline-flex items-center gap-1.5">
          <Kbd keys={['↑']} />
          <Kbd keys={['↓']} /> move
        </span>
        <span className="inline-flex items-center gap-1.5">
          <Kbd keys={['↵']} /> choose
        </span>
        <span className="inline-flex items-center gap-1.5">
          <Kbd keys={['esc']} /> close
        </span>
      </div>
    </ModalLayer>
  );
}
