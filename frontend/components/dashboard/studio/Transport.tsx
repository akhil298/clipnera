"use client";
import React from 'react';
import { ChevronsLeft, ChevronsRight, Pause, Play, RotateCcw, Volume2, VolumeX } from 'lucide-react';
import { Select, SelectOption } from '@/components/ui/Select';
import { formatPrecise } from './studioUtils';

const PLAYBACK_SPEED_OPTIONS: SelectOption<number>[] = [
  { value: 0.75, label: '0.75×' },
  { value: 1, label: '1×' },
  { value: 1.25, label: '1.25×' },
  { value: 1.5, label: '1.5×' },
  { value: 2, label: '2×' },
];

const iconButton = 'w-8 h-8 rounded-[9px] inline-flex items-center justify-center text-neutral-400 hover:bg-neutral-800 hover:text-white';

interface TransportProps {
  isPlaying: boolean;
  onTogglePlay: () => void;
  currentTime: number;
  duration: number;
  onSeek: (time: number) => void;
  speed: number;
  onSpeed: (speed: number) => void;
  muted: boolean;
  onToggleMute: () => void;
  compact?: boolean;
}

export function Transport({ isPlaying, onTogglePlay, currentTime, duration, onSeek, speed, onSpeed, muted, onToggleMute, compact }: TransportProps) {
  return (
    <div className="flex justify-center px-3.5 pt-2 pb-3">
      <div className="inline-flex items-center gap-1 px-2 py-[5px] rounded-[14px] border border-neutral-800 bg-neutral-900">
        {!compact && (
          <button type="button" onClick={() => onSeek(0)} className={iconButton} aria-label="Restart">
            <RotateCcw className="w-4 h-4" aria-hidden />
          </button>
        )}
        <button type="button" onClick={() => onSeek(currentTime - 2)} className={iconButton} aria-label="Back 2 seconds" title="Back 2 s (J)">
          <ChevronsLeft className="w-4 h-4" aria-hidden />
        </button>
        <button
          type="button"
          onClick={onTogglePlay}
          className="w-[38px] h-[38px] mx-1 rounded-full bg-neutral-100 hover:bg-white text-neutral-950 inline-flex items-center justify-center"
          aria-label={isPlaying ? 'Pause' : 'Play'}
          title={`${isPlaying ? 'Pause' : 'Play'} (Space)`}
        >
          {isPlaying ? <Pause className="w-4 h-4 fill-current" aria-hidden /> : <Play className="w-4 h-4 fill-current ml-0.5" aria-hidden />}
        </button>
        <button type="button" onClick={() => onSeek(currentTime + 2)} className={iconButton} aria-label="Forward 2 seconds" title="Forward 2 s (L)">
          <ChevronsRight className="w-4 h-4" aria-hidden />
        </button>
        <span className="px-1.5 font-mono text-xs text-neutral-400 whitespace-nowrap tabular-nums">
          <b className="font-medium text-neutral-100">{formatPrecise(currentTime)}</b> / {formatPrecise(duration)}
        </span>
        {!compact && (
          <>
            <Select
              value={speed}
              onChange={onSpeed}
              options={PLAYBACK_SPEED_OPTIONS}
              aria-label="Playback speed"
              className="h-7 px-2 rounded-lg border border-neutral-800 font-mono text-[11.5px] text-neutral-400"
            />
            <button type="button" onClick={onToggleMute} className={iconButton} aria-label={muted ? 'Unmute' : 'Mute'}>
              {muted ? <VolumeX className="w-4 h-4 text-rose-400" aria-hidden /> : <Volume2 className="w-4 h-4" aria-hidden />}
            </button>
          </>
        )}
      </div>
    </div>
  );
}
