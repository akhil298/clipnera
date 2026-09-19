'use client';

import React from 'react';
import { Lock } from 'lucide-react';

interface ProLockBadgeProps {
  /** Shown in the tooltip, e.g. "the 4:5 format" or "this caption style". */
  feature?: string;
  className?: string;
  size?: 'sm' | 'md';
}

/**
 * Marks a control the current plan cannot use. Paired with a click handler that
 * opens the upgrade flow, so a locked control explains itself instead of
 * silently doing nothing or failing at the API.
 */
export function ProLockBadge({ feature, className = '', size = 'sm' }: ProLockBadgeProps) {
  const dimension = size === 'sm' ? 'h-3 w-3' : 'h-4 w-4';
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full bg-amber-400/15 px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide text-amber-300 ring-1 ring-amber-400/30 ${className}`}
      title={feature ? `${feature} requires a paid plan` : 'Requires a paid plan'}
    >
      <Lock className={dimension} aria-hidden />
      Pro
    </span>
  );
}

interface UpgradeHintProps {
  message: string;
  onUpgrade: () => void;
  className?: string;
}

/** Inline "this is locked — upgrade" row shown beneath a gated group. */
export function UpgradeHint({ message, onUpgrade, className = '' }: UpgradeHintProps) {
  return (
    <div
      className={`flex items-center justify-between gap-3 rounded-xl border border-amber-400/25 bg-amber-400/10 px-3 py-2 ${className}`}
    >
      <span className="text-xs text-amber-200/90">{message}</span>
      <button
        type="button"
        onClick={onUpgrade}
        className="shrink-0 rounded-lg bg-amber-400 px-2.5 py-1 text-xs font-bold text-neutral-950 transition-colors hover:bg-amber-300"
      >
        Upgrade
      </button>
    </div>
  );
}
