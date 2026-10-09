'use client';

import { FollowUpChips } from '@/components/ui';
import type { FindingItem } from '@/lib/api/editor/types';
import type { Turn } from '@/lib/editor/run-store';
import { cx } from '@/lib/design/styles';

import { type CitationHandlers, CitedText } from './CitedText';
import { ReplySources } from './ReplySources';

export interface AnswerCardProps extends CitationHandlers {
  /** An Ask turn: `answerText` while streaming, `result.answer` once done. */
  turn: Turn;
  /** The Ask allowance from the estimate (EB-4): "Free · 17 of 20 questions left today". Omitted when unknown. */
  allowance?: string;
  /** Fills the composer with the suggestion as an edit; never sends. */
  onFollowUp: (prompt: string) => void;
  onUseMoment?: (moment: FindingItem) => void;
  className?: string;
}

/** An Ask-mode answer (02-editor §3.3): cited moments above, the answer with timecode chips, then "Make it an edit". */
export function AnswerCard({ turn, allowance, onFollowUp, onUseMoment, className, ...cite }: AnswerCardProps) {
  const done = turn.result !== undefined;
  const text = turn.result?.answer ?? turn.answerText;
  if (!text) return null;
  const suggestions = (turn.result?.suggestions ?? []).slice(0, 3);
  const prompts = new Map(suggestions.map((s) => [`Make it an edit: ${s.label}`, s.prompt]));

  return (
    <div className={cx('flex flex-col gap-3', className)}>
      <ReplySources findings={turn.sources} citations={turn.citations} fps={cite.fps} onSeek={cite.onSeek} onUseMoment={onUseMoment} posterAt={cite.posterAt} />
      <CitedText text={text} citations={turn.citations} streaming={!done} {...cite} />
      {done && (
        <>
          <p className="text-cn-caption text-cn-fg-muted">{allowance ? `${allowance}. Nothing was changed.` : 'Nothing was changed.'}</p>
          <FollowUpChips items={[...prompts.keys()]} onPick={(label) => onFollowUp(prompts.get(label) ?? label)} />
        </>
      )}
    </div>
  );
}
