'use client';

import { ArrowUp, ChevronDown, ListPlus, Plus, Square } from 'lucide-react';
import { type DragEvent, type KeyboardEvent, type ReactNode, type RefObject, useId, useMemo, useRef, useState } from 'react';

import { mergeRefs } from '@/lib/design/refs';
import { cx, focusRing, focusWithinRing } from '@/lib/design/styles';
import { useAutosize } from '@/lib/design/useAutosize';

import { commandOptionId, useCommandList } from './CommandMenu';
import { ContextChip, type PromptContext } from './ContextChip';
import { IconButton } from './IconButton';
import { Menu } from './Menu';
import { Popover } from './Popover';
import { isSlashQuery, type SlashCommand, SlashMenu, slashGroups } from './SlashMenu';
import { Tooltip } from './Tooltip';

export type PromptMode = 'edit' | 'ask' | 'plan';

const MODE_INFO: Record<PromptMode, { label: string; description: string }> = {
  edit: { label: 'Edit', description: 'changes the video' },
  ask: { label: 'Ask', description: 'answers, changes nothing' },
  plan: { label: 'Plan', description: 'you approve before it runs' },
};
const ALL_MODES: ReadonlyArray<PromptMode> = ['edit', 'ask', 'plan'];
const NO_COMMANDS: ReadonlyArray<SlashCommand> = [];

export interface PromptBarProps {
  value: string;
  onValueChange: (value: string) => void;
  /** Enter, or the send button. Called when there is text or at least one context chip. */
  onSubmit: () => void;
  /** Edit makes changes, Ask answers, Plan writes a plan to approve. Default `edit`. */
  mode?: PromptMode;
  onModeChange?: (mode: PromptMode) => void;
  /** Modes offered in the mode pill. Fewer than two hides it. Default: none for `hero`, all three for `docked`. */
  modes?: ReadonlyArray<PromptMode>;
  /** A run is active: the working edge sweeps, Stop shows, and Send adds to the queue. Typing stays allowed. */
  running?: boolean;
  /** Stops the run at the next safe point. Never clears the typed text. */
  onStop?: () => void;
  /** What the prompt applies to (source video, clip, range…). Empty means the whole project. */
  contexts?: ReadonlyArray<PromptContext>;
  onRemoveContext?: (id: string) => void;
  /** The + button's click. Use `attachMenu` instead to anchor a popover on it. */
  onAttach?: () => void;
  /** Popover content anchored on + (search + Upload video · Paste link · From library · Brand kit). */
  attachMenu?: ReactNode | ((close: () => void) => ReactNode);
  /** Name of the + button and its popover. */
  attachLabel?: string;
  /** Files dropped anywhere on the box. Turns on the drag-over state. */
  onDropFile?: (files: File[]) => void;
  /** Drag-over message. */
  dropLabel?: string;
  /** Credits the action will use, when known. Shown in Edit mode before sending (01 §3.10). */
  creditCost?: number;
  /** Replaces the credit hint, e.g. "Free · 17 of 20 left today" in Ask mode. */
  hint?: string;
  /** Prompts waiting behind the current run. */
  queueCount?: number;
  /** Typing `/` opens these as a menu; choosing one fills its template and never sends. */
  slashCommands?: ReadonlyArray<SlashCommand>;
  /** Called after a command is chosen (route `href` for "Go to" commands here). */
  onSlashCommand?: (command: SlashCommand) => void;
  /** Under the box: "Not sent · Retry", "Add credits", the viewing-an-older-version note. */
  footer?: ReactNode;
  /** `hero` on Home and landing (24 px radius, raised); `docked` in the editor and project. */
  size?: 'hero' | 'docked';
  placeholder?: string;
  disabled?: boolean;
  /** Why sending is off (offline, no credits): the Send tooltip. The text stays editable. */
  disabledReason?: string;
  /** Accessible name of the text area. */
  label?: string;
  ref?: RefObject<HTMLTextAreaElement | null>;
  className?: string;
}

function defaultPlaceholder(size: 'hero' | 'docked', mode: PromptMode, contexts: ReadonlyArray<PromptContext>): string {
  if (size === 'hero') return 'Paste a YouTube link or drop a video, then say what you want';
  const target = contexts.length === 0 ? 'the whole video' : contexts.length === 1 ? 'the selection' : `${contexts.length} selected items`;
  if (mode === 'ask') return `Ask about ${target}`;
  if (mode === 'plan') return `Describe what you want for ${target}. You approve the plan first.`;
  return `Describe an edit to ${target}`;
}

const hasFiles = (event: DragEvent) => event.dataTransfer.types.includes('Files');

/**
 * The composer (07 §6.1): one place to tell Clipnera what to do. Presentational:
 * the parent owns the text, mode, contexts and run state. Enter sends,
 * Shift+Enter adds a line, IME composition never sends early.
 */
export function PromptBar({
  value,
  onValueChange,
  onSubmit,
  mode = 'edit',
  onModeChange,
  modes,
  running = false,
  onStop,
  contexts = [],
  onRemoveContext,
  onAttach,
  attachMenu,
  attachLabel = 'Add a video, image, audio or link',
  onDropFile,
  dropLabel = 'Drop video to start',
  creditCost,
  hint: hintOverride,
  queueCount = 0,
  slashCommands,
  onSlashCommand,
  footer,
  size = 'docked',
  placeholder,
  disabled = false,
  disabledReason,
  label = 'Prompt',
  ref,
  className,
}: PromptBarProps) {
  const id = useId();
  const hintId = `${id}-hint`;
  const slashId = `${id}-commands`;
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const [dragging, setDragging] = useState(false);
  const [slashDismissed, setSlashDismissed] = useState(false);
  const hero = size === 'hero';
  useAutosize(textareaRef, value, hero ? 2 : 1, 8);

  const shownModes = modes ?? (hero ? [] : ALL_MODES);
  const hasText = value.trim().length > 0;
  const canSend = !disabled && !disabledReason && (hasText || contexts.length > 0);

  const commands = slashCommands ?? NO_COMMANDS;
  const groups = useMemo(() => slashGroups(commands), [commands]);
  const slashOpen = commands.length > 0 && !slashDismissed && isSlashQuery(value);
  const slash = useCommandList(groups, value, (item) => {
    const command = commands.find((candidate) => candidate.command === item.id);
    if (!command) return;
    setSlashDismissed(true);
    onValueChange(command.template?.(contexts) ?? '');
    onSlashCommand?.(command);
    textareaRef.current?.focus();
  });

  const send = () => {
    if (canSend) onSubmit();
  };

  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.nativeEvent.isComposing) return;
    if (slashOpen) {
      if (event.key === 'Escape') {
        event.preventDefault();
        setSlashDismissed(true);
        return;
      }
      if (event.key === 'Tab' && !event.shiftKey && slash.activeId) {
        event.preventDefault();
        const item = slash.groups.flatMap((group) => group.items).find((candidate) => candidate.id === slash.activeId);
        if (item) slash.select(item);
        return;
      }
      slash.onKeyDown(event);
      if (event.defaultPrevented) return;
    }
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      send();
    }
  };

  const dropHandlers = onDropFile
    ? {
        onDragOver: (event: DragEvent<HTMLDivElement>) => {
          if (!hasFiles(event) || disabled) return;
          event.preventDefault();
          setDragging(true);
        },
        onDragLeave: (event: DragEvent<HTMLDivElement>) => {
          if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setDragging(false);
        },
        onDrop: (event: DragEvent<HTMLDivElement>) => {
          if (!hasFiles(event) || disabled) return;
          event.preventDefault();
          setDragging(false);
          onDropFile(Array.from(event.dataTransfer.files));
        },
      }
    : {};

  const credits = creditCost !== undefined && mode === 'edit' ? `≈ ${creditCost} credit${creditCost === 1 ? '' : 's'}` : undefined;
  const queued = running && queueCount > 0 ? `${queueCount} waiting` : undefined;
  const hint = hintOverride ?? queued ?? credits;

  const combobox = slashOpen
    ? {
        role: 'combobox',
        'aria-expanded': true,
        'aria-controls': slashId,
        'aria-autocomplete': 'list' as const,
        'aria-activedescendant': slash.activeId ? commandOptionId(slashId, slash.activeId) : undefined,
      }
    : {};

  const attachButton = (props: object = { onClick: onAttach }) => (
    <IconButton label={attachLabel} icon={<Plus />} size="sm" className="rounded-cn-full" disabled={disabled} {...props} />
  );

  const stopOnly = running && !hasText && onStop;
  const sendLabel = running ? 'Add to queue' : 'Send';
  const sendTip = disabledReason ?? (canSend ? sendLabel : hero ? 'Type a prompt or add a video' : 'Type a prompt first');

  return (
    <div className={cx('relative flex flex-col gap-2', className)}>
      {slashOpen && (
        <SlashMenu
          id={slashId}
          groups={slash.groups}
          activeId={slash.activeId}
          onActiveChange={slash.setActiveId}
          onChoose={slash.select}
          query={value}
          className="absolute inset-x-0 bottom-full mb-2"
        />
      )}
      <div
        {...dropHandlers}
        className={cx(
          'relative flex flex-col gap-2 border bg-cn-surface-raised transition-[border-color] duration-cn-fast ease-cn-standard',
          'border-cn-border-strong hover:border-cn-control-border focus-within:border-cn-fg-muted focus-within:duration-cn-base',
          hero ? 'rounded-cn-3xl p-3 shadow-cn-2' : 'rounded-cn-xl p-2',
          running && 'cn-working-edge',
          disabled && 'opacity-60',
          focusWithinRing,
        )}
      >
        {contexts.length > 0 && (
          <ul aria-label="Applies to" className="flex flex-wrap gap-2">
            {contexts.map((context) => (
              <li key={context.id} className="motion-safe:animate-in motion-safe:fade-in motion-safe:duration-cn-fast">
                <ContextChip context={context} onRemove={disabled ? undefined : onRemoveContext} />
              </li>
            ))}
          </ul>
        )}
        <textarea
          ref={mergeRefs(textareaRef, ref)}
          value={value}
          onChange={(event) => {
            onValueChange(event.target.value);
            if (!event.target.value.startsWith('/')) setSlashDismissed(false);
          }}
          onKeyDown={onKeyDown}
          rows={hero ? 2 : 1}
          disabled={disabled}
          aria-label={label}
          aria-describedby={hint ? hintId : undefined}
          placeholder={placeholder ?? defaultPlaceholder(size, mode, contexts)}
          {...combobox}
          className={cx(
            'w-full resize-none bg-transparent px-1.5 py-1 text-cn-fg placeholder:text-cn-fg-muted focus-visible:outline-none',
            hero ? 'text-cn-body-lg' : 'text-cn-body-lg md:text-cn-body',
          )}
        />
        <div className="flex h-8 items-center gap-1.5">
          {attachMenu ? (
            <Popover label={attachLabel} side="bottom" align="start" trigger={(props) => attachButton(props)}>
              {attachMenu}
            </Popover>
          ) : (
            onAttach && attachButton()
          )}
          {shownModes.length > 1 && onModeChange && (
            <Menu
              side="top"
              trigger={(props) => (
                <button
                  type="button"
                  {...props}
                  disabled={disabled}
                  aria-label={`Mode: ${MODE_INFO[mode].label}. Change mode`}
                  className={cx(
                    'inline-flex h-7 items-center gap-1 rounded-cn-full border border-cn-border-strong px-2.5 text-cn-label font-medium text-cn-fg-secondary',
                    'transition-colors duration-cn-fast hover:bg-cn-surface-hover hover:text-cn-fg active:bg-cn-surface-active disabled:pointer-events-none',
                    focusRing,
                  )}
                >
                  {MODE_INFO[mode].label}
                  <ChevronDown aria-hidden className="size-3.5" />
                </button>
              )}
              items={shownModes.map((option) => ({
                id: option,
                label: `${MODE_INFO[option].label} · ${MODE_INFO[option].description}`,
                checked: option === mode,
                onSelect: () => onModeChange(option),
              }))}
            />
          )}
          <span className="flex-1" />
          {hint && (
            <span id={hintId} className="shrink-0 font-cn-mono text-cn-caption tabular-nums text-cn-fg-muted">
              {hint}
            </span>
          )}
          {running && onStop && hasText && <IconButton label="Stop" icon={<Square className="fill-current" />} size="sm" variant="secondary" className="rounded-cn-full" onClick={onStop} />}
          {stopOnly ? (
            <IconButton
              label="Stop"
              icon={<Square className="fill-current" />}
              size={hero ? 'md' : 'sm'}
              className="rounded-cn-full bg-cn-surface-active text-cn-fg hover:bg-cn-surface-hover"
              onClick={onStop}
            />
          ) : (
            <Tooltip content={sendTip} asLabel={false}>
              <button
                type="button"
                aria-label={sendLabel}
                aria-disabled={!canSend || undefined}
                onClick={send}
                className={cx(
                  'inline-flex shrink-0 items-center justify-center rounded-cn-full [&_svg]:size-4',
                  hero ? 'size-9' : 'size-8',
                  canSend ? 'cn-state bg-cn-accent text-cn-accent-fg' : 'cursor-not-allowed bg-cn-surface-active text-cn-fg-disabled',
                  focusRing,
                )}
              >
                {running ? <ListPlus aria-hidden /> : <ArrowUp aria-hidden />}
              </button>
            </Tooltip>
          )}
        </div>
        {dragging && (
          <div
            aria-hidden
            className={cx(
              'pointer-events-none absolute inset-0 flex items-center justify-center border-2 border-dashed border-cn-accent-border bg-cn-accent-subtle text-cn-body font-semibold text-cn-accent-text',
              hero ? 'rounded-cn-3xl' : 'rounded-cn-xl',
            )}
          >
            {dropLabel}
          </div>
        )}
      </div>
      {footer}
    </div>
  );
}
