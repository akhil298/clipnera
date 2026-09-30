"use client";
import React, { useEffect, useState } from 'react';
import { Clapperboard, X } from 'lucide-react';
import { creatorIntroApi } from '@/lib/api';
import { usePlan } from '@/hooks/usePlan';

const DISMISSED_KEY = 'clipnera.channelIntroNudge.dismissed';

function dismissed(): boolean {
  try {
    return window.localStorage.getItem(DISMISSED_KEY) === '1';
  } catch {
    return false;
  }
}

interface ChannelIntroNudgeProps {
  /** Takes the user to the intro in the brand kit. */
  onCreate: () => void;
}

/** One-time prompt, before a Pro user's project starts, to make their channel intro first. */
export const ChannelIntroNudge: React.FC<ChannelIntroNudgeProps> = ({ onCreate }) => {
  const { canUse } = usePlan();
  const allowed = canUse('creator_intro');
  const [show, setShow] = useState(false);

  useEffect(() => {
    if (!allowed || dismissed()) return;
    let cancelled = false;
    creatorIntroApi.get()
      .then((intro) => { if (!cancelled) setShow(!intro || intro.status === 'draft' || intro.status === 'failed'); })
      .catch(() => undefined);
    return () => { cancelled = true; };
  }, [allowed]);

  if (!show) return null;

  const dismiss = () => {
    setShow(false);
    try {
      window.localStorage.setItem(DISMISSED_KEY, '1');
    } catch {
      // Private windows can refuse storage; the nudge just shows again next time.
    }
  };

  return (
    <div className="flex items-start gap-3 rounded-xl border border-amber-400/25 bg-amber-400/10 p-3">
      <Clapperboard className="w-4 h-4 mt-0.5 text-amber-300 shrink-0" aria-hidden />
      <div className="flex-1 min-w-0">
        <p className="text-xs font-bold text-amber-100">Create your channel intro first</p>
        <p className="text-[11.5px] text-amber-200/80 mt-0.5">
          Your name, what your channel is about and a Subscribe or Follow tap, played before every clip you export. Made once.
        </p>
        <button type="button" onClick={onCreate}
          className="mt-2 rounded-lg bg-amber-400 px-2.5 py-1 text-xs font-bold text-neutral-950 hover:bg-amber-300">
          Create intro
        </button>
      </div>
      <button type="button" onClick={dismiss} aria-label="Not now" className="p-1 rounded-lg text-amber-200/70 hover:text-white hover:bg-amber-400/10">
        <X className="w-4 h-4" />
      </button>
    </div>
  );
};
