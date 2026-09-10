"use client";
import React, { useState } from 'react';
import { RotateCcw, Play, Pause, Volume2, VolumeX, Headphones, Check } from 'lucide-react';

const pseudoRandom = (i: number) => {
  const x = Math.sin(i * 12.9898 + 78.233) * 43758.5453;
  return x - Math.floor(x);
};

interface AudioBeforeAfterProps {
  beforeUrl?: string;
  afterUrl?: string;
  isReverted?: boolean;
  onRevert?: () => void;
  onApply?: () => void;
}

export const AudioBeforeAfter: React.FC<AudioBeforeAfterProps> = ({
  beforeUrl,
  afterUrl,
  isReverted = false,
  onRevert,
  onApply,
}) => {
  const [playing, setPlaying] = useState<'before' | 'after' | null>(null);
  const [muted, setMuted] = useState(false);

  if (!beforeUrl && !afterUrl) return null;

  return (
    <div className="rounded-xl bg-neutral-900 border border-neutral-800 p-4 space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-xs font-bold uppercase tracking-wider text-neutral-300 flex items-center gap-2">
          <Headphones className="w-4 h-4 text-amber-400" />
          AI Noise Cancellation Result
        </h3>
        {!isReverted ? (
          <button
            onClick={onRevert}
            className="px-3 py-1.5 rounded-lg bg-neutral-800 hover:bg-neutral-700 text-xs font-semibold text-neutral-300 border border-neutral-700 transition-colors flex items-center gap-1.5"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            Revert to Original
          </button>
        ) : (
          <button
            onClick={onApply}
            className="px-3 py-1.5 rounded-lg bg-amber-500 hover:bg-amber-400 text-neutral-950 text-xs font-bold transition-colors flex items-center gap-1.5"
          >
            <Check className="w-3.5 h-3.5" />
            Re-apply Denoising
          </button>
        )}
      </div>

      <div className="grid grid-cols-2 gap-3">
        {/* Before */}
        <div className={`p-3 rounded-xl border ${isReverted ? 'bg-emerald-500/5 border-emerald-500/30' : 'bg-neutral-950 border-neutral-800'}`}>
          <div className="flex items-center justify-between mb-2">
            <span className="text-[10px] font-bold uppercase tracking-wider text-neutral-400">
              {isReverted ? 'Current (Original)' : 'Original'}
            </span>
            <span className={`text-[9px] font-mono px-1.5 py-0.5 rounded font-bold ${isReverted ? 'bg-emerald-500/20 text-emerald-400' : 'bg-neutral-800 text-neutral-400'}`}>
              {isReverted ? 'ACTIVE' : 'BEFORE'}
            </span>
          </div>
          <div className="h-12 bg-neutral-900 rounded-lg border border-neutral-800 flex items-center justify-center gap-1 px-2">
            {Array.from({ length: 20 }).map((_, i) => (
              <div
                key={i}
                className="w-1 bg-neutral-600 rounded-full"
                style={{
                  height: `${20 + Math.sin(i * 0.5) * 15 + pseudoRandom(i) * 10}%`,
                }}
              />
            ))}
          </div>
          <div className="flex items-center justify-between mt-2">
            <button
              onClick={() => setPlaying(playing === 'before' ? null : 'before')}
              className="p-1.5 rounded-lg bg-neutral-800 hover:bg-neutral-700 text-neutral-300 transition-colors"
            >
              {playing === 'before' ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
            </button>
            <span className="text-[10px] text-neutral-500 font-mono">Original Audio</span>
          </div>
        </div>

        {/* After */}
        <div className={`p-3 rounded-xl border ${!isReverted && afterUrl ? 'bg-amber-500/5 border-amber-500/30' : 'bg-neutral-950 border-neutral-800'}`}>
          <div className="flex items-center justify-between mb-2">
            <span className="text-[10px] font-bold uppercase tracking-wider text-neutral-400">
              {!isReverted && afterUrl ? 'Denoised' : 'Processed'}
            </span>
            <span className={`text-[9px] font-mono px-1.5 py-0.5 rounded font-bold ${!isReverted && afterUrl ? 'bg-amber-500/20 text-amber-400' : 'bg-neutral-800 text-neutral-400'}`}>
              {isReverted ? 'BYPASSED' : 'AFTER'}
            </span>
          </div>
          <div className="h-12 bg-neutral-900 rounded-lg border border-neutral-800 flex items-center justify-center gap-1 px-2">
            {Array.from({ length: 20 }).map((_, i) => (
              <div
                key={i}
                className={`w-1 rounded-full ${!isReverted && afterUrl ? 'bg-amber-500/60' : 'bg-neutral-600'}`}
                style={{
                  height: `${15 + Math.sin(i * 0.7) * 12 + pseudoRandom(i + 100) * 8}%`,
                }}
              />
            ))}
          </div>
          <div className="flex items-center justify-between mt-2">
            <button
              onClick={() => setPlaying(playing === 'after' ? null : 'after')}
              className="p-1.5 rounded-lg bg-neutral-800 hover:bg-neutral-700 text-neutral-300 transition-colors"
            >
              {playing === 'after' ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
            </button>
            <span className="text-[10px] text-neutral-500 font-mono">
              {!isReverted && afterUrl ? 'AI Enhanced' : 'Awaiting Processing'}
            </span>
          </div>
        </div>
      </div>

      {muted && (
        <div className="flex items-center gap-1.5 text-[10px] text-neutral-400">
          <VolumeX className="w-3 h-3" />
          <span>Preview muted</span>
        </div>
      )}
    </div>
  );
};
