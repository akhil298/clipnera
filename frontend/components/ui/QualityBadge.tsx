import { cx } from '@/lib/design/styles';

export interface QualityBadgeProps {
  /** True while proxies play; fades out as the full-quality file cross-fades in. */
  visible: boolean;
  /** Default "Preview quality". */
  children?: string;
  className?: string;
}

/**
 * Top-left on the preview stage while proxies play (02 §4.9). Lives on the
 * stage, so it is always drawn in the dark theme (07 §1 rule 3). Chrome only:
 * never in screenshots or exports, not interactive.
 */
export function QualityBadge({ visible, children = 'Preview quality', className }: QualityBadgeProps) {
  return (
    <span
      data-theme="dark"
      aria-hidden={!visible}
      className={cx(
        'pointer-events-none inline-flex h-5 items-center rounded-cn-full border border-cn-border-strong bg-cn-stage/80 px-2 text-cn-caption font-semibold text-cn-fg-secondary',
        'transition-opacity duration-cn-base ease-cn-standard',
        visible ? 'opacity-100' : 'opacity-0',
        className,
      )}
    >
      {children}
    </span>
  );
}
