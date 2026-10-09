'use client';

import { ArrowUp } from 'lucide-react';

import { WorkingText } from '@/components/ui';
import { cx, focusRing } from '@/lib/design/styles';
import { selectActiveTurn, useRun, type RunStore } from '@/lib/editor/run-store';
import { selectSelected, useSelection, type SelectionStore } from '@/lib/editor/selection';

import { liveStep } from './composer-logic';

export interface ComposerDockLineProps {
  runs: RunStore;
  selection: SelectionStore;
  /** Opens the conversation as a bottom sheet (02-editor §2.1 phone layout). */
  onOpen: () => void;
  className?: string;
}

/**
 * The phone's docked prompt line (56 px, < 768): the live step while a run works, otherwise
 * "Describe an edit to …". Tapping it opens the conversation sheet with the composer.
 */
export function ComposerDockLine({ runs, selection, onOpen, className }: ComposerDockLineProps) {
  const active = useRun(runs, selectActiveTurn);
  const hasSelection = useSelection(selection, selectSelected).length > 0;
  const idle = `Describe an edit to ${hasSelection ? 'the selection' : 'the whole video'}`;

  return (
    <button
      type="button"
      onClick={onOpen}
      aria-haspopup="dialog"
      aria-label={active ? `${liveStep(active)}. Open the conversation` : `${idle}. Open the composer`}
      className={cx(
        'flex h-14 w-full items-center gap-3 border-t border-cn-border bg-cn-surface px-4 text-left',
        'transition-colors duration-cn-fast hover:bg-cn-surface-hover active:bg-cn-surface-active',
        focusRing,
        className,
      )}
    >
      <span
        className={cx(
          'flex h-11 min-w-0 flex-1 items-center rounded-cn-xl border border-cn-border-strong bg-cn-surface-raised px-3 text-cn-body-lg',
          active && 'cn-working-edge',
        )}
      >
        {active ? <WorkingText className="truncate text-cn-fg">{liveStep(active)}</WorkingText> : <span className="truncate text-cn-fg-muted">{idle}</span>}
      </span>
      <span aria-hidden className="inline-flex size-11 shrink-0 items-center justify-center rounded-cn-full bg-cn-surface-active text-cn-fg-secondary [&_svg]:size-4">
        <ArrowUp />
      </span>
    </button>
  );
}
