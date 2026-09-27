'use client';

import { Sparkles, Headphones, Wand2, Zap } from 'lucide-react';

export function Navbar({ onOpenAuthModal, onLaunchStudio }: { onOpenAuthModal: () => void; onLaunchStudio: () => void }) {
  return (
    <header className="sticky top-0 z-50 border-b border-neutral-800/80 bg-neutral-950/90 backdrop-blur-md">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        <button
          type="button"
          aria-label="Clipnera, back to top"
          className="flex items-center gap-3 rounded-xl"
          onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}
        >
          <div className="w-9 h-9 rounded-xl bg-amber-500 flex items-center justify-center shadow-md shadow-amber-500/15">
            <Sparkles className="w-5 h-5 text-neutral-950" aria-hidden="true" />
          </div>
          <div className="flex items-center gap-1.5">
            <span className="font-extrabold text-lg tracking-tight text-white font-['Syne',sans-serif]">Clipnera</span>
            <span className="text-[10px] font-extrabold px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-300 border border-amber-500/20">AI</span>
          </div>
        </button>

        <nav aria-label="Main" className="hidden md:flex items-center gap-6 text-xs font-semibold text-neutral-300">
          <a href="#features" className="hover:text-white transition-colors">Features</a>
          <a href="#denoise" className="hover:text-white transition-colors flex items-center gap-1">
            <Headphones className="w-3.5 h-3.5 text-amber-400" aria-hidden="true" />
            <span>AI Denoise</span>
          </a>
          <a href="#story-generator" className="hover:text-white transition-colors flex items-center gap-1">
            <Wand2 className="w-3.5 h-3.5 text-purple-400" aria-hidden="true" />
            <span>Prompt Story</span>
          </a>
          <a href="#samples" className="hover:text-white transition-colors">Examples</a>
          <a href="#how-it-works" className="hover:text-white transition-colors">Workflow</a>
          <a href="#pricing" className="hover:text-white transition-colors">Pricing</a>
        </nav>

        <div className="flex items-center gap-2.5">
          <button
            onClick={onOpenAuthModal}
            className="hidden sm:inline-flex px-3.5 py-1.5 rounded-xl border border-neutral-800 hover:border-neutral-700 bg-neutral-900/60 text-xs font-semibold text-neutral-300 hover:text-white transition-all"
          >
            Sign In
          </button>
          <button
            onClick={onLaunchStudio}
            className="px-4 py-2 rounded-xl bg-amber-500 hover:bg-amber-400 text-neutral-950 text-xs font-bold shadow-md shadow-amber-500/15 active:scale-95 transition-all flex items-center gap-1.5"
          >
            <Zap className="w-3.5 h-3.5 fill-current" aria-hidden="true" />
            <span>Launch Studio</span>
          </button>
        </div>
      </div>
    </header>
  );
}
