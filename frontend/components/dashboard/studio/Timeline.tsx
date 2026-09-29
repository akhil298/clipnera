"use client";
import React, { useRef, useState } from 'react';
import { AudioLines, Film, Layers, Music, Search, Type } from 'lucide-react';
import type { BRollOverlay, SoundEffect, WordTimestamp } from '@/lib/types';
import { TimeRange, formatClock, isWordCut } from './studioUtils';

interface TimelineProps {
  duration: number;
  currentTime: number;
  onSeek: (time: number) => void;
  words: WordTimestamp[];
  removed: ReadonlySet<number>;
  captionGroups: WordTimestamp[][];
  cuts: TimeRange[];
  bRoll: BRollOverlay[];
  soundEffects: SoundEffect[];
  title: string;
  posterUrl?: string;
  denoiseOn: boolean;
  /** Phones get a two-lane strip without labels or zoom. */
  variant?: 'full' | 'strip';
}

const TICK_STEPS = [1, 2, 5, 10, 15, 30, 60, 120];
const hatch = 'bg-[repeating-linear-gradient(135deg,rgba(251,113,133,0.35)_0_4px,rgba(251,113,133,0.08)_4px_8px)] border border-rose-400/70';

/** Everything in the clip on one ruler. Click or drag anywhere to move the playhead. */
export function Timeline(props: TimelineProps) {
  const { duration, currentTime, onSeek, words, removed, captionGroups, cuts, bRoll, soundEffects, title, posterUrl, denoiseOn, variant = 'full' } = props;
  const lanesRef = useRef<HTMLDivElement>(null);
  const [zoom, setZoom] = useState(1);
  const [scrubbing, setScrubbing] = useState(false);
  const total = Math.max(0.1, duration);
  const pct = (t: number) => `${(Math.max(0, Math.min(total, t)) / total) * 100}%`;
  const width = (from: number, to: number) => `${(Math.max(0, to - from) / total) * 100}%`;

  const seekFromPointer = (clientX: number) => {
    const rect = lanesRef.current?.getBoundingClientRect();
    if (!rect || rect.width === 0) return;
    onSeek(Math.max(0, Math.min(total - 0.05, ((clientX - rect.left) / rect.width) * total)));
  };

  const scrubHandlers = {
    onPointerDown: (e: React.PointerEvent) => {
      e.currentTarget.setPointerCapture(e.pointerId);
      setScrubbing(true);
      seekFromPointer(e.clientX);
    },
    onPointerMove: (e: React.PointerEvent) => scrubbing && seekFromPointer(e.clientX),
    onPointerUp: () => setScrubbing(false),
    onPointerCancel: () => setScrubbing(false),
  };

  const film = (
    <div
      className="absolute inset-y-[3px] inset-x-0 rounded-md overflow-hidden bg-neutral-800"
      style={
        posterUrl
          ? { backgroundImage: `url("${posterUrl}")`, backgroundSize: 'auto 100%', backgroundRepeat: 'repeat-x' }
          : { backgroundImage: 'linear-gradient(180deg,#2b2016,#0d0906)' }
      }
    />
  );
  const cutBlocks = cuts.map((c) => (
    <span key={c.start} title="Cut" className={`absolute inset-y-0 z-[2] rounded-[3px] ${hatch}`} style={{ left: pct(c.start), width: width(c.start, c.end) }} />
  ));
  const captionBlocks = (active: string) =>
    captionGroups.map((group) => {
      const start = group[0].start;
      const end = group[group.length - 1].end;
      const on = currentTime >= start && currentTime < end;
      return (
        <span
          key={group[0].id}
          className={`absolute inset-y-[3px] rounded-[5px] border px-[3px] overflow-hidden whitespace-nowrap text-[10px] font-semibold flex items-center ${
            on ? active : 'bg-amber-500/15 border-amber-500/35 text-amber-200'
          }`}
          style={{ left: pct(start), width: `calc(${width(start, end)} - 2px)` }}
        >
          {variant === 'full' && group.map((w) => w.text).join(' ')}
        </span>
      );
    });
  const playhead = (
    <div className="absolute inset-y-0 z-[8] w-0 pointer-events-none" style={{ left: pct(currentTime) }}>
      <span className="absolute -left-px inset-y-0 w-0.5 bg-white" />
      <span className="absolute -left-1.5 top-0 w-3 h-3 bg-white [clip-path:polygon(0_0,100%_0,100%_55%,50%_100%,0_55%)]" />
    </div>
  );

  if (variant === 'strip') {
    return (
      <div ref={lanesRef} {...scrubHandlers} className="relative mx-3 touch-none cursor-pointer" aria-label="Timeline" role="group">
        <div className="relative h-[34px]">
          {film}
          {cutBlocks}
          {bRoll.map((b) => (
            <span key={b.id} className="absolute bottom-0 h-1.5 rounded-sm bg-sky-400/60" style={{ left: pct(b.start), width: width(b.start, b.start + b.duration) }} />
          ))}
        </div>
        <div className="relative h-5">{captionBlocks('bg-amber-500/40 border-amber-400 text-white')}</div>
        {playhead}
      </div>
    );
  }

  const step = TICK_STEPS.find((s) => total / s <= 9 * zoom) ?? 300;
  const ticks = Array.from({ length: Math.floor(total / step) + 1 }, (_, i) => i * step);
  const lanes: Array<{ id: string; label: string; icon: React.ReactNode; tall?: boolean; note?: string; content: React.ReactNode }> = [
    {
      id: 'title',
      label: 'Title',
      icon: <Type className="w-3 h-3" />,
      content: title.trim() ? (
        <span className="absolute inset-y-[3px] left-0 right-0 rounded-[5px] border border-fuchsia-400/55 bg-fuchsia-400/15 px-1.5 text-[10px] font-bold text-fuchsia-200 flex items-center overflow-hidden whitespace-nowrap">
          {title}
        </span>
      ) : null,
    },
    { id: 'video', label: 'Video', icon: <Film className="w-3 h-3" />, tall: true, content: <>{film}{cutBlocks}</> },
    { id: 'captions', label: 'Captions', icon: <Type className="w-3 h-3" />, content: captionBlocks('bg-amber-500/40 border-amber-400 text-white') },
    {
      id: 'broll',
      label: 'B-roll',
      icon: <Layers className="w-3 h-3" />,
      content: bRoll.map((b) => (
        <span
          key={b.id}
          className="absolute inset-y-[3px] rounded-[5px] border border-sky-400/55 bg-sky-400/15 px-1.5 text-[10px] font-bold text-sky-200 flex items-center overflow-hidden whitespace-nowrap"
          style={{ left: pct(b.start), width: width(b.start, b.start + b.duration) }}
        >
          {b.title}
        </span>
      )),
    },
    {
      id: 'sfx',
      label: 'Sound',
      note: 'preview',
      icon: <Music className="w-3 h-3" />,
      content: soundEffects.map((s) => (
        <span
          key={s.id}
          title={`${s.name} · ${formatClock(s.time)}`}
          className="absolute top-1/2 w-[11px] h-[11px] -translate-x-1/2 -translate-y-1/2 rotate-45 border-[1.5px] border-dashed border-rose-400 bg-rose-400/15"
          style={{ left: pct(s.time) }}
        />
      )),
    },
    {
      id: 'speech',
      label: 'Speech',
      icon: <AudioLines className="w-3 h-3" />,
      content: (
        <>
          {words.map((w, i) => {
            const cut = isWordCut(w, removed);
            return (
              <span
                key={w.id}
                className={`absolute top-1/2 -translate-y-1/2 rounded-sm ${cut ? 'bg-rose-400/45' : 'bg-emerald-400/55'}`}
                style={{ left: pct(w.start), width: `max(2px, calc(${width(w.start, w.end)} - 1px))`, height: `${40 + ((w.text.length * 7 + i * 13) % 45)}%` }}
              />
            );
          })}
          {denoiseOn && (
            <span className="absolute right-0 inset-y-1 px-1.5 rounded-[5px] border border-emerald-400/40 bg-emerald-400/15 text-[9.5px] font-bold text-emerald-300 flex items-center">
              Denoise on
            </span>
          )}
        </>
      ),
    },
  ];

  return (
    <section aria-label="Timeline" className="[grid-area:tl] flex flex-col min-w-0 min-h-0 border-t border-neutral-800 bg-neutral-900">
      <div className="flex items-center gap-2.5 px-3 py-1.5 border-b border-neutral-800/70">
        <span className="flex-1 text-[11.5px] text-neutral-500">Click or drag to move the playhead · hatched = cut from the clip</span>
        <label className="inline-flex items-center gap-1.5 text-neutral-500">
          <Search className="w-3.5 h-3.5" aria-hidden />
          <span className="sr-only">Timeline zoom</span>
          <input
            type="range"
            min={1}
            max={4}
            step={0.5}
            value={zoom}
            onChange={(e) => setZoom(Number(e.target.value))}
            className="w-[70px] h-1 bg-neutral-800 rounded-lg appearance-none cursor-pointer accent-amber-400"
          />
        </label>
      </div>
      <div className="flex-1 min-h-0 grid grid-cols-[92px_minmax(0,1fr)] overflow-y-auto">
        <div className="border-r border-neutral-800/70">
          <div className="h-5 border-b border-neutral-800/50" />
          {lanes.map((lane) => (
            <div
              key={lane.id}
              className={`flex items-center gap-1.5 px-2.5 border-b border-neutral-800/50 text-[11px] font-semibold text-neutral-400 whitespace-nowrap [&>svg]:text-neutral-500 ${lane.tall ? 'h-[38px]' : 'h-[26px]'}`}
            >
              {lane.icon}
              {lane.label}
              {lane.note && (
                <span className="rounded border border-dashed border-rose-400/70 px-[3px] text-[8px] font-extrabold uppercase text-rose-300">{lane.note}</span>
              )}
            </div>
          ))}
        </div>
        <div className="min-w-0 overflow-x-auto">
          <div
            ref={lanesRef}
            {...scrubHandlers}
            className="relative mx-2.5 touch-none cursor-pointer"
            style={{ width: `calc(${zoom * 100}% - 20px)` }}
          >
            <div className="relative h-5 border-b border-neutral-800/50">
              {ticks.map((t) => (
                <span
                  key={t}
                  className="absolute top-1 -translate-x-1/2 font-mono text-[9.5px] text-neutral-500 after:absolute after:left-1/2 after:top-[13px] after:h-1 after:w-px after:bg-neutral-700"
                  style={{ left: pct(t) }}
                >
                  {formatClock(t)}
                </span>
              ))}
            </div>
            {lanes.map((lane) => (
              <div key={lane.id} className={`relative border-b border-neutral-800/50 ${lane.tall ? 'h-[38px]' : 'h-[26px]'}`}>
                {lane.content}
              </div>
            ))}
            {playhead}
          </div>
        </div>
      </div>
    </section>
  );
}
