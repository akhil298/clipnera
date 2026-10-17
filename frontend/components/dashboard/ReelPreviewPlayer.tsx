'use client';

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Pause, Play, RotateCcw } from 'lucide-react';
import type { EditPicture, EditSourceResponse, EditTimelineResponse, EditVoicePiece } from '@/lib/api';
import { formatSeconds } from '@/lib/utils/footageReels';

/** CSS stand-ins for the FFmpeg looks in backend/edit_engine/looks.py; the preview is close, not exact. */
const LOOK_FILTERS: Record<string, string> = {
  natural: 'contrast(1.03) saturate(1.05)',
  clean_bright: 'brightness(1.05) contrast(1.05) saturate(1.08)',
  warm_film: 'sepia(0.15) contrast(1.06) saturate(0.95)',
  teal_orange: 'contrast(1.08) saturate(1.1) hue-rotate(-8deg)',
  moody: 'contrast(1.12) brightness(0.94) saturate(0.8)',
  vivid: 'contrast(1.08) saturate(1.3)',
  bw_punch: 'grayscale(1) contrast(1.25)',
};
const WORDS_PER_LINE = 3;

const activeAt = <T extends { at: number }>(items: T[], t: number, length: (item: T) => number): T | undefined =>
  items.find((item) => item.at <= t && t < item.at + length(item));

const voiceLength = (piece: EditVoicePiece) => piece.source_end - piece.source_start;

/**
 * Plays a compiled timeline in the browser from the small proxies, so a plan can be
 * watched and changed without the server rendering anything. One muted video shows
 * the picture, a second element plays the voice, and the music runs underneath.
 */
export function ReelPreviewPlayer({ timeline, sources, musicUrl, seek, onTime }: {
  timeline: EditTimelineResponse; sources: EditSourceResponse[]; musicUrl: string | null;
  /** Jump here; a new ``n`` asks again for the same time. */
  seek?: { to: number; n: number };
  /** The preview position as it plays or is moved. */
  onTime?: (t: number) => void;
}) {
  const picture = useRef<HTMLVideoElement>(null);
  const voice = useRef<HTMLVideoElement>(null);
  const voiceover = useRef<HTMLAudioElement>(null);
  const music = useRef<HTMLAudioElement>(null);
  const clock = useRef<{ startedAt: number; from: number } | null>(null);
  const shown = useRef<{ picture?: EditPicture; voice?: EditVoicePiece }>({});
  const [t, setT] = useState(0);
  const [playing, setPlaying] = useState(false);

  const url = useCallback((src: number | null) => (src === null ? null : sources[src]?.url ?? null), [sources]);

  const sync = useCallback((time: number, force = false) => {
    const item = activeAt(timeline.picture, time, (p) => p.dur);
    if (item && (force || item !== shown.current.picture)) {
      shown.current.picture = item;
      const el = picture.current;
      const src = url(item.src);
      if (el && item.kind === 'video' && src) {
        if (el.getAttribute('src') !== src) el.src = src;
        el.currentTime = (item.source_start ?? 0) + (time - item.at);
        if (clock.current) el.play().catch(() => undefined);
      }
    }
    const piece = activeAt(timeline.voice, time, voiceLength);
    const el = voice.current;
    if (el && (force || piece !== shown.current.voice)) {
      shown.current.voice = piece;
      const src = piece ? url(piece.src) : null;
      if (piece && src) {
        if (el.getAttribute('src') !== src) el.src = src;
        el.currentTime = piece.source_start + (time - piece.at);
        if (clock.current) el.play().catch(() => undefined);
      } else {
        el.pause();
      }
    }
  }, [timeline, url]);

  const play = (from: number) => {
    const start = from >= timeline.duration - 0.05 ? 0 : from;
    clock.current = { startedAt: performance.now(), from: start };
    sync(start, true);
    if (voiceover.current) {
      voiceover.current.currentTime = start;
      voiceover.current.play().catch(() => undefined);
    }
    if (music.current && timeline.music) {
      music.current.volume = Math.min(1, 10 ** (timeline.music.gain_db / 20));
      music.current.currentTime = timeline.music.offset + start;
      music.current.play().catch(() => undefined);
    }
    setPlaying(true);
  };

  const pause = useCallback(() => {
    clock.current = null;
    [picture, voice, voiceover, music].forEach((ref) => ref.current?.pause());
    setPlaying(false);
  }, []);

  useEffect(() => {
    if (!playing) return;
    let frame = 0;
    const tick = () => {
      if (!clock.current) return;
      const now = clock.current.from + (performance.now() - clock.current.startedAt) / 1000;
      if (now >= timeline.duration) {
        pause();
        setT(timeline.duration);
        return;
      }
      sync(now);
      setT(now);
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [playing, timeline, sync, pause]);

  // A new plan (a change was applied) starts the preview over.
  useEffect(() => {
    pause();
    shown.current = {};
    setT(0);
    sync(0, true);
  }, [timeline, sync, pause]);

  // Only a new request jumps, so a recompiled plan still starts over from 0.
  const sought = useRef(seek?.n);
  useEffect(() => {
    if (!seek || seek.n === sought.current) return;
    sought.current = seek.n;
    pause();
    const to = Math.min(Math.max(0, seek.to), timeline.duration);
    setT(to);
    sync(to, true);
  }, [seek, timeline.duration, sync, pause]);

  useEffect(() => onTime?.(t), [t, onTime]);

  const current = activeAt(timeline.picture, t, (p) => p.dur) ?? timeline.picture[0];
  const wordIndex = timeline.words.findIndex((w) => w.start <= t && t < w.end + 0.25);
  const lineStart = wordIndex >= 0 ? wordIndex - (wordIndex % WORDS_PER_LINE) : -1;
  const line = lineStart >= 0 ? timeline.words.slice(lineStart, lineStart + WORDS_PER_LINE) : [];
  const texts = timeline.texts.filter((x) => x.at <= t && t < x.at + x.dur);
  const voiceoverUrl = url(timeline.voiceover_src);

  return (
    <div className="w-full max-w-[400px] space-y-3">
      <div className="relative aspect-[9/16] rounded-[28px] overflow-hidden bg-black border border-neutral-800"
        style={{ filter: LOOK_FILTERS[timeline.look] ?? LOOK_FILTERS.natural }}>
        <video ref={picture} muted playsInline preload="auto" aria-hidden="true"
          className={`absolute inset-0 w-full h-full object-cover ${current?.kind === 'video' ? '' : 'invisible'}`}
          style={{
            objectPosition: `${((current?.crop_x ?? 0.5) * 100).toFixed(1)}% 45%`,
            transform: `scale(${current?.zoom ?? 1})`,
          }} />
        {current?.kind === 'image' && url(current.src) && (
          <img src={url(current.src) ?? ''} alt="" className="absolute inset-0 w-full h-full object-cover" />
        )}
        {current?.kind === 'card' && (
          <div className="absolute inset-0 bg-neutral-950 flex items-center justify-center px-6 text-center text-2xl font-black uppercase leading-tight text-amber-300">
            {current.text}
          </div>
        )}
        {texts.map((text) => (
          <span key={`${text.kind}-${text.at}`}
            className={`absolute inset-x-4 text-center font-black uppercase leading-tight ${
              text.kind === 'hook' ? 'top-[18%] text-xl text-amber-300 bg-black/40 rounded-md px-2 py-1'
                : text.kind === 'pop' ? 'top-[36%] text-3xl text-white [text-shadow:0_2px_6px_rgba(0,0,0,.8)]'
                  : 'top-[66%] text-sm normal-case text-white bg-black/40 rounded-md px-2 py-1'
            }`}>
            {text.text}
          </span>
        ))}
        {line.length > 0 && (
          <p className="absolute inset-x-3 bottom-[24%] text-center text-lg font-black uppercase leading-tight [text-shadow:0_2px_4px_rgba(0,0,0,.9)]">
            {line.map((w, i) => (
              <span key={`${w.start}-${i}`} className={lineStart + i === wordIndex ? 'text-amber-300' : 'text-white'}>{w.word} </span>
            ))}
          </p>
        )}
        <button type="button" onClick={() => (playing ? pause() : play(t))} aria-label={playing ? 'Pause preview' : 'Play preview'}
          className="absolute inset-0 flex items-center justify-center group">
          {!playing && (
            <span className="w-14 h-14 rounded-full bg-black/60 group-hover:bg-black/75 flex items-center justify-center">
              <Play className="w-6 h-6 text-white translate-x-0.5" />
            </span>
          )}
        </button>
      </div>
      <div className="flex items-center gap-3">
        <button type="button" onClick={() => (playing ? pause() : play(t))}
          className="w-12 h-12 shrink-0 rounded-full bg-neutral-100 hover:bg-white text-neutral-950 flex items-center justify-center"
          aria-label={playing ? 'Pause preview' : 'Play preview'}>
          {playing ? <Pause className="w-5 h-5" /> : <Play className="w-5 h-5 translate-x-0.5" />}
        </button>
        <button type="button" onClick={() => { pause(); setT(0); sync(0, true); }}
          className="w-11 h-11 shrink-0 rounded-xl border border-neutral-800 text-neutral-300 hover:text-white hover:bg-neutral-800 flex items-center justify-center"
          aria-label="Back to the start">
          <RotateCcw className="w-4 h-4" />
        </button>
        <input type="range" min={0} max={timeline.duration} step={0.05} value={t} aria-label="Preview position"
          onChange={(e) => {
            const to = Number(e.target.value);
            setT(to);
            if (playing) play(to);
            else sync(to, true);
          }}
          className="flex-1 accent-amber-400" />
        <span className="font-mono text-xs text-neutral-400 tabular-nums">{formatSeconds(t)} / {formatSeconds(timeline.duration)}</span>
      </div>
      <p className="text-xs text-neutral-500">Preview plays in your browser and is close to the final; the render is sharper and fully mixed.</p>
      <video ref={voice} playsInline preload="auto" className="hidden" />
      {voiceoverUrl && <audio ref={voiceover} src={voiceoverUrl} preload="auto" className="hidden" />}
      {musicUrl && <audio ref={music} src={musicUrl} preload="auto" className="hidden" />}
    </div>
  );
}
