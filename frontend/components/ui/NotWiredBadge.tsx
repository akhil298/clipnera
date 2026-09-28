import React from 'react';

interface NotWiredBadgeProps {
  /** Short label shown on the badge. */
  label?: string;
  /** What is missing, shown on hover and read by screen readers. */
  reason: string;
  className?: string;
}

/**
 * Marks a control or panel that is on screen but not connected to the
 * backend yet (fixed sample data, a timer that fakes an AI call, state that is
 * never saved). Keeps the feature visible without letting it pass as real.
 */
export const NotWiredBadge: React.FC<NotWiredBadgeProps> = ({ label = 'Preview', reason, className = '' }) => (
  <span
    title={reason}
    className={`relative inline-flex items-center gap-1 h-5 px-1.5 rounded-md border border-dashed border-rose-400/60 bg-rose-500/10 text-rose-300 text-[10px] font-bold uppercase tracking-wide whitespace-nowrap ${className}`}
  >
    <span className="w-1.5 h-1.5 rounded-full bg-rose-400" aria-hidden="true" />
    {label}
    <span className="sr-only">: {reason}</span>
  </span>
);
