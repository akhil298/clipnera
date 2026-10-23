'use client';

import React, { useEffect, useState } from 'react';
import { AlertCircle, Check, Download, Loader2, Sparkles } from 'lucide-react';
import type { EditReel, EditResponse, PremiumPlannedReel } from '@/lib/api';
import { editPhase } from '@/lib/utils/footageReels';

const FRAME_SECONDS = 1.6;

/** While reels are being made: the footage itself (thumbnails from across it while it is read), then one card per
 * reel with a frame from its moment, its hook and where it is. The engine's own stages stay out of sight. */
export function ReelEditingProgress({ edit }: { edit: EditResponse }) {
  const { steps, active, minutesLeft } = editPhase(edit);
  const cover = edit.sources.find((s) => s.kind === 'video' && s.url) ?? edit.sources.find((s) => s.kind === 'image' && s.url);
  const percent = ((active + 0.5) / steps.length) * 100;
  const frames = edit.premium?.frames ?? [];
  const planned = edit.premium?.planned ?? [];
  const many = planned.length;
  const ready = planned.filter((r) => r.status === 'ready').length;
  const editing = planned.find((r) => r.status === 'editing');

  return (
    <div className="mx-auto max-w-5xl space-y-10 py-2">
      <div className="flex flex-wrap items-center justify-center gap-10 lg:gap-16">
        <Preview cover={cover} frames={frames} editing={editing} />

        <section aria-label="Progress" className="flex-[1_1_360px] max-w-md min-w-0 space-y-7">
          <div className="space-y-2">
            <p className="text-[13px] font-bold tracking-[0.14em] text-amber-300">EDITING</p>
            <h2 className="font-syne text-4xl font-extrabold leading-[1.08] text-white" aria-live="polite">
              {many > 1 ? `We're making ${many} reels` : <>We&apos;re editing your reel</>}
            </h2>
            <p className="text-base text-neutral-400">
              {many > 1 ? `Your video has ${many} strong moments. ${ready} of ${many} ready. ` : ''}
              {many > 1 ? 'You can close this tab; we\'ll let you know when they\'re ready.'
                : <>About {minutesLeft} minute{minutesLeft === 1 ? '' : 's'} left. You can close this tab; we&apos;ll let you know when it&apos;s ready.</>}
            </p>
          </div>

          <div className="h-2 rounded-full bg-neutral-800 overflow-hidden" role="progressbar" aria-label="Edit progress"
            aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(percent)}>
            <div className="h-full rounded-full bg-amber-500 transition-[width] duration-700" style={{ width: `${percent}%` }} />
          </div>

          <ol className="space-y-1.5">
            {steps.map((step, i) => {
              const state = i < active ? 'done' : i === active ? 'run' : 'todo';
              return (
                <li key={step} className={`flex items-center gap-4 px-4 py-3 rounded-2xl border transition-colors ${
                  state === 'run' ? 'border-neutral-700 bg-neutral-900' : 'border-transparent'
                }`}>
                  {state === 'done' ? (
                    <span className="w-7 h-7 rounded-full bg-emerald-500/15 text-emerald-300 flex items-center justify-center shrink-0"><Check className="w-4 h-4" /></span>
                  ) : state === 'run' ? (
                    <span className="w-7 h-7 rounded-full border-[3px] border-amber-500 flex items-center justify-center shrink-0">
                      <span className="w-2.5 h-2.5 rounded-full bg-amber-400 animate-pulse" />
                    </span>
                  ) : (
                    <span className="w-7 h-7 rounded-full border-2 border-neutral-700 shrink-0" />
                  )}
                  <span className={`text-base ${state === 'run' ? 'font-semibold text-white' : state === 'done' ? 'text-neutral-300' : 'text-neutral-500'}`}>{step}</span>
                </li>
              );
            })}
          </ol>
        </section>
      </div>

      {planned.length > 0 ? <PlannedReels planned={planned} reels={edit.reels} />
        : frames.length > 0 && <Filmstrip frames={frames} />}
    </div>
  );
}

/** The phone-sized preview: the reel being edited (its moment and hook), else the footage's frames in turn, else the
 * footage itself, softly. */
function Preview({ cover, frames, editing }: {
  cover: EditResponse['sources'][number] | undefined; frames: string[]; editing: PremiumPlannedReel | undefined;
}) {
  const [shown, setShown] = useState(0);
  useEffect(() => {
    if (frames.length < 2 || editing) return;
    const timer = window.setInterval(() => setShown((n) => (n + 1) % frames.length), FRAME_SECONDS * 1000);
    return () => window.clearInterval(timer);
  }, [frames.length, editing]);
  const still = editing?.thumb_url ?? frames[shown];

  return (
    <div className="relative w-[260px] sm:w-[300px] aspect-[9/16] rounded-[28px] overflow-hidden bg-neutral-900 border border-neutral-800 shadow-2xl shadow-amber-500/10 shrink-0" aria-hidden="true">
      {still ? (
        <img key={still} src={still} alt="" className="absolute inset-0 w-full h-full object-cover animate-[caption-fade_0.6s_ease-out_both]" />
      ) : cover?.kind === 'video' && cover.url ? (
        <video src={cover.url} autoPlay muted loop playsInline className="absolute inset-0 w-full h-full object-cover scale-110 blur-[3px] opacity-60" />
      ) : cover?.kind === 'image' && cover.url ? (
        <img src={cover.url} alt="" className="absolute inset-0 w-full h-full object-cover scale-110 blur-[3px] opacity-60" />
      ) : null}
      <div className="absolute inset-0 bg-gradient-to-b from-black/40 via-black/5 to-black/75" />
      {editing ? (
        <p className="absolute left-5 right-5 top-14 text-center font-syne text-2xl font-extrabold leading-tight text-white drop-shadow-[0_3px_10px_rgba(0,0,0,.8)]">
          {editing.title}
        </p>
      ) : (
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="relative flex w-16 h-16">
            <span className="absolute inset-0 rounded-full bg-amber-400/30 animate-ping" />
            <span className="relative w-16 h-16 rounded-full bg-amber-500 text-neutral-950 flex items-center justify-center shadow-lg shadow-amber-500/30">
              <Sparkles className="w-7 h-7" />
            </span>
          </span>
        </div>
      )}
      <div className="absolute left-5 right-5 bottom-6 space-y-2">
        <div className="h-3.5 w-3/4 rounded-md bg-white/15 animate-pulse" />
        <div className="h-3.5 w-1/2 rounded-md bg-amber-400/60 animate-pulse" />
      </div>
    </div>
  );
}

/** Frames from across the video, while it is read. */
function Filmstrip({ frames }: { frames: string[] }) {
  return (
    <section aria-label="Your video" className="space-y-3">
      <p className="text-[13px] font-bold tracking-[0.14em] text-neutral-400">READING YOUR VIDEO</p>
      <ul className="grid grid-cols-[repeat(auto-fill,minmax(96px,1fr))] gap-2.5">
        {frames.map((url, i) => (
          <li key={url} className="aspect-video rounded-xl overflow-hidden bg-neutral-900 border border-neutral-800">
            <img src={url} alt="" className="w-full h-full object-cover animate-[caption-fade_0.6s_ease-out_both]" style={{ animationDelay: `${i * 80}ms` }} />
          </li>
        ))}
      </ul>
    </section>
  );
}

const BADGE: Record<PremiumPlannedReel['status'], { label: string; className: string }> = {
  queued: { label: 'Up next', className: 'bg-neutral-900/80 text-neutral-300' },
  editing: { label: 'Editing', className: 'bg-amber-500 text-neutral-950' },
  ready: { label: 'Ready', className: 'bg-emerald-500 text-neutral-950' },
  failed: { label: "Couldn't make this one", className: 'bg-red-500/90 text-white' },
};

/** One card per reel: a frame from its moment and its hook while it waits or is edited; the reel itself once ready. */
function PlannedReels({ planned, reels }: { planned: PremiumPlannedReel[]; reels: EditReel[] }) {
  // Ready reels arrive in the same order as their moments (failed ones have no reel).
  let next = 0;
  const cards = planned.map((reel) => ({ reel, video: reel.status === 'ready' ? reels[next++] : undefined }));

  return (
    <section aria-label="Your reels" className="space-y-3">
      <p className="text-[13px] font-bold tracking-[0.14em] text-neutral-400">YOUR REELS</p>
      <ul className="grid grid-cols-[repeat(auto-fill,minmax(150px,1fr))] gap-4">
        {cards.map(({ reel, video }, i) => (
          <li key={i} className="relative aspect-[9/16] rounded-2xl overflow-hidden border border-neutral-800 bg-neutral-900">
            {video?.url ? (
              <video src={video.url} controls playsInline preload="metadata" className="absolute inset-0 w-full h-full object-cover bg-black" />
            ) : (
              <>
                {reel.thumb_url && <img src={reel.thumb_url} alt="" className={`absolute inset-0 w-full h-full object-cover ${reel.status === 'queued' ? 'opacity-50' : ''}`} />}
                <div className="absolute inset-0 bg-gradient-to-b from-black/60 via-transparent to-black/70" />
                <p className="absolute left-3 right-3 top-3 text-[15px] font-bold leading-snug text-white drop-shadow-[0_2px_6px_rgba(0,0,0,.8)]">{reel.title}</p>
              </>
            )}
            <span className={`absolute left-3 bottom-3 inline-flex items-center gap-1.5 h-7 px-2.5 rounded-full text-[12px] font-bold ${BADGE[reel.status].className}`}>
              {reel.status === 'editing' && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
              {reel.status === 'ready' && <Check className="w-3.5 h-3.5" />}
              {reel.status === 'failed' && <AlertCircle className="w-3.5 h-3.5" />}
              {BADGE[reel.status].label}
            </span>
            {video?.url && (
              <a href={video.url} download aria-label={`Download reel ${i + 1}`}
                className="absolute top-2 right-2 w-9 h-9 rounded-xl bg-amber-500 hover:bg-amber-400 text-neutral-950 flex items-center justify-center">
                <Download className="w-4 h-4" />
              </a>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
