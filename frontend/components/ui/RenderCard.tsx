'use client';

import { AlertCircle, CheckCircle2, Download } from 'lucide-react';
import type { ReactNode } from 'react';

import { cx } from '@/lib/design/styles';

import { Button } from './Button';
import { ProgressBar } from './ProgressBar';
import { WorkingText } from './WorkingText';

export type RenderStatus = 'queued' | 'rendering' | 'checking' | 'done' | 'failed' | 'cancelled' | 'expired';

export interface RenderCardProps {
  title: string;
  /** "0:42 · 1080×1920 · MP4 · ≈ 38 MB" — mono meta under the title. */
  meta?: string;
  poster?: string;
  aspect?: '9:16' | '16:9' | '1:1';
  status: RenderStatus;
  /** Current step from `job.step`: "Burning in captions". */
  step?: string;
  /** 0–100, only from `job.progress.percent`; never invented (07 §1 rule 4). */
  percent?: number;
  /** "about 0:40 left", only when measured. */
  eta?: string;
  /** Queue position when known: 2 → "2nd in line". */
  queuePosition?: number;
  /** Shown while rendering when the endpoint still blocks (until EB-24). */
  keepTabOpen?: boolean;
  /** Failed: what happened, in plain words. */
  error?: string;
  /** Done: facts like "Watermark on", "Channel intro first". */
  facts?: ReadonlyArray<string>;
  onDownload?: () => void;
  /** Amber Download only when it is the view's one action (editor, E-D2); otherwise secondary. */
  downloadPrimary?: boolean;
  /** Done: Copy link, Schedule (flag) and the like, as `size="sm"` buttons. */
  actions?: ReactNode;
  onCancel?: () => void;
  /** Failed (retryable), cancelled or expired. */
  onRetry?: () => void;
  className?: string;
}

const ordinal = (n: number) => `${n}${n % 10 === 1 && n % 100 !== 11 ? 'st' : n % 10 === 2 && n % 100 !== 12 ? 'nd' : n % 10 === 3 && n % 100 !== 13 ? 'rd' : 'th'}`;

/**
 * An export as a job (07 §6.6, editor §11.3): queued, rendering with a real
 * percentage, checking, then a verified "Ready". Shown in the conversation's
 * Outputs, the activity popover and the project page.
 */
export function RenderCard({
  title,
  meta,
  poster,
  aspect = '9:16',
  status,
  step,
  percent,
  eta,
  queuePosition,
  keepTabOpen = false,
  error,
  facts = [],
  onDownload,
  downloadPrimary = false,
  actions,
  onCancel,
  onRetry,
  className,
}: RenderCardProps) {
  const working = status === 'queued' || status === 'rendering' || status === 'checking';
  return (
    <article aria-label={`Export: ${title}`} aria-busy={working || undefined} className={cx('flex gap-3 rounded-cn-lg border border-cn-border bg-cn-surface p-3', className)}>
      <div
        className={cx(
          'cn-media-edge shrink-0 overflow-hidden rounded-cn-md bg-cn-stage',
          aspect === '9:16' ? 'aspect-cn-portrait w-12' : aspect === '1:1' ? 'aspect-square w-16' : 'aspect-video w-24',
        )}
      >
        {poster && <img src={poster} alt="" className={cx('size-full object-cover', status === 'expired' && 'opacity-50')} />}
        {status === 'rendering' && <span aria-hidden className="cn-pending-sheen absolute inset-0" />}
      </div>
      <div className="flex min-w-0 flex-1 flex-col gap-1.5">
        <h3 className="truncate text-cn-label font-semibold text-cn-fg">{title}</h3>
        {meta && <p className="truncate font-cn-mono text-cn-caption tabular-nums text-cn-fg-muted">{meta}</p>}
        <div role="status" className="flex flex-col gap-1.5 text-cn-caption">
          {status === 'queued' && (
            <span className="flex items-center gap-1.5 text-cn-fg-secondary">
              <WorkingText>Waiting to start</WorkingText>
              {queuePosition !== undefined && <span className="text-cn-fg-muted">· {ordinal(queuePosition)} in line</span>}
            </span>
          )}
          {status === 'rendering' && (
            <>
              <span className="flex items-center gap-1.5">
                <span aria-hidden className="size-1.5 rounded-cn-full bg-cn-accent motion-safe:animate-cn-pulse" />
                <WorkingText>{step ?? 'Rendering'}</WorkingText>
              </span>
              {percent !== undefined && (
                <ProgressBar
                  label={`${title}: ${step ?? 'Rendering'}`}
                  value={percent}
                  valueText={`${Math.round(percent)}%${eta ? ` · ${eta}` : ''}`}
                  size="sm"
                  hideLabel
                />
              )}
              {percent !== undefined && (
                <span className="font-cn-mono tabular-nums text-cn-fg-secondary">
                  {Math.round(percent)}%{eta && ` · ${eta}`}
                </span>
              )}
              {keepTabOpen && <span className="text-cn-fg-muted">Keep this tab open until it’s ready.</span>}
            </>
          )}
          {status === 'checking' && <WorkingText>Checking the file</WorkingText>}
          {status === 'done' && (
            <span className="flex flex-wrap items-center gap-1.5 text-cn-success-text">
              <CheckCircle2 aria-hidden className="size-3.5" /> Ready
              {facts.map((fact) => (
                <span key={fact} className="text-cn-fg-muted">
                  · {fact}
                </span>
              ))}
            </span>
          )}
          {status === 'failed' && (
            <span className="flex items-start gap-1.5 text-cn-danger-text">
              <AlertCircle aria-hidden className="mt-0.5 size-3.5 shrink-0" />
              <span>
                {error ?? 'The export didn’t finish.'} <span className="text-cn-fg-secondary">Your edit is safe and nothing was charged.</span>
              </span>
            </span>
          )}
          {status === 'cancelled' && <span className="text-cn-fg-secondary">Export cancelled.</span>}
          {status === 'expired' && <span className="text-cn-fg-muted">Removed after 30 days.</span>}
        </div>
        <div className="flex flex-wrap gap-2 pt-0.5 empty:hidden">
          {status === 'done' && onDownload && (
            <Button size="sm" variant={downloadPrimary ? 'primary' : 'secondary'} leadingIcon={<Download />} onClick={onDownload}>
              Download
            </Button>
          )}
          {status === 'done' && actions}
          {working && status !== 'checking' && onCancel && (
            <Button size="sm" variant="ghost" onClick={onCancel}>
              Cancel
            </Button>
          )}
          {(status === 'failed' || status === 'cancelled' || status === 'expired') && onRetry && (
            <Button size="sm" variant="secondary" onClick={onRetry}>
              {status === 'failed' ? 'Try again' : status === 'expired' ? 'Render again' : 'Export again'}
            </Button>
          )}
        </div>
      </div>
    </article>
  );
}
