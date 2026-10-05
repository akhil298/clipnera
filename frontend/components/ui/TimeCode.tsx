import { type TimecodeOptions, formatTimecode, isoDuration, spokenDuration } from '@/lib/design/timecode';
import { cx } from '@/lib/design/styles';

export interface TimeCodeProps extends TimecodeOptions {
  /** Position or length in seconds. */
  seconds: number;
  /** Shows "current / total" (player read-out). Also pads `seconds` to the total's width. */
  total?: number;
  /** `muted` for meta rows; `inherit` keeps the parent colour. */
  tone?: 'default' | 'muted' | 'inherit';
  className?: string;
}

/**
 * A time in JetBrains Mono with tabular figures, so digits never jitter.
 * Screen readers hear "1 minute 5 seconds", not "one colon zero five".
 */
export function TimeCode({ seconds, total, hours, fps, tone = 'default', className }: TimeCodeProps) {
  const options = { hours, fps, total };
  const spoken = total === undefined ? spokenDuration(seconds) : `${spokenDuration(seconds)} of ${spokenDuration(total)}`;
  return (
    <span
      className={cx(
        'font-cn-mono tabular-nums',
        tone === 'default' && 'text-cn-fg',
        tone === 'muted' && 'text-cn-fg-muted',
        className,
      )}
    >
      <time dateTime={isoDuration(seconds)} aria-hidden>
        {formatTimecode(seconds, options)}
      </time>
      {total !== undefined && (
        <>
          <span aria-hidden className="text-cn-fg-muted"> / </span>
          <time dateTime={isoDuration(total)} aria-hidden className="text-cn-fg-muted">
            {formatTimecode(total, options)}
          </time>
        </>
      )}
      <span className="sr-only">{spoken}</span>
    </span>
  );
}
