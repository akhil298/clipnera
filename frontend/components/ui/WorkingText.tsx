import type { ReactNode } from 'react';

import { cx } from '@/lib/design/styles';

/**
 * Text that is in progress: a slow light sweep across the words ("Trimming
 * 14 silences"). Replaces spinners everywhere. Under reduced motion it is
 * plain secondary text (handled in tokens.css).
 */
export function WorkingText({ children, className }: { children: ReactNode; className?: string }) {
  return <span className={cx('cn-shimmer-text', className)}>{children}</span>;
}
