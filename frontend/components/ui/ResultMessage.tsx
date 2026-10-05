'use client';

import { CircleAlert, CircleCheck, CircleMinus, GitCompareArrows, Redo2, RotateCcw, Undo2 } from 'lucide-react';
import { type ReactNode, useId, useState } from 'react';

import { cx, focusRing } from '@/lib/design/styles';

import { Badge } from './Badge';
import { Button } from './Button';
import { FollowUpChips } from './FollowUpChips';
import { type RunStep, StepList } from './StepList';
import { Tab, TabList, TabPanel, Tabs } from './Tabs';

export type ResultStatus = 'done' | 'partial' | 'stopped' | 'failed';

export interface ResultVersion {
  /** Named from the prompt: "Trimmed silences, added captions". */
  name: string;
  /** One press undoes the whole AI edit (01 §7). */
  onUndo?: () => void;
  /** After undo: puts the edit back. */
  onRedo?: () => void;
  /** Before / after at the changed range. */
  onCompare?: () => void;
  undone?: boolean;
}

export interface ResultMessageProps {
  status: ResultStatus;
  /** Short and numeric: "Done — 3 clips, captions added." For failures: what happened. */
  summary: string;
  /** What it changed, one line each. */
  changes?: ReadonlyArray<string>;
  /** What it could not do, and why. Never hidden (01 §3.6). */
  notDone?: ReadonlyArray<{ label: string; reason?: string }>;
  /** For `failed` and `stopped`: what is still safe ("Your earlier versions are untouched."). */
  safeNote?: string;
  version?: ResultVersion;
  /** `failed` only: the one next action. */
  onRetry?: () => void;
  /** Up to three next-step prompts; a click fills the prompt bar, it does not send. */
  suggestions?: ReadonlyArray<string>;
  onSuggestion?: (prompt: string) => void;
  /** Details view: the run's steps and, in plain words, the timeline operations. */
  details?: { steps: ReadonlyArray<RunStep>; operations: ReadonlyArray<string> };
  /** "2 min ago". */
  timestamp?: string;
  className?: string;
}

const STATUS: Record<ResultStatus, { icon: ReactNode; tone: string; label: string }> = {
  done: { icon: <CircleCheck />, tone: 'text-cn-success-text', label: 'Done' },
  partial: { icon: <CircleMinus />, tone: 'text-cn-accent-text', label: 'Partly done' },
  stopped: { icon: <CircleMinus />, tone: 'text-cn-fg-secondary', label: 'Stopped' },
  failed: { icon: <CircleAlert />, tone: 'text-cn-danger-text', label: 'Not done' },
};

/**
 * How a run ends in the conversation. Undo sits on the result, not in a
 * menu (01 §3.4). Errors follow one pattern: what happened, what is still
 * safe, one action (01 §8).
 */
export function ResultMessage({
  status,
  summary,
  changes = [],
  notDone = [],
  safeNote,
  version,
  onRetry,
  suggestions = [],
  onSuggestion,
  details,
  timestamp,
  className,
}: ResultMessageProps) {
  const id = useId();
  const [showDetails, setShowDetails] = useState(false);
  const { icon, tone, label } = STATUS[status];

  return (
    <article aria-labelledby={`${id}-summary`} className={cx('flex flex-col gap-3', className)}>
      <div className="flex items-start gap-2.5">
        <span aria-hidden className={cx('mt-0.5 inline-flex [&_svg]:size-[18px]', tone)}>
          {icon}
        </span>
        <div className="min-w-0 flex-1 space-y-1">
          <p id={`${id}-summary`} className="text-cn-body font-semibold text-cn-fg">
            <span className="sr-only">{label}: </span>
            {summary}
          </p>
          {safeNote && <p className="text-cn-label text-cn-fg-secondary">{safeNote}</p>}
          {timestamp && <p className="text-cn-caption text-cn-fg-muted">{timestamp}</p>}
        </div>
      </div>

      {changes.length > 0 && (
        <ul className="ml-7 list-disc space-y-0.5 pl-4 text-cn-label text-cn-fg-secondary marker:text-cn-fg-disabled">
          {changes.map((change) => (
            <li key={change}>{change}</li>
          ))}
        </ul>
      )}

      {notDone.length > 0 && (
        <div className="ml-7 rounded-cn-md border border-cn-border bg-cn-surface px-3 py-2">
          <p className="text-cn-caption font-semibold text-cn-fg-secondary">Not done</p>
          <ul className="mt-1 space-y-1">
            {notDone.map((item) => (
              <li key={item.label} className="text-cn-label text-cn-fg">
                {item.label}
                {item.reason && <span className="text-cn-fg-muted"> — {item.reason}</span>}
              </li>
            ))}
          </ul>
        </div>
      )}

      {(version || onRetry || details) && (
        <div className="ml-7 flex flex-wrap items-center gap-2">
          {status === 'failed' && onRetry && (
            <Button size="sm" leadingIcon={<RotateCcw />} onClick={onRetry}>
              Try again
            </Button>
          )}
          {version && (
            <>
              <Badge tone={version.undone ? 'neutral' : 'accent'} className="max-w-[14rem]">
                {version.undone ? `Undone: ${version.name}` : version.name}
              </Badge>
              {version.undone
                ? version.onRedo && (
                    <Button size="sm" variant="secondary" leadingIcon={<Redo2 />} onClick={version.onRedo}>
                      Redo
                    </Button>
                  )
                : version.onUndo && (
                    <Button size="sm" variant="secondary" leadingIcon={<Undo2 />} onClick={version.onUndo}>
                      Undo
                    </Button>
                  )}
              {version.onCompare && !version.undone && (
                <Button size="sm" variant="ghost" leadingIcon={<GitCompareArrows />} onClick={version.onCompare}>
                  Compare
                </Button>
              )}
            </>
          )}
          {details && (
            <button
              type="button"
              aria-expanded={showDetails}
              aria-controls={showDetails ? `${id}-details` : undefined}
              onClick={() => setShowDetails(!showDetails)}
              className={cx('rounded-cn-xs text-cn-label font-semibold text-cn-fg-secondary hover:text-cn-fg', focusRing)}
            >
              {showDetails ? 'Hide details' : 'Details'}
            </button>
          )}
        </div>
      )}

      {details && showDetails && (
        <Tabs defaultValue="steps" variant="pill" className="ml-7">
          <TabList label="Run details">
            <Tab value="steps">Steps</Tab>
            <Tab value="changes">Changes</Tab>
          </TabList>
          <div id={`${id}-details`} className="mt-2">
            <TabPanel value="steps">
              <StepList steps={details.steps} defaultExpanded />
            </TabPanel>
            <TabPanel value="changes">
              <ul className="space-y-1 rounded-cn-lg border border-cn-border bg-cn-surface p-3 text-cn-label text-cn-fg-secondary">
                {details.operations.map((operation) => (
                  <li key={operation}>{operation}</li>
                ))}
              </ul>
            </TabPanel>
          </div>
        </Tabs>
      )}

      {onSuggestion && <FollowUpChips items={suggestions} onPick={onSuggestion} className="ml-7" />}
    </article>
  );
}
