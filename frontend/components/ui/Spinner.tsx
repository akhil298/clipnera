import { cx } from '@/lib/design/styles';

const SIZE = { sm: 'size-4', md: 'size-5', lg: 'size-6' } as const;

export interface SpinnerProps {
  /** What is happening, read once by screen readers: "Connecting to YouTube". */
  label: string;
  size?: keyof typeof SIZE;
  /** Show the label beside the spinner (otherwise screen-reader only). */
  showLabel?: boolean;
  className?: string;
}

/**
 * For the rare wait with no step to name and no layout to mirror (an OAuth
 * hand-off, a popup opening). Prefer `WorkingText`, `ProgressBar` or a
 * skeleton. Under reduced motion the arc holds still.
 */
export function Spinner({ label, size = 'md', showLabel = false, className }: SpinnerProps) {
  return (
    <span role="status" className={cx('inline-flex items-center gap-2 text-cn-fg-secondary', className)}>
      <svg aria-hidden viewBox="0 0 24 24" fill="none" className={cx('shrink-0 motion-safe:animate-spin', SIZE[size])}>
        <circle cx="12" cy="12" r="9" stroke="currentColor" strokeOpacity="0.25" strokeWidth="2.5" />
        <path d="M21 12a9 9 0 0 0-9-9" stroke="rgb(var(--cn-accent))" strokeWidth="2.5" strokeLinecap="round" />
      </svg>
      <span className={showLabel ? 'text-cn-label' : 'sr-only'}>{label}</span>
    </span>
  );
}
