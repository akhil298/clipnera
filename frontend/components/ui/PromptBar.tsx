'use client';

import { ArrowUp, ListPlus, Paperclip, Square } from 'lucide-react';
import { type KeyboardEvent, type RefObject, useId, useRef } from 'react';

import { mergeRefs } from '@/lib/design/refs';
import { cx, focusWithinRing } from '@/lib/design/styles';
import { useAutosize } from '@/lib/design/useAutosize';

import { ContextChip, type PromptContext } from './ContextChip';
import { IconButton } from './IconButton';
import { SegmentedControl } from './SegmentedControl';

export type PromptMode = 'edit' | 'ask' | 'plan';

const MODES = [
  { value: 'edit', label: 'Edit' },
  { value: 'ask', label: 'Ask' },
  { value: 'plan', label: 'Plan' },
] as const satisfies ReadonlyArray<{ value: PromptMode; label: string }>;

export interface PromptBarProps {
  value: string;
  onValueChange: (value: string) => void;
  /** Enter, or the send button. Not called for empty text. */
  onSubmit: () => void;
  /** While a run is active: Edit makes changes, Ask answers, Plan writes a plan to approve. */
  mode: PromptMode;
  onModeChange: (mode: PromptMode) => void;
  /** A run is active: shows Stop beside Send, and Send adds to the queue. Typing stays allowed. */
  running?: boolean;
  /** Stops the run at the next safe point. Never clears the typed text. */
  onStop?: () => void;
  /** Selected things the prompt applies to. Empty means the whole project. */
  contexts?: ReadonlyArray<PromptContext>;
  onRemoveContext?: (id: string) => void;
  /** Opens the attach picker (video, image, audio, link). Hidden when omitted. */
  onAttach?: () => void;
  /** Credits the action will use, when known. Shown before sending (01 §3.10). */
  creditCost?: number;
  /** Prompts waiting behind the current run. */
  queueCount?: number;
  /** `hero` on Home; `docked` in the editor conversation panel. */
  size?: 'hero' | 'docked';
  placeholder?: string;
  disabled?: boolean;
  /** Accessible name of the text area. */
  label?: string;
  ref?: RefObject<HTMLTextAreaElement | null>;
  className?: string;
}

function defaultPlaceholder(mode: PromptMode, contexts: ReadonlyArray<PromptContext>): string {
  const target = contexts.length === 0 ? 'the whole project' : contexts.length === 1 ? 'the selection' : `${contexts.length} selected items`;
  if (mode === 'ask') return `Ask about ${target}`;
  if (mode === 'plan') return `Describe what you want for ${target}. You approve the plan before anything changes.`;
  return `Describe an edit to ${target}`;
}

/**
 * The one place to tell Clipnera what to do. Presentational: the parent owns
 * the text, mode, contexts and run state. Enter sends, Shift+Enter adds a
 * line, and IME composition never sends early.
 */
export function PromptBar({
  value,
  onValueChange,
  onSubmit,
  mode,
  onModeChange,
  running = false,
  onStop,
  contexts = [],
  onRemoveContext,
  onAttach,
  creditCost,
  queueCount = 0,
  size = 'docked',
  placeholder,
  disabled = false,
  label = 'Prompt',
  ref,
  className,
}: PromptBarProps) {
  const id = useId();
  const hintId = `${id}-hint`;
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const hero = size === 'hero';
  useAutosize(textareaRef, value, hero ? 2 : 1, 6);

  const canSend = !disabled && value.trim().length > 0;
  const send = () => {
    if (canSend) onSubmit();
  };

  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      send();
    }
  };

  const credits = creditCost !== undefined && mode === 'edit' ? `${creditCost} credit${creditCost === 1 ? '' : 's'}` : undefined;
  const queued = running && queueCount > 0 ? `${queueCount} waiting` : undefined;
  const hint = credits ?? queued;

  return (
    <div
      className={cx(
        'flex flex-col gap-2 border border-cn-control-border bg-cn-field transition-colors duration-cn-fast hover:border-cn-fg-muted',
        hero ? 'rounded-cn-2xl p-3 shadow-cn-2' : 'rounded-cn-xl p-2',
        disabled && 'pointer-events-none opacity-60',
        focusWithinRing,
        className,
      )}
    >
      {contexts.length > 0 && (
        <ul aria-label="Applies to" className="flex flex-wrap gap-1.5">
          {contexts.map((context) => (
            <li key={context.id}>
              <ContextChip context={context} onRemove={onRemoveContext} />
            </li>
          ))}
        </ul>
      )}
      <textarea
        ref={mergeRefs(textareaRef, ref)}
        value={value}
        onChange={(event) => onValueChange(event.target.value)}
        onKeyDown={onKeyDown}
        rows={hero ? 2 : 1}
        disabled={disabled}
        aria-label={label}
        aria-describedby={hint ? hintId : undefined}
        placeholder={placeholder ?? defaultPlaceholder(mode, contexts)}
        className={cx(
          'w-full resize-none bg-transparent px-1.5 text-cn-fg placeholder:text-cn-fg-muted focus-visible:outline-none',
          hero ? 'py-1 text-cn-body-lg' : 'py-1 text-cn-body',
        )}
      />
      <div className="flex items-center gap-1.5">
        {onAttach && <IconButton label="Attach video, image, audio or link" icon={<Paperclip />} size="sm" onClick={onAttach} />}
        <SegmentedControl label="Prompt mode" size="sm" options={MODES} value={mode} onValueChange={onModeChange} />
        <span className="flex-1" />
        {hint && (
          <span id={hintId} className="shrink-0 text-cn-caption text-cn-fg-muted">
            {/* The cost never truncates: the short form fits a phone. */}
            {credits && <span className="hidden sm:inline">Uses about </span>}
            {hint}
          </span>
        )}
        {running && onStop && <IconButton label="Stop" icon={<Square className="fill-current" />} size="sm" variant="secondary" onClick={onStop} />}
        <IconButton
          label={running ? 'Add to queue' : 'Send'}
          icon={running ? <ListPlus /> : <ArrowUp />}
          size="sm"
          variant="primary"
          disabled={!canSend}
          onClick={send}
        />
      </div>
    </div>
  );
}
