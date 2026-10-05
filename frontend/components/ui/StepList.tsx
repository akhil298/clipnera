'use client';

import { AnimatePresence, motion } from 'framer-motion';
import { Check, ChevronDown, CircleAlert, CircleDashed, Minus, RotateCcw } from 'lucide-react';
import { type ReactNode, useId } from 'react';

import { useReducedMotion } from '@/lib/design/useReducedMotion';
import { collapseTransition, motionPreset } from '@/lib/design/motion';
import { cx, focusRing } from '@/lib/design/styles';
import { useControllableState } from '@/lib/design/useControllableState';

import { Button } from './Button';
import { WorkingText } from './WorkingText';

export type StepStatus = 'queued' | 'active' | 'done' | 'failed' | 'skipped';

export interface RunStep {
  id: string;
  /** Verb plus object, present tense: "Trimming 14 silences". */
  label: string;
  status: StepStatus;
  /** When done: what it changed ("Removed 42 seconds"). When failed: why, in plain words. */
  detail?: string;
  /** For long steps: "3 of 14" or "42%". A visible change at least every 5 s (01 §5). */
  progress?: string;
}

export interface StepListProps {
  steps: ReadonlyArray<RunStep>;
  /** Running time, "0:18". */
  elapsed?: string;
  expanded?: boolean;
  defaultExpanded?: boolean;
  onExpandedChange?: (expanded: boolean) => void;
  /** Shows "Try again" on a failed step. */
  onRetryStep?: (id: string) => void;
  className?: string;
}

const ICON: Record<StepStatus, ReactNode> = {
  done: <Check className="text-cn-fg-muted" />,
  active: (
    <span className="relative inline-flex size-4 items-center justify-center">
      <span className="size-2 rounded-cn-full bg-cn-accent motion-safe:animate-cn-pulse" />
    </span>
  ),
  queued: <CircleDashed className="text-cn-fg-disabled" />,
  failed: <CircleAlert className="text-cn-danger-text" />,
  skipped: <Minus className="text-cn-fg-disabled" />,
};

const SPOKEN: Record<StepStatus, string> = {
  done: 'done',
  active: 'in progress',
  queued: 'waiting',
  failed: 'failed',
  skipped: 'skipped',
};

function summarise(steps: ReadonlyArray<RunStep>, elapsed?: string): { text: string; working: boolean; icon: StepStatus } {
  const total = steps.length;
  const time = elapsed ? ` · ${elapsed}` : '';
  const activeIndex = steps.findIndex((step) => step.status === 'active');
  if (activeIndex >= 0) {
    const active = steps[activeIndex];
    const progress = active.progress ? ` · ${active.progress}` : '';
    return { text: `${active.label} · step ${activeIndex + 1} of ${total}${progress}${time}`, working: true, icon: 'active' };
  }
  const failedIndex = steps.findIndex((step) => step.status === 'failed');
  if (failedIndex >= 0) return { text: `Stopped at step ${failedIndex + 1} of ${total}: ${steps[failedIndex].label}`, working: false, icon: 'failed' };
  if (steps.every((step) => step.status === 'queued')) return { text: 'Waiting to start', working: false, icon: 'queued' };
  const done = steps.filter((step) => step.status === 'done').length;
  return { text: `${done} step${done === 1 ? '' : 's'} done${time}`, working: false, icon: 'done' };
}

/**
 * The live steps of one AI run. Collapsed, it is one calm line; expanded, the
 * list with each step's state and what it changed (01 §5, "Collapsed and
 * expanded"). Screen readers hear each new step once.
 */
export function StepList({
  steps,
  elapsed,
  expanded,
  defaultExpanded = false,
  onExpandedChange,
  onRetryStep,
  className,
}: StepListProps) {
  const id = useId();
  const reduced = useReducedMotion();
  const [open, setOpen] = useControllableState(expanded, defaultExpanded, onExpandedChange);
  const summary = summarise(steps, elapsed);
  const activeIndex = steps.findIndex((step) => step.status === 'active');
  const announcement =
    activeIndex >= 0 ? `Step ${activeIndex + 1} of ${steps.length}: ${steps[activeIndex].label}` : summary.text;
  const rise = motionPreset('rise', reduced);

  return (
    <div className={cx('rounded-cn-lg border border-cn-border bg-cn-surface', className)}>
      <span className="sr-only" role="status" aria-live="polite">
        {announcement}
      </span>
      <button
        type="button"
        aria-expanded={open}
        aria-controls={`${id}-steps`}
        onClick={() => setOpen(!open)}
        className={cx('flex min-h-10 w-full items-center gap-2 rounded-cn-lg px-3 text-left text-cn-label', focusRing)}
      >
        <span aria-hidden className="inline-flex [&_svg]:size-4">
          {ICON[summary.icon]}
        </span>
        <span className="min-w-0 flex-1 truncate">
          {summary.working ? <WorkingText>{summary.text}</WorkingText> : <span className="text-cn-fg-secondary">{summary.text}</span>}
        </span>
        <ChevronDown
          aria-hidden
          className={cx('size-4 shrink-0 text-cn-fg-muted motion-safe:transition-transform motion-safe:duration-cn-base', open && 'rotate-180')}
        />
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            id={`${id}-steps`}
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={collapseTransition(reduced)}
            className="overflow-hidden"
          >
            <ol className="flex flex-col gap-2.5 border-t border-cn-border px-3 py-3">
              {steps.map((step) => (
                <li key={step.id} className="flex items-start gap-2.5">
                  <span aria-hidden className="mt-0.5 inline-flex [&_svg]:size-4">
                    {ICON[step.status]}
                  </span>
                  <motion.div key={step.status} {...(step.status === 'active' ? rise : {})} className="min-w-0 flex-1 space-y-0.5">
                    <p
                      className={cx(
                        'text-cn-label transition-colors duration-cn-fast',
                        step.status === 'active' && 'font-semibold',
                        step.status === 'done' && 'text-cn-fg-secondary',
                        step.status === 'failed' && 'font-semibold text-cn-danger-text',
                        (step.status === 'queued' || step.status === 'skipped') && 'text-cn-fg-muted',
                      )}
                    >
                      {step.status === 'active' ? <WorkingText>{step.label}</WorkingText> : step.label}
                      {step.progress && step.status === 'active' && (
                        <span className="ml-2 font-cn-mono text-cn-caption tabular-nums text-cn-fg-muted">{step.progress}</span>
                      )}
                      <span className="sr-only">, {SPOKEN[step.status]}</span>
                    </p>
                    {step.detail && <p className="text-cn-caption text-cn-fg-muted">{step.detail}</p>}
                    {step.status === 'failed' && onRetryStep && (
                      <Button size="sm" variant="secondary" leadingIcon={<RotateCcw />} onClick={() => onRetryStep(step.id)} className="mt-1.5">
                        Try again
                      </Button>
                    )}
                  </motion.div>
                </li>
              ))}
            </ol>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
