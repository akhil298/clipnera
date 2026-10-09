'use client';

import type { ReactNode } from 'react';

import { FollowUpChips, ResultMessage } from '@/components/ui';
import type { FindingItem, RunOutput } from '@/lib/api/editor/types';
import type { Turn } from '@/lib/editor/run-store';
import { cx } from '@/lib/design/styles';

import { BrollResultCard, type BrollPlacement } from './BrollResultCard';
import { summariseResult } from './citations';
import { type CitationHandlers, CitedText } from './CitedText';
import { OutputsRow } from './OutputsRow';
import { ReplySources } from './ReplySources';

export interface ResultCardProps extends CitationHandlers {
  /** A turn with `result` (run.result). Renders nothing before that. */
  turn: Turn;
  /**
   * The editability line that ends the summary: "Each clip is separate, so you can trim or swap any
   * of them." Defaults to a line built from whether a version was saved.
   */
  editability?: string;
  /** "0:42 · just now". */
  timestamp?: string;
  /** Undo the whole run as one step (T2 / V1). Redo shows once `turn.undone` is true. */
  onUndo?: () => void;
  onRedo?: () => void;
  /** Before / after at the changed range (V1 compare). */
  onCompare?: () => void;
  /** Fills the composer; never sends. */
  onFollowUp: (prompt: string) => void;
  onUseMoment?: (moment: FindingItem) => void;
  /** B-roll this run placed, as result cards with Swap and Remove. */
  broll?: ReadonlyArray<BrollPlacement>;
  onSwapBroll?: (placement: BrollPlacement) => void;
  onRemoveBroll?: (placement: BrollPlacement) => void;
  renderOutput?: (output: RunOutput) => ReactNode;
  onOpenVersion?: (versionId: string) => void;
  className?: string;
}

function defaultEditability(turn: Turn, versionName: string | undefined): string | undefined {
  if (turn.stopping) return versionName ? `What was done is kept as “${versionName}”.` : 'Nothing was changed.';
  if (!versionName) return 'Nothing was changed.';
  return 'Every change is its own item on the timeline, so you can trim, move or swap any of it.';
}

/**
 * How an Edit run ends (07 §6.2 rule 5): moments it found, the counted summary with the editability
 * line, the version chip with Undo and Compare, up to 3 follow-ups, B-roll it placed, then Outputs.
 */
export function ResultCard({
  turn,
  editability,
  timestamp,
  onUndo,
  onRedo,
  onCompare,
  onFollowUp,
  onUseMoment,
  broll = [],
  onSwapBroll,
  onRemoveBroll,
  renderOutput,
  onOpenVersion,
  className,
  ...cite
}: ResultCardProps) {
  const result = turn.result;
  if (!result) return null;
  const { status, summary, changes } = summariseResult(result, turn.stopping);
  const version = result.version;
  const steps = turn.steps.filter((step) => step.status !== 'queued');
  const suggestions = result.suggestions.slice(0, 3);
  const promptFor = (label: string) => suggestions.find((s) => s.label === label)?.prompt ?? label;

  return (
    <div className={cx('flex flex-col gap-3', className)}>
      <ReplySources findings={turn.sources} citations={turn.citations} fps={cite.fps} onSeek={cite.onSeek} onUseMoment={onUseMoment} posterAt={cite.posterAt} />
      {turn.summaryText && <CitedText text={turn.summaryText} citations={turn.citations} {...cite} />}
      <ResultMessage
        status={status}
        summary={summary}
        changes={changes}
        notDone={result.summary.not_done.map((item) => ({ label: item.text, reason: item.reason }))}
        safeNote={editability ?? defaultEditability(turn, version?.name)}
        version={version ? { name: version.name, undone: turn.undone, onUndo, onRedo, onCompare } : undefined}
        details={steps.length ? { steps, operations: result.summary.done.length ? result.summary.done : ['No timeline changes'] } : undefined}
        timestamp={timestamp}
      />
      <FollowUpChips items={suggestions.map((s) => s.label)} onPick={(label) => onFollowUp(promptFor(label))} className="ml-7" />
      {!turn.undone && broll.length > 0 && (
        <ul aria-label="B-roll added" className="ml-7 flex flex-col gap-2">
          {broll.map((placement) => (
            <li key={placement.itemId}>
              <BrollResultCard placement={placement} onSeek={cite.onSeek} onSwap={onSwapBroll} onRemove={onRemoveBroll} />
            </li>
          ))}
        </ul>
      )}
      <OutputsRow outputs={result.outputs ?? []} renderOutput={renderOutput} onOpenVersion={onOpenVersion} className="ml-7" />
    </div>
  );
}
