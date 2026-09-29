"use client";
import React from 'react';
import { X } from 'lucide-react';
import type { ViralClip } from '@/lib/types';
import { ClipPoster } from '../ClipPoster';

interface ClipSwitcherProps {
  clips: ViralClip[];
  activeId: string;
  onSelect: (clip: ViralClip) => void;
}

/** The project's clips down the left edge on laptops: poster and score, click to switch. */
export function ClipRail({ clips, activeId, onSelect }: ClipSwitcherProps) {
  return (
    <nav
      aria-label="Clips in this project"
      className="[grid-area:rail] flex flex-col items-center gap-2.5 py-3 overflow-y-auto border-r border-neutral-800 bg-neutral-900 [scrollbar-width:none]"
    >
      <h2 className="text-[10px] font-bold uppercase tracking-[0.08em] text-neutral-500">Clips</h2>
      {clips.map((clip, index) => {
        const active = clip.id === activeId;
        return (
          <button
            key={clip.id}
            type="button"
            onClick={() => onSelect(clip)}
            aria-current={active ? 'true' : undefined}
            title={`${index + 1}. ${clip.title}`}
            className="w-[46px] shrink-0 flex flex-col items-center gap-1"
          >
            <ClipPoster
              clip={clip}
              pendingLabel=""
              className={`rounded-lg outline outline-2 outline-offset-2 ${active ? 'outline-amber-400' : 'outline-transparent hover:outline-neutral-700'}`}
            />
            <span className={`text-[10.5px] font-extrabold tabular-nums ${active ? 'text-amber-300' : 'text-neutral-400'}`}>
              {clip.viralityScore}
            </span>
          </button>
        );
      })}
    </nav>
  );
}

/** Tablet: the same clips in a slide-over list. */
export function ClipDrawer({ clips, activeId, onSelect, onClose, projectTitle }: ClipSwitcherProps & { onClose: () => void; projectTitle?: string }) {
  return (
    <>
      <div className="fixed inset-0 z-40 bg-black/45" onClick={onClose} aria-hidden="true" />
      <aside
        role="dialog"
        aria-label="Clips in this project"
        className="fixed inset-y-0 left-0 z-50 w-[340px] max-w-[90vw] flex flex-col border-r border-neutral-700 bg-neutral-900 shadow-2xl shadow-black/60"
      >
        <div className="flex items-center gap-2 px-4 pt-3 pb-2.5">
          <h2 className="flex-1 truncate text-[13px] font-bold text-white">
            Clips{projectTitle ? ` in ${projectTitle}` : ''}
          </h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="w-8 h-8 rounded-[9px] inline-flex items-center justify-center text-neutral-400 hover:bg-neutral-800 hover:text-white"
          >
            <X className="w-4 h-4" aria-hidden />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto px-4 pb-4 space-y-2">
          {clips.map((clip) => (
            <button
              key={clip.id}
              type="button"
              onClick={() => {
                onSelect(clip);
                onClose();
              }}
              aria-current={clip.id === activeId ? 'true' : undefined}
              className={`w-full flex items-center gap-2.5 p-2 rounded-xl border bg-neutral-900 text-left ${
                clip.id === activeId ? 'border-amber-400' : 'border-neutral-800 hover:border-neutral-700'
              }`}
            >
              <ClipPoster clip={clip} pendingLabel="" className="!w-[34px] shrink-0 rounded-md" />
              <span className="min-w-0 flex-1">
                <b className="block truncate text-[12.5px] text-white">{clip.title}</b>
                <small className="text-[11px] text-neutral-500 tabular-nums">
                  Score {clip.viralityScore} · {Math.round(clip.duration)} s
                </small>
              </span>
            </button>
          ))}
        </div>
      </aside>
    </>
  );
}
