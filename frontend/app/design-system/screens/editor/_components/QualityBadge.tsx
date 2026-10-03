import { cx } from '@/lib/design/styles';

/**
 * Design-system addition (02 §4.9). Top-left on the preview while proxies
 * play; fades out over 200 ms as the full-quality file cross-fades in. It is
 * chrome: never in screenshots or exports. Not interactive.
 */
export function QualityBadge({ visible, className }: { visible: boolean; className?: string }) {
  return (
    <span
      aria-hidden={!visible}
      className={cx(
        'pointer-events-none inline-flex h-5 items-center rounded-cn-full border border-cn-border-strong bg-cn-bg/80 px-2 text-cn-caption font-semibold text-cn-fg-secondary',
        'transition-opacity duration-cn-base ease-cn-out',
        visible ? 'opacity-100' : 'opacity-0',
        className,
      )}
    >
      Preview quality
    </span>
  );
}
