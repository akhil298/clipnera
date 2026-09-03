'use client';

import { useState } from 'react';

interface RoiCalculatorProps {
  onLaunchStudio: () => void;
}

export function RoiCalculator({ onLaunchStudio }: RoiCalculatorProps) {
  const [videoCount, setVideoCount] = useState(4);

  return (
    <section className="py-16 bg-neutral-900/40 border-y border-neutral-800/80">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 space-y-8">
        <div className="text-center space-y-2">
          <span className="text-xs font-extrabold uppercase tracking-wider text-amber-400 font-['Syne',sans-serif]">
            Creator ROI Calculator
          </span>
          <h2 className="text-2xl sm:text-3xl font-extrabold text-white font-['Syne',sans-serif]">
            How much time & money will you save?
          </h2>
        </div>

        <div className="p-6 sm:p-8 rounded-2xl bg-neutral-900/90 border border-neutral-800 shadow-xl space-y-6">
          <div className="space-y-2">
            <div className="flex items-center justify-between text-xs font-bold">
              <span className="text-neutral-300">Long Videos Created per Month:</span>
              <span className="text-amber-400 font-mono text-base">{videoCount} Videos</span>
            </div>
            <input
              type="range"
              min={1}
              max={20}
              value={videoCount}
              onChange={(e) => setVideoCount(Number(e.target.value))}
              className="w-full h-2 bg-neutral-800 rounded-lg appearance-none cursor-pointer accent-amber-400"
            />
            <div className="flex justify-between text-[10px] text-neutral-500 font-mono">
              <span>1 video/mo</span>
              <span>10 videos/mo</span>
              <span>20 videos/mo</span>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-4 border-t border-neutral-800">
            <div className="p-4 rounded-xl bg-neutral-950 border border-neutral-800 text-center space-y-1">
              <span className="text-xs text-neutral-400">Viral Shorts Generated:</span>
              <p className="text-2xl font-extrabold text-amber-400 font-mono">{videoCount * 8} Clips</p>
              <span className="text-[10px] text-neutral-500">Ready for TikTok & Reels</span>
            </div>
            <div className="p-4 rounded-xl bg-neutral-950 border border-neutral-800 text-center space-y-1">
              <span className="text-xs text-neutral-400">Editing Hours Saved:</span>
              <p className="text-2xl font-extrabold text-emerald-400 font-mono">{videoCount * 6} Hours</p>
              <span className="text-[10px] text-neutral-500">~{Math.round((videoCount * 6) / 8)} full working days</span>
            </div>
            <div className="p-4 rounded-xl bg-neutral-950 border border-neutral-800 text-center space-y-1">
              <span className="text-xs text-neutral-400">Agency Cost Saved:</span>
              <p className="text-2xl font-extrabold text-purple-400 font-mono">${videoCount * 350}</p>
              <span className="text-[10px] text-neutral-500">vs Freelancer Editors</span>
            </div>
          </div>

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
