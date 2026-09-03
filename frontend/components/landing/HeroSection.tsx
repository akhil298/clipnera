'use client';

import { Sparkles, Youtube, CheckCircle2 } from 'lucide-react';

interface HeroSectionProps {
  heroUrl: string;
  setHeroUrl: (url: string) => void;
  onLaunchStudio: () => void;
}

export function HeroSection({
  heroUrl,
  setHeroUrl,
  onLaunchStudio,
}: HeroSectionProps) {
  return (
    <section className="relative pt-12 pb-20 overflow-hidden">
      <div className="absolute top-1/4 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[700px] h-[350px] bg-amber-500/10 blur-[120px] pointer-events-none rounded-full" />
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10">
        <div className="text-center max-w-3xl mx-auto space-y-5">
          <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-amber-500/10 border border-amber-500/20 text-amber-300 text-xs font-semibold">
            <Sparkles className="w-3.5 h-3.5 text-amber-400" />
            <span>Gemini 3.7 Flash Video Intelligence • Studio Denoise & Prompt-to-Shorts</span>
          </div>

          <h1 className="text-3xl sm:text-5xl lg:text-6xl font-extrabold text-white tracking-tight font-['Syne',sans-serif] leading-[1.12]">
            Turn 1 Long Video or Prompt into{' '}
            <span className="text-amber-400">10 Viral Shorts</span> in 60s
          </h1>

          <p className="text-sm sm:text-base text-neutral-300 leading-relaxed font-normal max-w-2xl mx-auto">
            Extract high-retention 9:16 clips automatically. Auto-reframes faces, eliminates background room noise, adds kinetic karaoke subtitles, and inserts smart B-roll cutaways.
          </p>

          <div className="pt-3 max-w-2xl mx-auto">
            <div className="p-2 rounded-2xl bg-neutral-900/90 border border-neutral-800 shadow-xl space-y-3">
              <div className="p-1">
                <div className="flex items-center gap-2 py-1.5 px-3 rounded-lg bg-neutral-800 text-amber-400 shadow text-xs font-bold">
                  <Youtube className="w-3.5 h-3.5 text-red-400" />
                  <span>YouTube Link</span>
                </div>
              </div>

              <div className="flex flex-col sm:flex-row gap-2">
                <input
                  type="url"
                  value={heroUrl}
                  onChange={(e) => setHeroUrl(e.target.value)}
                  placeholder="Paste any YouTube video link..."
                  className="flex-1 px-4 py-2.5 rounded-xl bg-neutral-950 border border-neutral-700/80 text-xs text-white placeholder-neutral-500 focus:outline-none focus:border-amber-400 transition-colors shadow-inner"
                />
                <button
                  onClick={onLaunchStudio}
                  className="px-5 py-2.5 rounded-xl bg-amber-500 hover:bg-amber-400 text-neutral-950 text-xs font-bold shadow-md shadow-amber-500/15 active:scale-95 transition-all flex items-center justify-center gap-2 whitespace-nowrap"
                >
                  <Sparkles className="w-4 h-4" />
                  <span>Extract Viral Clips</span>
                </button>
              </div>

              <div className="flex flex-wrap items-center justify-center gap-3 pt-1 text-[11px] text-neutral-400">
                <span className="flex items-center gap-1">
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                  <span>No Watermarks</span>
                </span>
                <span className="flex items-center gap-1">
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                  <span>60 Free AI Minutes</span>
                </span>
                <span className="flex items-center gap-1">
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                  <span>Studio Noise Cancellation</span>
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
