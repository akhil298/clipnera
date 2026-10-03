'use client';

import { useEffect, useId } from 'react';

import type { PromptContext } from '@/components/ui/ContextChip';
import { cx, floatingSurface } from '@/lib/design/styles';

export interface SlashCommand {
  command: string;
  description: string;
  /** Fills the prompt bar for the person to edit. Never sends (01 §4). */
  template: (contexts: ReadonlyArray<PromptContext>) => string;
  group: 'Edit' | 'Go to';
}

/** The 01 §4 command set. `/go` entries navigate; nothing else runs on selection. */
export const SLASH_COMMANDS: ReadonlyArray<SlashCommand> = [
  { command: '/clips', description: 'Find the best moments', template: () => 'Find the 5 best moments about ', group: 'Edit' },
  { command: '/captions', description: 'Add or restyle captions', template: () => 'Add captions in my brand style', group: 'Edit' },
  { command: '/trim', description: 'Remove silences, fillers and retakes', template: () => 'Remove silences and fillers, balanced', group: 'Edit' },
  { command: '/reframe', description: 'Change aspect ratio and tracking', template: () => 'Reframe to 9:16 and follow the speaker', group: 'Edit' },
  {
    command: '/broll',
    description: 'Add B-roll from your uploads or the Clipnera library',
    template: (contexts) => {
      const range = contexts.find((context) => context.kind === 'range');
      if (contexts.some((context) => context.kind === 'asset')) return 'Use this clip at ';
      return range ? `Add B-roll of  over ${range.label}` : 'Add B-roll of  at ';
    },
    group: 'Edit',
  },
  { command: '/hook', description: 'Write or change the opening hook', template: () => 'Write a hook that lands in under 2 seconds', group: 'Edit' },
  { command: '/audio', description: 'Clean up or level audio', template: () => 'Clean up the audio and level my voice', group: 'Edit' },
  { command: '/music', description: 'Add or change music', template: () => 'Add calm music under my voice', group: 'Edit' },
  { command: '/export', description: 'Export with given settings', template: () => 'Export for Instagram Reels at 1080p', group: 'Edit' },
  { command: '/undo', description: 'Undo the last AI edit', template: () => 'Undo the last edit', group: 'Edit' },
  { command: '/go projects', description: 'Go to your projects', template: () => '', group: 'Go to' },
  { command: '/go library', description: 'Go to the library', template: () => '', group: 'Go to' },
  { command: '/go brand kit', description: 'Go to brand kit', template: () => '', group: 'Go to' },
  { command: '/go settings', description: 'Go to settings', template: () => '', group: 'Go to' },
];

export function filterCommands(query: string): SlashCommand[] {
  const needle = query.toLowerCase().replace(/^\//, '');
  return SLASH_COMMANDS.filter((item) => item.command.slice(1).startsWith(needle) || item.description.toLowerCase().includes(needle));
}

/** Highlights the characters that matched, in `fg`; the rest stays muted. */
function Match({ text, query }: { text: string; query: string }) {
  const needle = query.replace(/^\//, '');
  if (!needle || !text.slice(1).startsWith(needle)) return <>{text}</>;
  return (
    <>
      <span className="text-cn-fg">/{needle}</span>
      {text.slice(needle.length + 1)}
    </>
  );
}

/**
 * Design-system addition (02 §4.3). A listbox attached above the prompt bar;
 * the textarea is the combobox (`aria-activedescendant`), so typing keeps
 * filtering. ↑↓ move, Enter or Tab fill, Escape closes and leaves the text.
 * Max 8 rows visible, then scroll.
 */
export function SlashMenu({
  query,
  items,
  activeIndex,
  onPick,
  onHover,
  textarea,
  className,
}: {
  query: string;
  items: ReadonlyArray<SlashCommand>;
  activeIndex: number;
  onPick: (item: SlashCommand) => void;
  onHover: (index: number) => void;
  /** The prompt textarea, which becomes the combobox while the menu is open. */
  textarea: HTMLTextAreaElement | null;
  className?: string;
}) {
  const id = useId();
  const optionId = (index: number) => `${id}-option-${index}`;

  useEffect(() => {
    if (!textarea) return;
    textarea.setAttribute('role', 'combobox');
    textarea.setAttribute('aria-expanded', 'true');
    textarea.setAttribute('aria-controls', id);
    textarea.setAttribute('aria-autocomplete', 'list');
    if (items[activeIndex]) textarea.setAttribute('aria-activedescendant', optionId(activeIndex));
    return () => {
      ['role', 'aria-expanded', 'aria-controls', 'aria-autocomplete', 'aria-activedescendant'].forEach((name) => textarea.removeAttribute(name));
    };
  });

  let lastGroup = '';
  return (
    <div className={cx('z-cn-popover max-h-80 overflow-y-auto p-1', floatingSurface, className)}>
      {items.length === 0 ? (
        <p className="px-2.5 py-2 text-cn-label text-cn-fg-muted">No command matches</p>
      ) : (
        <ul id={id} role="listbox" aria-label="Commands">
          {items.map((item, index) => {
            const header = item.group !== lastGroup && index > 0 ? item.group : null;
            lastGroup = item.group;
            return (
              <li key={item.command} role="presentation">
                {header && (
                  <p role="presentation" className="px-2.5 pb-1 pt-2 text-cn-caption font-semibold text-cn-fg-muted">
                    {header}
                  </p>
                )}
                <div
                  id={optionId(index)}
                  role="option"
                  aria-selected={index === activeIndex}
                  onPointerDown={(event) => {
                    event.preventDefault();
                    onPick(item);
                  }}
                  onPointerEnter={() => onHover(index)}
                  className={cx(
                    'flex cursor-pointer items-baseline gap-3 rounded-cn-sm px-2.5 py-1.5',
                    index === activeIndex ? 'bg-cn-surface-hover' : '',
                  )}
                >
                  <span className="w-28 shrink-0 font-cn-mono text-cn-label text-cn-fg-secondary">
                    <Match text={item.command} query={query} />
                  </span>
                  <span className="min-w-0 truncate text-cn-label text-cn-fg-secondary">{item.description}</span>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
