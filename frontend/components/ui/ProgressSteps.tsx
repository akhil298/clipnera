import { Check, X } from 'lucide-react';
import type { ReactNode } from 'react';

import { cx } from '@/lib/design/styles';

export type ProgressStepStatus = 'upcoming' | 'active' | 'done' | 'failed';

export interface ProgressStep {
  id: string;
  label: ReactNode;
  description?: ReactNode;
  status: ProgressStepStatus;
}

export interface ProgressStepsProps {
  /** Accessible name of the list: "Upload progress". */
  label: string;
  steps: ReadonlyArray<ProgressStep>;
  orientation?: 'horizontal' | 'vertical';
  className?: string;
}

const SPOKEN: Record<ProgressStepStatus, string> = {
  upcoming: 'Not started',
  active: 'In progress',
  done: 'Done',
  failed: 'Failed',
};

function Marker({ status, index }: { status: ProgressStepStatus; index: number }) {
  return (
    <span
      aria-hidden
      className={cx(
        'relative z-cn-raised inline-flex size-6 shrink-0 items-center justify-center rounded-cn-full border text-cn-caption font-semibold [&_svg]:size-3.5',
        status === 'done' && 'border-cn-accent-border bg-cn-accent text-cn-accent-fg',
        status === 'active' && 'border-cn-accent-border bg-cn-accent-subtle text-cn-accent-text',
        status === 'failed' && 'border-cn-danger-text bg-cn-danger-subtle text-cn-danger-text',
        status === 'upcoming' && 'border-cn-control-border bg-cn-surface text-cn-fg-muted',
      )}
    >
      {status === 'done' ? <Check strokeWidth={3} /> : status === 'failed' ? <X strokeWidth={3} /> : index + 1}
    </span>
  );
}

/**
 * The stages of a known, fixed process (upload → analyse → clips ready; a
 * checkout). For an AI run's open-ended steps, use StepList.
 */
export function ProgressSteps({ label, steps, orientation = 'horizontal', className }: ProgressStepsProps) {
  const vertical = orientation === 'vertical';
  return (
    <ol aria-label={label} className={cx('flex', vertical ? 'flex-col gap-0' : 'items-start gap-2', className)}>
      {steps.map((step, index) => {
        const last = index === steps.length - 1;
        return (
          <li
            key={step.id}
            aria-current={step.status === 'active' ? 'step' : undefined}
            className={cx('relative flex min-w-0', vertical ? 'gap-3 pb-5 last:pb-0' : 'flex-1 flex-col gap-2')}
          >
            {!last && (
              <span
                aria-hidden
                className={cx(
                  'absolute',
                  vertical ? 'bottom-0 left-3 top-6 w-px' : 'left-8 right-0 top-3 h-px',
                  step.status === 'done' ? 'bg-cn-accent' : 'bg-cn-border-strong',
                )}
              />
            )}
            <Marker status={step.status} index={index} />
            <span className="flex min-w-0 flex-col gap-0.5">
              <span
                className={cx(
                  'text-cn-label font-semibold',
                  step.status === 'upcoming' ? 'text-cn-fg-muted' : step.status === 'failed' ? 'text-cn-danger-text' : 'text-cn-fg',
                )}
              >
                {step.label}
                <span className="sr-only">, {SPOKEN[step.status]}</span>
              </span>
              {step.description && <span className="text-cn-caption text-cn-fg-muted">{step.description}</span>}
            </span>
          </li>
        );
      })}
    </ol>
  );
}
