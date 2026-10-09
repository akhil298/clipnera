'use client';

import { useRouter } from 'next/navigation';
import { type KeyboardEvent, type RefObject, useMemo, useRef } from 'react';

import { PromptBar, PromptQueue, type PromptContext, SLASH_COMMANDS } from '@/components/ui';
import { cx } from '@/lib/design/styles';

import { AttachMenu } from './AttachMenu';
import { ComposerNotice } from './ComposerNotice';
import { type EditorComposerStores, useEditorComposer } from './useEditorComposer';

export interface EditorComposerProps extends EditorComposerStores {
  /** Files picked with + or dropped on the box. Leave out until the editor has an upload path. */
  onAddFiles?: (files: File[]) => void;
  /** The editor's prompt ref, so ⌘K and / can focus the text field. */
  promptRef?: RefObject<HTMLTextAreaElement | null>;
  className?: string;
}

/**
 * The docked composer for the editor's conversation zone (07 §6.1, 02-editor §3.1): Up next,
 * then the PromptBar with selection chips, Edit/Ask/Plan, slash templates, the estimate, Send or
 * Add to queue, Stop, and the line under the box. Self-contained: give it the editor's stores.
 */
export function EditorComposer({ onAddFiles, promptRef, className, ...stores }: EditorComposerProps) {
  const router = useRouter();
  const localRef = useRef<HTMLTextAreaElement>(null);
  const textareaRef = promptRef ?? localRef;
  const state = useEditorComposer(stores);
  const { block, chips } = state;

  // A step holding an item locks its chip; ContextChip can't show one locked chip yet (request DS-E),
  // so while any chip is locked the row is read-only and the locked ones say why.
  const anyLocked = chips.some((chip) => chip.locked);
  const contexts: PromptContext[] = useMemo(
    () => chips.map(({ locked, ...chip }) => (locked ? { ...chip, meta: 'In use' } : chip)),
    [chips],
  );

  const onKeyDownCapture = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key !== 'Tab' || !event.shiftKey || event.target !== textareaRef.current || block?.disabled) return;
    event.preventDefault();
    state.cycleMode();
  };

  const insertText = (text: string) => {
    state.setValue((current) => (current.trim() ? `${current.trimEnd()} ${text}` : text));
    textareaRef.current?.focus();
  };

  return (
    <div className={cx('flex flex-col gap-2', className)} onKeyDownCapture={onKeyDownCapture}>
      <PromptQueue items={state.queue} onChange={state.changeQueue} />
      <PromptBar
        ref={textareaRef}
        size="docked"
        label="Prompt"
        value={state.value}
        onValueChange={state.setValue}
        onSubmit={state.send}
        mode={state.mode}
        onModeChange={state.setMode}
        running={state.running}
        onStop={state.stop}
        contexts={contexts}
        onRemoveContext={anyLocked ? undefined : state.removeContext}
        attachMenu={(close) => <AttachMenu close={close} onAddFiles={onAddFiles} onInsertText={insertText} />}
        onDropFile={onAddFiles}
        hint={state.hint}
        queueCount={state.queue.length}
        slashCommands={SLASH_COMMANDS}
        onSlashCommand={(command) => {
          if (command.href) {
            state.setValue('');
            router.push(command.href);
          }
        }}
        placeholder={state.placeholder}
        disabled={block?.disabled}
        disabledReason={block?.reason}
        footer={<ComposerNotice state={state} />}
      />
    </div>
  );
}
