"use client";
import React, { useEffect, useRef, useState } from 'react';
import { ChevronRight, Zap } from 'lucide-react';
import { useEntitlements, videoMinutesFor } from '@/hooks/useEntitlements';
import { formatDate } from '@/lib/utils/dates';

interface CreditsPopoverProps {
  remaining: number;
  total: number;
  onManagePlan: () => void;
}

/** Header credit badge. Opens a panel explaining what the balance buys. */
export const CreditsPopover: React.FC<CreditsPopoverProps> = ({ remaining, total, onManagePlan }) => {
  const { entitlements } = useEntitlements();
  const [isOpen, setIsOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!isOpen) return;
    const onPointerDown = (event: MouseEvent) => {
      if (!containerRef.current?.contains(event.target as Node)) setIsOpen(false);
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setIsOpen(false);
    };
    document.addEventListener('mousedown', onPointerDown);
    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.removeEventListener('mousedown', onPointerDown);
      document.removeEventListener('keydown', onKeyDown);
    };
  }, [isOpen]);

  const percent = total > 0 ? Math.min(100, Math.max(0, (remaining / total) * 100)) : 0;
  const extraShare = Math.round(entitlements.extra_aspect_ratio_credit_share * 100);

  return (
    <div ref={containerRef} className="relative">
      <button
        onClick={() => setIsOpen((open) => !open)}
        className="flex items-center gap-1.5 h-9 px-2.5 rounded-xl bg-neutral-900 border border-neutral-800 text-xs text-neutral-300 tabular-nums hover:border-amber-500/40 hover:text-white transition-all"
        title={`${remaining} of ${total} AI credits remaining`}
        aria-expanded={isOpen}
        aria-haspopup="dialog"
      >
        <Zap className="w-3.5 h-3.5 text-amber-400 fill-amber-400" />
        <span className="font-semibold">
          {remaining}
          {total > 0 && <span className="text-neutral-500">/{total}</span>}
          <span className="hidden sm:inline text-neutral-400"> credits</span>
        </span>
      </button>

      {isOpen && (
        <div
          role="dialog"
          aria-label="AI credits"
          className="absolute right-0 top-full mt-2 w-72 max-w-[calc(100vw-2rem)] p-4 rounded-xl bg-neutral-950 border border-neutral-800 shadow-xl shadow-black/40 space-y-3 z-30"
        >
          <div className="flex items-center justify-between text-xs">
            <span className="flex items-center gap-1.5 font-bold text-neutral-200">
              <Zap className="w-4 h-4 text-amber-400 fill-amber-400" />
              <span>AI Credits</span>
            </span>
            <span className="font-bold text-amber-300 tabular-nums">
              {remaining} / {total}
            </span>
          </div>
          <div className="h-2 w-full bg-neutral-800 rounded-full overflow-hidden">
            <div className="h-full bg-amber-500 rounded-full" style={{ width: `${percent}%` }} />
          </div>
          <p className="text-xs text-neutral-300">
            ≈ <span className="font-bold text-white">{videoMinutesFor(entitlements, remaining)} min</span> of video left
          </p>
          {entitlements.purchased_credits_remaining > 0 && (
            <p className="text-[11px] text-emerald-400">
              Includes {entitlements.purchased_credits_remaining} bought credits that never expire
            </p>
          )}

          <div className="pt-3 border-t border-neutral-800 space-y-1.5 text-[11px] text-neutral-400">
            <p className="font-semibold text-neutral-300">How credits work</p>
            <p>• {entitlements.credits_per_video_minute} credits per minute of video processed</p>
            <p>• +{extraShare}% for each extra output format</p>
            <p>
              •{' '}
              {entitlements.next_credit_reset_at
                ? `Plan credits reset to ${entitlements.credit_minutes} on ${formatDate(entitlements.next_credit_reset_at)}`
                : `Plan credits reset to ${entitlements.credit_minutes} every 30 days`}
              ; unused ones don&apos;t roll over
            </p>
          </div>

          <button
            onClick={() => {
              setIsOpen(false);
              onManagePlan();
            }}
            className="w-full flex items-center justify-center gap-1 py-2 rounded-lg bg-neutral-900 border border-neutral-800 text-xs font-bold text-amber-400 hover:border-amber-500/40 transition-colors"
          >
            <span>Buy credits or upgrade</span>
            <ChevronRight className="w-3.5 h-3.5" />
          </button>
        </div>
      )}
    </div>
  );
};
