'use client';

import { ArrowDown, ArrowUp, Pencil, X } from 'lucide-react';
import { type KeyboardEvent, useState } from 'react';

import { ContextChip } from '@/components/ui/ContextChip';
import { IconButton } from '@/components/ui/IconButton';
import { cx, focusRing } from '@/lib/design/styles';

import type { QueuedPrompt } from './run/useRunSimulator';

/**
 * Design-system addition (02 §4.7). Prompts waiting behind the current run, in
 * the order they will run. Edit inline (Enter saves, Escape cancels), move
 * with buttons so it works by keyboard, remove. Collapses to one line when
 * more than two wait. Reorders are announced politely.
 */
export function PromptQueue({
  items,
  onChange,
  className,
}: {
  items: ReadonlyArray<QueuedPrompt>;
  onChange: (items: QueuedPrompt[]) => void;
  className?: string;
}) {
  const [expanded, setExpanded] = useState(false);
  const [editing, setEditing] = useState<string | null>(null);
  const [draft, setDraft] = useState('');
  const [announcement, setAnnouncement] = useState('');

  if (items.length === 0) return null;
  const collapsed = items.length > 2 && !expanded;

  const move = (index: number, by: number) => {
    const next = [...items];
    const [item] = next.splice(index, 1);
    next.splice(index + by, 0, item);
    onChange(next);
    setAnnouncement(`Moved to position ${index + by + 1}`);
  };

  const save = (id: string) => {
    onChange(items.map((item) => (item.id === id ? { ...item, prompt: draft.trim() || item.prompt } : item)));
    setEditing(null);
  };

  const onEditKey = (event: KeyboardEvent<HTMLInputElement>, id: string) => {
    if (event.key === 'Enter') {
      event.preventDefault();
      save(id);
    } else if (event.key === 'Escape') {
      event.preventDefault();
      setEditing(null);
    }
  };

  return (
    <section aria-label="Up next" className={cx('rounded-cn-lg border border-cn-border bg-cn-surface', className)}>
      <span className="sr-only" role="status" aria-live="polite">
        {announcement}
      </span>
      <div className="flex h-8 items-center gap-2 px-3">
        <span className="text-cn-caption font-semibold text-cn-fg-secondary">Up next · {items.length}</span>
        <span className="flex-1" />
        {items.length > 2 && (
          <button
            type="button"
            aria-expanded={expanded}
            onClick={() => setExpanded(!expanded)}
            className={cx('rounded-cn-xs text-cn-caption font-semibold text-cn-fg-secondary hover:text-cn-fg', focusRing)}
          >
            {expanded ? 'Hide' : 'Show'}
          </button>
        )}
      </div>
      {collapsed ? (
        <p className="truncate border-t border-cn-border px-3 py-2 text-cn-label text-cn-fg-muted">{items.length} waiting · first: {items[0].prompt}</p>
      ) : (
        <ol aria-label="Queued prompts" className="flex flex-col border-t border-cn-border">
          {items.map((item, index) => (
            <li key={item.id} className="flex items-start gap-2 border-b border-cn-border px-3 py-2 last:border-b-0">
              <span className="mt-0.5 w-4 shrink-0 font-cn-mono text-cn-caption tabular-nums text-cn-fg-muted">{index + 1}</span>
              <div className="min-w-0 flex-1 space-y-1">
                {editing === item.id ? (
                  <input
                    autoFocus
                    aria-label={`Edit queued prompt ${index + 1}`}
                    value={draft}
                    onChange={(event) => setDraft(event.target.value)}
                    onKeyDown={(event) => onEditKey(event, item.id)}
                    onBlur={() => save(item.id)}
                    className={cx('h-7 w-full rounded-cn-sm border border-cn-control-border bg-cn-field px-2 text-cn-label text-cn-fg', focusRing)}
                  />
                ) : (
                  <p className="truncate text-cn-label text-cn-fg">{item.prompt}</p>
                )}
                {item.chips.length > 0 && (
                  <div className="flex flex-wrap gap-1">
                    {item.chips.map((chip) => (
                      <ContextChip key={chip.id} context={chip} className="h-6" />
                    ))}
                  </div>
                )}
              </div>
              <div className="flex shrink-0 items-center">
                <IconButton
                  size="sm"
                  label={`Edit “${item.prompt}”`}
                  icon={<Pencil />}
                  onClick={() => {
                    setDraft(item.prompt);
                    setEditing(item.id);
                  }}
                />
                <IconButton size="sm" label="Move up" icon={<ArrowUp />} disabled={index === 0} onClick={() => move(index, -1)} />
                <IconButton size="sm" label="Move down" icon={<ArrowDown />} disabled={index === items.length - 1} onClick={() => move(index, 1)} />
                <IconButton size="sm" label={`Remove “${item.prompt}” from the queue`} icon={<X />} onClick={() => onChange(items.filter((other) => other.id !== item.id))} />
              </div>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
