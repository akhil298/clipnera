'use client';

import { Check } from 'lucide-react';
import { type KeyboardEvent, type ReactNode, useId } from 'react';

import { cx, focusRing } from '@/lib/design/styles';

export interface Choice {
  id: string;
  label: string;
  description?: string;
  /** A small preview: a poster, a caption style sample, a waveform. Decorative. */
  preview?: ReactNode;
}

export interface ChoiceCardProps {
  /** One plain question: "Which clip should get the new hook?" */
  question: string;
  /** Up to four options (01 §5 step 4). */
  choices: ReadonlyArray<Choice>;
  onChoose: (id: string) => void;
  /** "Skip, use your best guess". Omit to make the question required. */
  onSkip?: () => void;
  skipLabel?: string;
  /** Set once answered: the card locks and shows the pick. `'skip'` when skipped. */
  chosenId?: string | 'skip';
  className?: string;
}

const MAX_CHOICES = 4;

/**
 * The assistant asking with options instead of a paragraph. Picking one
 * continues the run; the card then stays in the conversation, locked, as a
 * record. Number keys 1–4 pick while the card has focus.
 */
export function ChoiceCard({
  question,
  choices,
  onChoose,
  onSkip,
  skipLabel = 'Skip, use your best guess',
  chosenId,
  className,
}: ChoiceCardProps) {
  const id = useId();
  const answered = chosenId !== undefined;
  const shown = choices.slice(0, MAX_CHOICES);

  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (answered || event.metaKey || event.ctrlKey || event.altKey) return;
    if (event.target instanceof HTMLInputElement || event.target instanceof HTMLTextAreaElement) return;
    const choice = shown[Number(event.key) - 1];
    if (choice) {
      event.preventDefault();
      onChoose(choice.id);
    }
  };

  return (
    <div
      role="group"
      aria-labelledby={`${id}-question`}
      onKeyDown={onKeyDown}
      className={cx('flex flex-col gap-3 rounded-cn-lg border border-cn-border bg-cn-surface p-3.5', className)}
    >
      <p id={`${id}-question`} className="text-cn-body font-semibold text-cn-fg">
        {question}
      </p>
      <div className="grid gap-2 sm:grid-cols-2">
        {shown.map((choice, index) => {
          const picked = chosenId === choice.id;
          return (
            <button
              key={choice.id}
              type="button"
              disabled={answered}
              aria-pressed={answered ? picked : undefined}
              onClick={() => onChoose(choice.id)}
              className={cx(
                'flex items-start gap-2.5 rounded-cn-md border p-2.5 text-left transition-colors duration-cn-fast',
                picked
                  ? 'border-cn-accent-border bg-cn-accent-subtle'
                  : answered
                    ? 'border-cn-border opacity-50'
                    : 'border-cn-border-strong hover:border-cn-control-border hover:bg-cn-surface-hover',
                focusRing,
              )}
            >
              {choice.preview ? (
                <span aria-hidden className="shrink-0 overflow-hidden rounded-cn-sm">
                  {choice.preview}
                </span>
              ) : (
                <span
                  aria-hidden
                  className="inline-flex size-5 shrink-0 items-center justify-center rounded-cn-xs border border-cn-border-strong font-cn-mono text-cn-caption text-cn-fg-muted"
                >
                  {picked ? <Check className="size-3 text-cn-accent-text" strokeWidth={3} /> : index + 1}
                </span>
              )}
              <span className="flex min-w-0 flex-col gap-0.5">
                <span className="text-cn-label font-semibold text-cn-fg">{choice.label}</span>
                {choice.description && <span className="text-cn-caption text-cn-fg-secondary">{choice.description}</span>}
              </span>
            </button>
          );
        })}
      </div>
      {onSkip && !answered && (
        <button
          type="button"
          onClick={onSkip}
          className={cx('self-start rounded-cn-xs text-cn-label font-semibold text-cn-fg-secondary hover:text-cn-fg', focusRing)}
        >
          {skipLabel}
        </button>
      )}
      {chosenId === 'skip' && <p className="text-cn-caption text-cn-fg-muted">Skipped. I used my best guess.</p>}
    </div>
  );
}
