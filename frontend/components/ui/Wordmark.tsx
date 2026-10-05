import { cx } from '@/lib/design/styles';

import { LogoMark } from './LogoMark';

/**
 * The one brand lock-up: the mark plus lowercase "clipnera" in Syne (DS-1).
 * `markOnly` for the collapsed sidebar rail. Decorative: put it inside a link
 * named "Clipnera home".
 */
export function Wordmark({ size = 'md', markOnly = false, className }: { size?: 'sm' | 'md'; markOnly?: boolean; className?: string }) {
  return (
    <span aria-hidden className={cx('inline-flex items-center gap-2', className)}>
      <LogoMark size={size === 'sm' ? 24 : 28} />
      {!markOnly && (
        <span className={cx('font-cn-display font-bold tracking-tight text-cn-fg', size === 'sm' ? 'text-cn-body-lg' : 'text-cn-title-sm')}>clipnera</span>
      )}
    </span>
  );
}
