'use client';

import { Sparkles } from 'lucide-react';

interface FooterProps {
  onLaunchApp: () => void;
  onOpenAuthModal: () => void;
}

export function Footer({ onLaunchApp, onOpenAuthModal }: FooterProps) {
  return (
    <footer className="border-t border-neutral-800 bg-neutral-950 py-10 text-xs text-neutral-500">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between gap-4">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded-lg bg-amber-500/20 text-amber-400 flex items-center justify-center font-bold text-xs">
            C
          </div>
          <span className="font-bold text-white font-['Syne',sans-serif]">
            Clipnera AI Studio
          </span>
          <span>• Next-Gen Shorts Repurposing</span>
        </div>

        <div className="flex items-center gap-6 text-neutral-400">
          <button onClick={onLaunchApp} className="hover:text-white transition-colors">
            App Dashboard
          </button>
          <button onClick={onLaunchApp} className="hover:text-white transition-colors">
            Project Folders
          </button>
          <button onClick={onLaunchApp} className="hover:text-white transition-colors">
            Settings & Billing
          </button>
          <button onClick={onOpenAuthModal} className="hover:text-white transition-colors">
            Sign In
          </button>
        </div>

        <div>
          © {new Date().getFullYear()} Clipnera AI. All rights reserved.
        </div>
      </div>
    </footer>
  );
}
