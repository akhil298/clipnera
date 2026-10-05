import { CircleAlert, CircleCheck, FileVideo, Pause, Play, RotateCcw, X } from 'lucide-react';
import type { ReactNode } from 'react';

import { cx } from '@/lib/design/styles';

import { IconButton } from './IconButton';
import { ProgressBar } from './ProgressBar';
import { WorkingText } from './WorkingText';

export type UploadStatus = 'queued' | 'uploading' | 'paused' | 'processing' | 'done' | 'failed';

export interface UploadProgressItemProps {
  name: string;
  /** "1.2 GB" or "1.2 GB · 4:12". */
  meta?: string;
  status: UploadStatus;
  /** 0–100 while uploading. Omit when unknown (indeterminate). */
  percent?: number;
  /** Right-hand detail while uploading: "3 min left", "12 MB/s". */
  eta?: string;
  /** Present-tense step while processing: "Finding moments". */
  step?: string;
  /** Failed: what happened and what is safe ("Connection dropped. Uploaded parts are kept."). */
  error?: string;
  /** Poster or file thumbnail. Decorative. */
  thumbnail?: ReactNode;
  onCancel?: () => void;
  onPause?: () => void;
  onResume?: () => void;
  onRetry?: () => void;
  /** Done/failed: take the row out of the tray. */
  onDismiss?: () => void;
  /** Done: the one next action, e.g. a "Open project" link. */
  action?: ReactNode;
  className?: string;
}

const STATUS_WORD: Record<UploadStatus, string> = {
  queued: 'Waiting',
  uploading: 'Uploading',
  paused: 'Paused',
  processing: 'Processing',
  done: 'Uploaded',
  failed: 'Upload failed',
};

/**
 * One file in an upload tray or list: name, size, progress and the actions
 * that apply in its state. Progress is named, never a bare spinner.
 */
export function UploadProgressItem({
  name,
  meta,
  status,
  percent,
  eta,
  step,
  error,
  thumbnail,
  onCancel,
  onPause,
  onResume,
  onRetry,
  onDismiss,
  action,
  className,
}: UploadProgressItemProps) {
  const icon =
    status === 'done' ? <CircleCheck className="text-cn-success-text" /> : status === 'failed' ? <CircleAlert className="text-cn-danger-text" /> : <FileVideo className="text-cn-fg-muted" />;
  const active = status === 'uploading' || status === 'processing' || status === 'paused';

  return (
    <div className={cx('flex items-start gap-3 py-2.5', className)}>
      <span aria-hidden className="inline-flex size-10 shrink-0 items-center justify-center overflow-hidden rounded-cn-sm bg-cn-surface-active [&_svg]:size-4">
        {thumbnail ?? icon}
      </span>
      <div className="min-w-0 flex-1 space-y-1.5">
        <div className="flex items-baseline justify-between gap-3">
          <p className="min-w-0 truncate text-cn-label font-semibold text-cn-fg" title={name}>
            {name}
          </p>
          {status === 'uploading' && percent !== undefined && (
            <span className="shrink-0 font-cn-mono text-cn-caption tabular-nums text-cn-fg-secondary">{Math.round(percent)}%</span>
          )}
        </div>
        {active && (
          <ProgressBar
            label={`${STATUS_WORD[status]} ${name}`}
            value={status === 'processing' ? undefined : percent}
            tone="accent"
            size="sm"
            hideLabel
          />
        )}
        <p className="flex min-w-0 flex-wrap gap-x-2 text-cn-caption text-cn-fg-muted">
          {status === 'processing' ? (
            <WorkingText>{step ?? 'Processing'}</WorkingText>
          ) : status === 'failed' ? (
            <span className="text-cn-danger-text">{error ?? STATUS_WORD.failed}</span>
          ) : (
            <span>{STATUS_WORD[status]}</span>
          )}
          {meta && <span className="font-cn-mono tabular-nums">{meta}</span>}
          {status === 'uploading' && eta && <span className="font-cn-mono tabular-nums">{eta}</span>}
        </p>
      </div>
      <div className="flex shrink-0 items-center gap-0.5">
        {status === 'done' && action}
        {status === 'uploading' && onPause && <IconButton label={`Pause ${name}`} icon={<Pause />} size="sm" onClick={onPause} />}
        {status === 'paused' && onResume && <IconButton label={`Resume ${name}`} icon={<Play />} size="sm" onClick={onResume} />}
        {status === 'failed' && onRetry && <IconButton label={`Try ${name} again`} icon={<RotateCcw />} size="sm" onClick={onRetry} />}
        {(status === 'queued' || active) && onCancel && <IconButton label={`Cancel ${name}`} icon={<X />} size="sm" onClick={onCancel} />}
        {(status === 'done' || status === 'failed') && onDismiss && <IconButton label={`Remove ${name} from the list`} icon={<X />} size="sm" onClick={onDismiss} />}
      </div>
    </div>
  );
}
