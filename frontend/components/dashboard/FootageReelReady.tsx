'use client';

import React, { useState } from 'react';
import { Check, Copy, Download, Pencil, Plus } from 'lucide-react';
import type { EditResponse } from '@/lib/api';
import { formatSeconds } from '@/lib/utils/footageReels';

function CopyButton({ text, labelText }: { text: string; labelText: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button type="button" aria-label={labelText}
      onClick={() => navigator.clipboard.writeText(text).then(() => { setCopied(true); setTimeout(() => setCopied(false), 1500); }).catch(() => undefined)}
      className="ml-auto inline-flex items-center gap-1.5 h-10 px-3.5 rounded-xl border border-neutral-700 text-[13px] font-semibold text-neutral-200 hover:bg-neutral-800">
      {copied ? <Check className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4" />} {copied ? 'Copied' : 'Copy'}
    </button>
  );
}

/** The finished reel: watch it, take it, copy its post text, or go back and change it. */
export function FootageReelReady({ edit, onEdit, onNew }: { edit: EditResponse; onEdit?: () => void; onNew: () => void }) {
  const plan = edit.plan;
  const caption = [plan?.caption, plan?.hashtags.join(' '), edit.music_credit].filter(Boolean).join('\n\n');

  return (
    <div className="flex flex-wrap gap-8 lg:gap-10 items-start">
      <section aria-label="Your reel" className="flex-[0_1_420px] min-w-[260px] space-y-3">
        <video src={edit.output_url ?? undefined} controls playsInline className="w-full aspect-[9/16] rounded-[28px] bg-black border border-neutral-800" />
        <p className="text-[13px] text-neutral-400 text-center">{formatSeconds(edit.duration_s)} · {edit.credits_charged} credits used</p>
      </section>

      <section className="flex-[999_1_480px] min-w-0 space-y-5">
        <div className="space-y-2">
          <h2 className="font-syne text-4xl sm:text-5xl font-extrabold leading-none text-white">Your reel is ready.</h2>
          <p className="text-[17px] text-neutral-400 max-w-xl">
            {onEdit
              ? 'Download it and post it. Want a change? Go back to the plan; a re-render costs a quarter of the first one.'
              : 'Download it and post it. Below is how the AI edited it and how its review scored it.'}
          </p>
        </div>
        <div className="flex flex-wrap gap-2.5">
          {edit.output_url && (
            <a href={edit.output_url} download className="inline-flex items-center gap-2.5 h-14 px-6 rounded-2xl bg-amber-500 hover:bg-amber-400 text-neutral-950 text-base font-bold">
              <Download className="w-5 h-5" /> Download MP4
            </a>
          )}
          {onEdit && (
            <button type="button" onClick={onEdit} className="inline-flex items-center gap-2 h-14 px-5 rounded-2xl border border-neutral-700 bg-neutral-900 hover:bg-neutral-800 text-[15px] font-semibold text-white">
              <Pencil className="w-4 h-4" /> Make changes
            </button>
          )}
          <button type="button" onClick={onNew} className="inline-flex items-center gap-2 h-14 px-5 rounded-2xl text-[15px] font-semibold text-amber-300 hover:bg-amber-500/10">
            <Plus className="w-4 h-4" /> Make another reel
          </button>
        </div>

        {caption && (
          <div className="rounded-[22px] border border-neutral-800 bg-neutral-900/80 p-5 sm:px-6 space-y-3">
            <div className="flex items-center gap-3">
              <h3 className="text-base font-semibold text-white">Caption for your post</h3>
              <CopyButton text={caption} labelText="Copy the caption" />
            </div>
            <p className="text-[15px] text-neutral-200 whitespace-pre-line">{caption}</p>
          </div>
        )}
        {edit.music_credit && (
          <div className="rounded-[22px] border border-neutral-800 bg-neutral-900/80 p-5 sm:px-6 space-y-2">
            <div className="flex items-center gap-3">
              <h3 className="text-base font-semibold text-white">Music credit</h3>
              <CopyButton text={edit.music_credit} labelText="Copy the music credit" />
            </div>
            <p className="text-[15px] text-neutral-200">{edit.music_credit}</p>
            <p className="text-[13px] text-neutral-400">The track's licence asks for this credit. It's already in the caption above.</p>
          </div>
        )}
      </section>
    </div>
  );
}
