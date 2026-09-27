'use client';

import { useState } from 'react';

interface RoiCalculatorProps {
  onLaunchStudio: () => void;
}

// Stated on the page: these are assumptions for an estimate, not measured results.
const CLIPS_PER_VIDEO = 5;
const EDITING_HOURS_PER_CLIP = 1;
const EDITOR_RATE_INR_PER_HOUR = 500;

const inr = new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 });

export function RoiCalculator({ onLaunchStudio }: RoiCalculatorProps) {
  const [videoCount, setVideoCount] = useState(4);
  const clips = videoCount * CLIPS_PER_VIDEO;
  const hours = clips * EDITING_HOURS_PER_CLIP;

  return (
    <section className="py-16 bg-neutral-900/40 border-y border-neutral-800/80">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 space-y-8">
        <div className="text-center space-y-2">
          <span className="text-xs font-extrabold uppercase tracking-wider text-amber-400 font-['Syne',sans-serif]">
            Time-Saving Estimate
          </span>
          <h2 className="text-2xl sm:text-3xl font-extrabold text-white font-['Syne',sans-serif]">
            How much time & money will you save?
          </h2>
        </div>

        <div className="p-6 sm:p-8 rounded-2xl bg-neutral-900/90 border border-neutral-800 shadow-xl space-y-6">
          <div className="space-y-2">
            <div className="flex items-center justify-between text-xs font-bold">
              <label htmlFor="roi-video-count" className="text-neutral-300">Long Videos Created per Month:</label>
              <span className="text-amber-400 font-mono text-base">{videoCount} Videos</span>
            </div>
            <input
              id="roi-video-count"
              type="range"
              min={1}
              max={20}
              value={videoCount}
              onChange={(e) => setVideoCount(Number(e.target.value))}
              className="w-full h-2 bg-neutral-800 rounded-lg appearance-none cursor-pointer accent-amber-400"
            />
            <div aria-hidden="true" className="flex justify-between text-[10px] text-neutral-400 font-mono">
              <span>1 video/mo</span>
              <span>10 videos/mo</span>
              <span>20 videos/mo</span>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-4 border-t border-neutral-800">
            <div className="p-4 rounded-xl bg-neutral-950 border border-neutral-800 text-center space-y-1">
              <span className="text-xs text-neutral-300">Shorts Created:</span>
              <p className="text-2xl font-extrabold text-amber-400 font-mono">{clips} Clips</p>
              <span className="text-[10px] text-neutral-400">Ready for TikTok & Reels</span>
            </div>
            <div className="p-4 rounded-xl bg-neutral-950 border border-neutral-800 text-center space-y-1">
              <span className="text-xs text-neutral-300">Editing Hours Saved:</span>
              <p className="text-2xl font-extrabold text-emerald-400 font-mono">~{hours} Hours</p>
              <span className="text-[10px] text-neutral-400">~{Math.round(hours / 8)} full working days</span>
            </div>
            <div className="p-4 rounded-xl bg-neutral-950 border border-neutral-800 text-center space-y-1">
              <span className="text-xs text-neutral-300">Editor Cost Saved:</span>
              <p className="text-2xl font-extrabold text-purple-400 font-mono">~{inr.format(hours * EDITOR_RATE_INR_PER_HOUR)}</p>
              <span className="text-[10px] text-neutral-400">vs a freelance editor</span>
            </div>
          </div>

          <p className="text-[11px] text-neutral-400 text-center">
            Estimate only, not a guarantee. Assumes {CLIPS_PER_VIDEO} clips per video, about {EDITING_HOURS_PER_CLIP} hour of
            manual editing per clip, and a freelance editor at {inr.format(EDITOR_RATE_INR_PER_HOUR)} per hour. Your results
            will vary, and you still review and adjust clips yourself.
          </p>

          <div className="text-center pt-2">
            <button
              onClick={onLaunchStudio}
              className="px-6 py-2.5 rounded-xl bg-amber-500 hover:bg-amber-400 text-neutral-950 text-xs font-bold shadow-md shadow-amber-500/15 active:scale-95 transition-all"
            >
              Start Saving Time Now
            </button>
          </div>
        </div>
      </div>
    </section>
  );
}
