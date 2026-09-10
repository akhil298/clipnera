'use client';

import { LANDING_SAMPLE_PROJECTS } from '@/lib/data/mockProjects';
import { ArrowRight, Clock } from 'lucide-react';

interface SamplesSectionProps {
  onLaunchApp: () => void;
  onOpenSample: (projectId: string) => void;
}

export function SamplesSection({ onLaunchApp, onOpenSample }: SamplesSectionProps) {
  return (
    <section id="samples" className="py-16 bg-neutral-950/70 border-t border-neutral-800/80">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-10">
        <div className="flex flex-col sm:flex-row items-start sm:items-end justify-between gap-4">
          <div>
            <span className="text-xs font-extrabold uppercase tracking-wider text-amber-400 font-['Syne',sans-serif]">
              Try Live Interactive Projects
            </span>
            <h2 className="text-2xl sm:text-3xl font-extrabold text-white font-['Syne',sans-serif] mt-1">
              Explore pre-processed viral templates
            </h2>
            <p className="text-xs text-neutral-400 mt-1">
              Click any project folder to jump straight into the live interactive Editor Studio:
            </p>
          </div>
          <button
            onClick={onLaunchApp}
            className="px-4 py-2 rounded-xl bg-neutral-800 hover:bg-neutral-700 text-amber-400 text-xs font-bold border border-neutral-700 flex items-center gap-1.5 transition-all active:scale-95"
          >
            <span>View All Project Folders</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>

        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-5">
          {LANDING_SAMPLE_PROJECTS.map((sample) => (
            <div
              key={sample.id}
              onClick={() => onOpenSample(sample.id)}
              className="p-4 rounded-2xl bg-neutral-900/90 border border-neutral-800 hover:border-amber-500/50 cursor-pointer transition-all hover:-translate-y-1 space-y-3 group"
            >
              <div className="relative aspect-video rounded-xl overflow-hidden bg-black">
                <img
                  src={sample.posterUrl}
                  alt={sample.title}
                  className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                />
                <div className="absolute top-2.5 left-2.5 px-2 py-0.5 rounded-md bg-black/70 backdrop-blur text-[10px] font-bold text-amber-300 border border-white/10">
                  {sample.folderCategory || sample.genre}
                </div>
                <div className="absolute bottom-2.5 right-2.5 px-2 py-0.5 rounded-md bg-emerald-500 text-black text-[10px] font-extrabold">
                  {sample.clips.length} Viral Clips
                </div>
              </div>

              <div>
                <h4 className="text-sm font-bold text-white group-hover:text-amber-300 transition-colors line-clamp-1">
                  {sample.title}
                </h4>
                <p className="text-xs text-neutral-400 line-clamp-2 mt-1">
                  {sample.description}
                </p>
              </div>

              <div className="pt-2 border-t border-neutral-800/80 flex items-center justify-between text-xs text-neutral-400">
                <span className="flex items-center gap-1 font-mono text-[11px]">
                  <Clock className="w-3 h-3 text-neutral-500" />
                  <span>{Math.floor(sample.duration / 60)} mins raw</span>
                </span>
                <span className="text-amber-400 font-bold text-[11px] flex items-center gap-1">
                  <span>Open in Studio</span>
                  <ArrowRight className="w-3 h-3" />
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
