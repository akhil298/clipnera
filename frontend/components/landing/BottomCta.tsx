'use client';

import { ArrowRight, Zap } from 'lucide-react';

interface BottomCtaProps {
  onLaunchStudio: () => void;
}

export function BottomCta({ onLaunchStudio }: BottomCtaProps) {
  return (
    <section className="py-20 relative overflow-hidden">
      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 text-center relative z-10">
        <div className="p-8 sm:p-12 rounded-3xl bg-neutral-900/90 border border-neutral-800 shadow-xl space-y-6">
          <h2 className="text-3xl sm:text-4xl font-extrabold text-white font-['Syne',sans-serif]">
            Ready to turn your videos into shorts?
          </h2>
          <p className="text-xs sm:text-sm text-neutral-300 max-w-xl mx-auto">
            Turn your long videos into short-form clips without hiring an editor. Start on the free plan.
          </p>
          <div className="flex flex-col sm:flex-row items-center justify-center gap-3 pt-2">
            <button
              onClick={onLaunchStudio}
              className="w-full sm:w-auto px-6 py-3 rounded-xl bg-amber-500 hover:bg-amber-400 text-neutral-950 text-xs font-bold shadow-md shadow-amber-500/15 active:scale-95 transition-all flex items-center justify-center gap-2"
            >
              <Zap className="w-4 h-4 fill-current" aria-hidden="true" />
              <span>Launch Clipnera Studio Free</span>
            </button>
            <button
              onClick={onLaunchStudio}
              className="w-full sm:w-auto px-6 py-3 rounded-xl bg-neutral-800 hover:bg-neutral-700 text-amber-400 text-xs font-bold border border-neutral-700 transition-all active:scale-95 flex items-center justify-center gap-2"
            >
              <ArrowRight className="w-4 h-4" aria-hidden="true" />
              <span>Ingest YouTube Video</span>
            </button>
          </div>
        </div>
      </div>
    </section>
  );
}
