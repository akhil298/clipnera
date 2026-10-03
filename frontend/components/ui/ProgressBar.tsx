import { cx } from '@/lib/design/styles';

export interface ProgressBarProps {
  /** Accessible and visible name: "Uploading interview.mp4". */
  label: string;
  /** 0–`max`. Omit for work whose length is unknown (indeterminate). */
  value?: number;
  max?: number;
  /** Visible value text, e.g. "42%" or "3 of 8 clips". Defaults to a percentage. */
  valueText?: string;
  tone?: 'accent' | 'success' | 'danger';
  /** Hide the label row (when the label is shown elsewhere; it stays the accessible name). */
  hideLabel?: boolean;
  size?: 'sm' | 'md';
  className?: string;
}

const FILL = { accent: 'bg-cn-accent', success: 'bg-cn-success', danger: 'bg-cn-danger' } as const;

/**
 * Progress for one job. Indeterminate bars sweep instead of spinning and are
 * replaced by a determinate value as soon as one is known.
 */
export function ProgressBar({
  label,
  value,
  max = 100,
  valueText,
  tone = 'accent',
  hideLabel = false,
  size = 'md',
  className,
}: ProgressBarProps) {
  const determinate = value !== undefined;
  const percent = determinate ? Math.round((Math.min(Math.max(value, 0), max) / max) * 100) : 0;
  const text = valueText ?? (determinate ? `${percent}%` : undefined);

  return (
    <div className={cx('flex flex-col gap-1.5', className)}>
      {!hideLabel && (
        <div className="flex items-baseline justify-between gap-3 text-cn-label">
          <span className="truncate text-cn-fg">{label}</span>
          {text && <span className="shrink-0 font-cn-mono text-cn-caption tabular-nums text-cn-fg-secondary">{text}</span>}
        </div>
      )}
      <div
        role="progressbar"
        aria-label={label}
        aria-valuemin={determinate ? 0 : undefined}
        aria-valuemax={determinate ? max : undefined}
        aria-valuenow={determinate ? value : undefined}
        aria-valuetext={determinate ? text : 'Working'}
        className={cx('relative w-full overflow-hidden rounded-cn-full bg-cn-surface-active', size === 'sm' ? 'h-1' : 'h-1.5')}
      >
        {determinate ? (
          <span
            className={cx('block h-full rounded-cn-full transition-[width] duration-cn-base ease-cn-out', FILL[tone])}
            style={{ width: `${percent}%` }}
          />
        ) : (
          <span
            className={cx(
              'absolute inset-y-0 left-0 w-2/5 rounded-cn-full motion-safe:animate-cn-sweep motion-reduce:w-full motion-reduce:opacity-40',
              FILL[tone],
            )}
          />
        )}
      </div>
    </div>
  );
}
