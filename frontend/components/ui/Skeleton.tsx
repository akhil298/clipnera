import type { CSSProperties, ReactNode } from 'react';

import { cx } from '@/lib/design/styles';

/**
 * One placeholder block. Silent to screen readers: wrap a set of blocks in
 * `SkeletonGroup`, which announces "Loading …" once.
 */
export function Skeleton({ className, style }: { className?: string; style?: CSSProperties }) {
  return (
    <span
      aria-hidden
      style={style}
      className={cx('block rounded-cn-md bg-cn-surface-hover motion-safe:animate-cn-pulse', className)}
    />
  );
}

/** Lines of text; the last one is shorter, like a real paragraph. */
export function SkeletonText({ lines = 3, className }: { lines?: number; className?: string }) {
  return (
    <span aria-hidden className={cx('flex flex-col gap-2', className)}>
      {Array.from({ length: lines }, (_, index) => (
        <Skeleton key={index} className={cx('h-3', index === lines - 1 && lines > 1 ? 'w-3/5' : 'w-full')} />
      ))}
    </span>
  );
}

export interface SkeletonGroupProps {
  /** What is loading, e.g. "Loading projects". Read once by screen readers. */
  label: string;
  children: ReactNode;
  className?: string;
}

/**
 * The single live region for a loading area. Mirror the real layout's shape so
 * nothing jumps when content arrives; never show a bare spinner instead.
 */
export function SkeletonGroup({ label, children, className }: SkeletonGroupProps) {
  return (
    <div role="status" aria-busy="true" className={className}>
      <span className="sr-only">{label}</span>
      {children}
    </div>
  );
}
