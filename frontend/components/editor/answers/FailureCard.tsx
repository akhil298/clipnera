'use client';

import { Coins, RotateCcw, Upload } from 'lucide-react';

import { Button, FollowUpChips, ResultMessage } from '@/components/ui';
import { editorMessage } from '@/lib/api/messages/editor';
import type { Turn } from '@/lib/editor/run-store';
import { cx, focusRing } from '@/lib/design/styles';

export interface FailureCardProps {
  /** A turn with `failure` (run.failed). */
  turn: Turn;
  timestamp?: string;
  /** "Try again": POST /runs/{id}/retry with the same prompt and chips (EB-3). */
  onRetry: () => void;
  /** Undo / redo the steps kept as a version before the failure. */
  onUndo?: () => void;
  onRedo?: () => void;
  /** The different prompt suggested after a second failure; fills the composer, never sends. */
  onFollowUp: (prompt: string) => void;
  /** MEDIA_UNREADABLE: opens the file picker to replace the source. */
  onReplaceFile?: () => void;
  onAddCredits?: () => void;
  supportHref?: string;
  className?: string;
}

/**
 * A failed run: what happened, what is still safe, one action (01 §8). The action comes from the
 * error code (lib/api/messages/editor.ts); the server's message names the cause and the file.
 */
export function FailureCard({
  turn,
  timestamp,
  onRetry,
  onUndo,
  onRedo,
  onFollowUp,
  onReplaceFile,
  onAddCredits,
  supportHref = 'mailto:support@clipnera.com',
  className,
}: FailureCardProps) {
  const failure = turn.failure;
  if (!failure) return null;
  const { error, version, suggestion } = failure;
  const { text, action } = editorMessage(error.code, error.message);
  const cause = error.message || text;
  const safeNote = version ? `“${version.name}” is kept as a version. Your earlier versions are untouched.` : 'Nothing was changed.';
  const steps = turn.steps.filter((step) => step.status !== 'queued');

  return (
    <div className={cx('flex flex-col gap-2', className)}>
      <ResultMessage
        status="failed"
        summary={cause}
        safeNote={action === 'replace_file' ? `${safeNote} ${text}` : safeNote}
        onRetry={action === 'retry' && error.retryable ? onRetry : undefined}
        version={version ? { name: version.name, undone: turn.undone, onUndo, onRedo } : undefined}
        details={steps.length ? { steps, operations: version ? [version.name] : ['No timeline changes'] } : undefined}
        timestamp={timestamp}
      />
      {action === 'replace_file' && onReplaceFile && (
        <Button size="sm" leadingIcon={<Upload />} onClick={onReplaceFile} className="ml-7 self-start">
          Replace file
        </Button>
      )}
      {action === 'add_credits' && onAddCredits && (
        <Button size="sm" leadingIcon={<Coins />} onClick={onAddCredits} className="ml-7 self-start">
          Add credits
        </Button>
      )}
      {action === 'contact_support' && (
        <div className="ml-7 flex flex-col gap-2">
          {suggestion && (
            <>
              <p className="text-cn-label text-cn-fg-secondary">Try saying it a different way:</p>
              <FollowUpChips items={[suggestion.label]} onPick={() => onFollowUp(suggestion.prompt)} />
            </>
          )}
          <a href={supportHref} className={cx('self-start rounded-cn-xs text-cn-label font-semibold text-cn-accent-text hover:underline', focusRing)}>
            Contact support
          </a>
        </div>
      )}
    </div>
  );
}

/** POST /runs never arrived (`send_failed`). The prompt stays in the turn; Retry sends it again. */
export function SendFailedNote({ turn, onRetry, onDiscard, className }: { turn: Turn; onRetry: () => void; onDiscard?: () => void; className?: string }) {
  if (turn.status !== 'send_failed') return null;
  return (
    <div role="alert" className={cx('flex flex-wrap items-center gap-2 text-cn-label text-cn-danger-text', className)}>
      <span>{turn.sendError?.code === 'NETWORK' || !turn.sendError ? 'Not sent. Check your connection.' : editorMessage(turn.sendError.code, turn.sendError.message).text}</span>
      <Button size="sm" variant="secondary" leadingIcon={<RotateCcw />} onClick={onRetry}>
        Retry
      </Button>
      {onDiscard && (
        <Button size="sm" variant="ghost" onClick={onDiscard}>
          Discard
        </Button>
      )}
    </div>
  );
}

/** `run.cancelled`: stopped before anything changed, or a queued prompt that never ran. */
export function StoppedNote({ turn, className }: { turn: Turn; className?: string }) {
  const cancelled = turn.cancelled;
  if (!cancelled) return null;
  // An approval run cancelled with nothing changed is the person saying "Not now".
  const declined = turn.plan?.needsApproval;
  const text =
    cancelled.while === 'queued'
      ? 'Removed from the queue. Nothing was changed.'
      : cancelled.changed
        ? 'Stopped. What was done is kept as a version.'
        : declined
          ? 'Not started. Nothing was changed.'
          : 'Stopped. Nothing was changed.';
  return <p className={cx('text-cn-label text-cn-fg-secondary', className)}>{text}</p>;
}
