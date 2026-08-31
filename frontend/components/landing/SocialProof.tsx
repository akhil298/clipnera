'use client';

import { Youtube, Radio, Flame, Layers, Zap } from 'lucide-react';

export function SocialProof() {
  return (
    <section className="py-8 border-y border-neutral-800/80 bg-neutral-950/50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <p className="text-center text-xs font-semibold uppercase tracking-wider text-neutral-500 mb-6">
          Trusted by 120,000+ Podcasters, YouTubers & High-Growth Media Teams
        </p>
        <div className="flex flex-wrap items-center justify-center gap-8 sm:gap-14 text-neutral-400 font-extrabold text-sm sm:text-base opacity-75">
          <span className="flex items-center gap-1.5 hover:text-white transition-colors">
            <Youtube className="w-5 h-5 text-red-500" /> Creators Studio
          </span>
          <span className="flex items-center gap-1.5 hover:text-white transition-colors">
            <Radio className="w-5 h-5 text-amber-400" /> Podcast Hub
          </span>
          <span className="flex items-center gap-1.5 hover:text-white transition-colors">
            <Flame className="w-5 h-5 text-rose-500" /> Viral Media Lab
          </span>
          <span className="flex items-center gap-1.5 hover:text-white transition-colors">
            <Layers className="w-5 h-5 text-sky-400" /> Nexus Agency
          </span>
          <span className="flex items-center gap-1.5 hover:text-white transition-colors">
            <Zap className="w-5 h-5 text-purple-400" /> ShortForm Pro
          </span>
        </div>
      </div>
    </section>
  );
}
