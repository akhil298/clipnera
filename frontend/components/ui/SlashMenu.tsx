'use client';

import { cx, floatingSurface } from '@/lib/design/styles';

import { type CommandGroup, type CommandItem, CommandList } from './CommandMenu';
import type { PromptContext } from './ContextChip';

export interface SlashCommand {
  /** "/captions", "/go library". Also the option's id. */
  command: string;
  description: string;
  group: 'Edit' | 'Go to';
  /** Text the prompt is filled with, for the person to finish. Choosing a command never sends (01 §4). */
  template?: (contexts: ReadonlyArray<PromptContext>) => string;
  /** Where a "Go to" command navigates. The caller routes in `onSlashCommand`. */
  href?: string;
}

/** The 01 §4 command set: edits fill an editable template, `/go` entries navigate. */
export const SLASH_COMMANDS: ReadonlyArray<SlashCommand> = [
  { command: '/clips', description: 'Find the best moments', group: 'Edit', template: () => 'Find the 5 best moments about ' },
  { command: '/captions', description: 'Add or restyle captions', group: 'Edit', template: () => 'Add captions in my brand style' },
  { command: '/trim', description: 'Remove silences, fillers and retakes', group: 'Edit', template: () => 'Remove silences and fillers, balanced' },
  { command: '/reframe', description: 'Change aspect ratio and tracking', group: 'Edit', template: () => 'Reframe to 9:16 and follow the speaker' },
  {
    command: '/broll',
    description: 'Add B-roll from your uploads or the Clipnera library',
    group: 'Edit',
    template: (contexts) => {
      if (contexts.some((context) => context.kind === 'asset')) return 'Use this clip at ';
      const range = contexts.find((context) => context.kind === 'range');
      return range ? `Add B-roll of  over ${range.label}` : 'Add B-roll of  at ';
    },
  },
  { command: '/hook', description: 'Write or change the opening hook', group: 'Edit', template: () => 'Write a hook that lands in under 2 seconds' },
  { command: '/audio', description: 'Clean up or level audio', group: 'Edit', template: () => 'Clean up the audio and level my voice' },
  { command: '/music', description: 'Add or change music', group: 'Edit', template: () => 'Add calm music under my voice' },
  { command: '/export', description: 'Export with given settings', group: 'Edit', template: () => 'Export for Instagram Reels at 1080p' },
  { command: '/undo', description: 'Undo the last AI edit', group: 'Edit', template: () => 'Undo the last edit' },
  { command: '/go projects', description: 'Go to your projects', group: 'Go to', href: '/dashboard/projects' },
  { command: '/go library', description: 'Go to the library', group: 'Go to', href: '/dashboard/library' },
  { command: '/go brand kit', description: 'Go to brand kit', group: 'Go to', href: '/dashboard/brand-kit' },
  { command: '/go settings', description: 'Go to settings', group: 'Go to', href: '/dashboard/settings' },
];

/** Longest text still treated as a command being typed. */
const MAX_QUERY = 24;

/** True while the prompt is a command being typed ("/", "/cap", "/go li"). */
export const isSlashQuery = (text: string) => text.startsWith('/') && text.length < MAX_QUERY && !text.includes('\n');

/** Commands as CommandList groups, in their given order. */
export function slashGroups(commands: ReadonlyArray<SlashCommand>): CommandGroup[] {
  const toItem = (command: SlashCommand): CommandItem => ({ id: command.command, label: command.command, description: command.description });
  return (['Edit', 'Go to'] as const).map((group) => ({
    id: group,
    label: commands.some((command) => command.group !== group) ? group : undefined,
    items: commands.filter((command) => command.group === group).map(toItem),
  }));
}

export interface SlashMenuProps {
  /** Listbox id; the prompt textarea points `aria-controls` at it. */
  id: string;
  /** Already filtered, from `useCommandList(slashGroups(...), text, …)`. */
  groups: ReadonlyArray<CommandGroup>;
  activeId: string | null;
  onActiveChange: (id: string) => void;
  onChoose: (item: CommandItem) => void;
  /** The typed text, to bold the match. */
  query: string;
  className?: string;
}

/**
 * The `/` command list attached above the prompt (02 §4.3). The textarea stays
 * the combobox, so typing keeps filtering: ↑↓ move, Enter or Tab fill, Escape
 * closes and keeps the text. PromptBar renders it when given `slashCommands`.
 */
export function SlashMenu({ id, groups, activeId, onActiveChange, onChoose, query, className }: SlashMenuProps) {
  return (
    <div className={cx('z-cn-popover overflow-hidden', floatingSurface, className)}>
      <CommandList
        id={id}
        label="Commands"
        groups={groups}
        activeId={activeId}
        onActiveChange={onActiveChange}
        onChoose={onChoose}
        query={query}
        emptyText="No command matches. Keep typing to send it as a prompt."
        className="max-h-80"
      />
    </div>
  );
}
