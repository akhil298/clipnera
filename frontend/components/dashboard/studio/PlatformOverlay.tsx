"use client";
import React from 'react';
import { Eye, Smartphone } from 'lucide-react';
import type { Platform } from './studioUtils';

/** Mock app chrome over the preview, so creators see what each platform covers. */
export function PlatformOverlay({ platform, title, hashtags }: { platform: Platform; title: string; hashtags: string[] }) {
  if (platform === 'tiktok') {
    return (
      <div className="absolute inset-0 z-40 pointer-events-none p-3 flex flex-col justify-between text-white">
        <div className="flex items-center justify-between text-xs font-semibold opacity-80 pt-1">
          <span>Following</span>
          <span className="font-bold border-b-2 border-white pb-0.5">For You</span>
          <Eye className="w-4 h-4" />
        </div>
        <div className="flex justify-between items-end pb-2">
          <div className="space-y-1 max-w-[180px]">
            <p className="text-xs font-bold">@clipnera</p>
            <p className="text-[10px] opacity-90 line-clamp-2">
              {title} {hashtags.slice(0, 3).join(' ')}
            </p>
          </div>
          <div className="flex flex-col items-center gap-2.5 text-center text-[10px]">
            <div className="w-8 h-8 rounded-full bg-rose-500/80 flex items-center justify-center">❤️</div>
            <span>42.8K</span>
            <div className="w-8 h-8 rounded-full bg-neutral-800/80 flex items-center justify-center">💬</div>
            <span>1.2K</span>
            <div className="w-8 h-8 rounded-full bg-neutral-800/80 flex items-center justify-center">↗️</div>
            <span>5.9K</span>
          </div>
        </div>
      </div>
    );
  }

  if (platform === 'reels') {
    return (
      <div className="absolute inset-0 z-40 pointer-events-none p-3 flex flex-col justify-between text-white">
        <div className="flex items-center justify-between text-xs font-bold">
          <span>Reels</span>
          <Smartphone className="w-4 h-4" />
        </div>
        <div className="flex justify-between items-end pb-2">
          <div className="space-y-1 max-w-[180px]">
            <div className="flex items-center gap-1.5">
              <div className="w-5 h-5 rounded-full bg-gradient-to-tr from-amber-400 to-rose-500" />
              <p className="text-xs font-bold">clipnera</p>
            </div>
            <p className="text-[10px] opacity-90">{title}</p>
          </div>
          <div className="flex flex-col items-center gap-2 text-[10px]">
            <span>❤️ 24K</span>
            <span>💬 830</span>
            <span>✈️ 3.4K</span>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="absolute inset-0 z-40 pointer-events-none p-3 flex flex-col justify-between text-white">
      <div className="flex items-center justify-between text-xs font-bold">
        <span>Shorts</span>
        <Smartphone className="w-4 h-4" />
      </div>
      <div className="flex justify-between items-end pb-2">
        <div className="space-y-1.5 max-w-[180px]">
          <div className="flex items-center gap-1.5">
            <div className="w-5 h-5 rounded-full bg-gradient-to-tr from-rose-500 to-red-600" />
            <p className="text-xs font-bold">@clipnera</p>
            <span className="px-2 py-0.5 rounded-full bg-white text-black text-[9px] font-bold">Subscribe</span>
          </div>
          <p className="text-[10px] opacity-90 line-clamp-2">{title}</p>
        </div>
        <div className="flex flex-col items-center gap-2 text-[10px]">
          <span>👍 18K</span>
          <span>👎</span>
          <span>💬 640</span>
          <span>↗️ 2.1K</span>
        </div>
      </div>
    </div>
  );
}
