'use client';

import React, { useEffect, useRef, useState } from 'react';
import { ArrowRight, Film, Image as ImageIcon, Instagram, Link2, Loader2, Mic, Sparkles, Upload, X, Youtube } from 'lucide-react';
import {
  EDIT_AUDIO_TYPES,
  EDIT_IMAGE_TYPES,
  EDIT_VIDEO_TYPES,
  EditLimitsResponse,
  EditSourceType,
  editsApi,
} from '@/lib/api';
import { useEntitlements } from '@/hooks/useEntitlements';
import { DEFAULT_CAPTION_PRESET } from '@/lib/utils/captionStyles';
import { INTENT_MAX, estimateEditCredits, formatSeconds, isInstagramLink, isSourceLink, mediaDuration } from '@/lib/utils/footageReels';

const ACCEPTED = [...EDIT_VIDEO_TYPES, ...EDIT_IMAGE_TYPES, ...EDIT_AUDIO_TYPES];
/** The big card a new reel is made in, shared with the photos form. */
export const COMPOSER = 'rounded-[28px] border border-neutral-800 bg-neutral-900/80 p-2.5 space-y-2.5';
const field = 'h-12 px-4 rounded-xl bg-neutral-950 border border-neutral-800 text-[15px] text-white placeholder:text-neutral-500 focus:outline-none focus:border-amber-400';

interface Picked {
  file: File;
  durationS: number | null;
  preview: string;
}

const kindOf = (file: File): 'video' | 'image' | 'audio' =>
  file.type.startsWith('image/') ? 'image' : file.type.startsWith('audio/') ? 'audio' : 'video';

/** Start a reel: drop videos, photos or a voiceover and/or paste a YouTube or Instagram reel link, then one click. The AI does the rest. */
export function FootageReelForm({ onCreated }: { onCreated: (id: string) => void }) {
  const { entitlements } = useEntitlements();
  const isPro = Boolean(entitlements?.pro_ai_provider);
  const [limits, setLimits] = useState<EditLimitsResponse | null>(null);
  const [files, setFiles] = useState<Picked[]>([]);
  const [link, setLink] = useState<string | null>(null);
  const [linkDraft, setLinkDraft] = useState('');
  const [intent, setIntent] = useState('');
  const [dragging, setDragging] = useState(false);
  const [progress, setProgress] = useState<number[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    editsApi.limits().then(setLimits).catch(() => setLimits(null));
  }, []);
  // Previews are freed when their file is removed, and the rest when the form goes away.
  const shown = useRef<string[]>([]);
  shown.current = files.map((f) => f.preview);
  useEffect(() => () => shown.current.forEach((url) => URL.revokeObjectURL(url)), []);

  const addFiles = async (list: FileList | File[] | null) => {
    const accepted = Array.from(list || []).filter((f) => ACCEPTED.includes(f.type as EditSourceType));
    const skipped = (list?.length ?? 0) - accepted.length;
    const voices = files.filter((f) => kindOf(f.file) === 'audio').length;
    const kept = accepted.filter((f, i) => kindOf(f) !== 'audio' || voices + accepted.slice(0, i).filter((g) => kindOf(g) === 'audio').length < 1);
    const picked = await Promise.all(kept.map(async (file) => ({ file, durationS: await mediaDuration(file), preview: URL.createObjectURL(file) })));
    setFiles((prev) => [...prev, ...picked]);
    setError(skipped > 0 ? 'Some files were skipped: use MP4, MOV, JPG, PNG, WebP, MP3, M4A or WAV.'
      : kept.length < accepted.length ? 'One voiceover per reel: the extra audio file was skipped.' : null);
  };

  const remove = (item: Picked) => {
    URL.revokeObjectURL(item.preview);
    setFiles((prev) => prev.filter((f) => f !== item));
  };

  const addLink = () => {
    const url = linkDraft.trim();
    if (!isSourceLink(url)) {
      setError('Paste a YouTube video, Shorts or Instagram reel link.');
      return;
    }
    setError(null);
    setLink(url);
    setLinkDraft('');
  };

  const linkIsInstagram = Boolean(link && isInstagramLink(link));
  const linkName = linkIsInstagram ? 'Instagram reel' : 'YouTube video';
  const footage = files.filter((f) => kindOf(f.file) !== 'audio');
  const rawSeconds = files.reduce((sum, f) => sum + (kindOf(f.file) === 'video' ? f.durationS ?? 0 : 0), 0);
  const overFootage = limits ? rawSeconds > limits.max_raw_seconds : false;
  const overFiles = limits ? files.length > limits.max_files : false;
  const hasSource = footage.length > 0 || Boolean(link);
  const canSubmit = hasSource && !overFootage && !overFiles && !busy;
  const estimate = estimateEditCredits(45, rawSeconds, true);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!canSubmit) return;
    setBusy(true);
    setError(null);
    try {
      const edit = await editsApi.create({
        title: 'Untitled reel',
        intent: intent.trim() || null,
        language: 'auto',
        caption_style: DEFAULT_CAPTION_PRESET,
        target_seconds: 0,
        // Pro gets the premium edit; everyone else gets a plan that renders by itself. Either way: one click.
        engine: isPro ? 'premium' : 'classic',
        autopilot: !isPro,
        source_url: link,
      });
      if (files.length) {
        setProgress(files.map(() => 0));
        await editsApi.uploadSources(edit.id, files.map(({ file, durationS }) => ({ file, durationS })),
          (i, f) => setProgress((prev) => prev && prev.map((v, j) => (j === i ? f : v))));
      }
      await editsApi.analyze(edit.id);
      onCreated(edit.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not start the reel');
      setProgress(null);
    } finally {
      setBusy(false);
    }
  };

  const uploaded = progress ? progress.reduce((a, b) => a + b, 0) / Math.max(1, progress.length) : 0;

  return (
    <section aria-label="New reel" className={`${COMPOSER} max-w-3xl mx-auto w-full`}>
      <form onSubmit={submit} className="rounded-[22px] bg-neutral-950 border border-neutral-800 p-4 sm:p-6 flex flex-col gap-5">
        {/* Files */}
        <label
          className={`rounded-2xl border-2 border-dashed p-7 sm:p-9 flex flex-col items-center gap-3 text-center cursor-pointer transition-colors ${
            dragging ? 'border-amber-400 bg-amber-500/[0.06]' : 'border-neutral-700 hover:border-amber-500/50 bg-neutral-900/40'
          }`}
          onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => { e.preventDefault(); setDragging(false); addFiles(e.dataTransfer.files); }}
        >
          <span className="w-14 h-14 rounded-2xl bg-amber-500/10 border border-amber-500/25 text-amber-400 flex items-center justify-center"><Upload className="w-6 h-6" /></span>
          <span className="text-lg font-bold text-white">Drag videos, photos or audio here</span>
          <span className="text-sm text-neutral-400">
            MP4, MOV, JPG, PNG, MP3 · up to {limits ? `${Math.round(limits.max_raw_seconds / 60)} min of video` : '…'} on your plan
          </span>
          <span className="mt-1 inline-flex items-center h-11 px-5 rounded-xl border border-neutral-700 bg-neutral-800 text-[15px] font-semibold text-white">Choose files</span>
          <input type="file" multiple accept={ACCEPTED.join(',')} className="sr-only" disabled={busy} onChange={(e) => { addFiles(e.target.files); e.target.value = ''; }} />
        </label>

        {/* Link */}
        <div className="flex items-center gap-3 text-xs font-semibold tracking-wider text-neutral-500" aria-hidden="true">
          <span className="flex-1 h-px bg-neutral-800" /> OR PASTE A YOUTUBE OR INSTAGRAM LINK <span className="flex-1 h-px bg-neutral-800" />
        </div>
        <div className="flex flex-wrap gap-2.5">
          <label htmlFor="source-link" className="sr-only">YouTube or Instagram reel link</label>
          <div className="flex-[1_1_320px] min-w-0 relative">
            <Link2 className="w-5 h-5 text-neutral-500 absolute left-4 top-1/2 -translate-y-1/2" aria-hidden="true" />
            <input id="source-link" value={linkDraft} onChange={(e) => setLinkDraft(e.target.value)} disabled={busy || Boolean(link)} maxLength={1000}
              onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addLink(); } }}
              placeholder={link ? 'One link per reel' : 'YouTube or Instagram reel link'} className={`${field} w-full pl-12`} />
          </div>
          <button type="button" onClick={addLink} disabled={busy || Boolean(link) || !linkDraft.trim()}
            className="h-12 px-5 rounded-xl bg-neutral-800 hover:bg-neutral-700 text-[15px] font-semibold text-white disabled:opacity-40">Add link</button>
        </div>

        {/* What's added */}
        {(files.length > 0 || link) && (
          <div className="flex flex-col gap-2">
            <div className="flex items-baseline justify-between text-[13px]">
              <span className="font-semibold text-neutral-300">Added</span>
              <span className={overFootage || overFiles ? 'text-rose-300' : 'text-neutral-400'}>
                {overFootage ? `Over your plan's ${Math.round((limits?.max_raw_seconds ?? 0) / 60)} min of video`
                  : overFiles ? `Your plan takes up to ${limits?.max_files} files`
                  : `${files.length + (link ? 1 : 0)} item${files.length + (link ? 1 : 0) === 1 ? '' : 's'}${rawSeconds ? ` · ${formatSeconds(rawSeconds)} of video` : ''}`}
              </span>
            </div>
            <ul className="flex flex-col gap-2" aria-label="Added for this reel">
              {link && (
                <li className="flex items-center gap-3.5 p-2.5 rounded-xl bg-neutral-900 border border-neutral-800">
                  <span className="w-14 h-11 rounded-lg bg-neutral-800 flex items-center justify-center shrink-0">
                    {linkIsInstagram ? <Instagram className="w-5 h-5 text-amber-400" /> : <Youtube className="w-5 h-5 text-amber-400" />}
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block text-[15px] font-semibold text-white truncate">{link}</span>
                    <span className="block text-[13px] text-neutral-400">{linkName} · we fetch it for you</span>
                  </span>
                  <button type="button" disabled={busy} onClick={() => setLink(null)} aria-label={`Remove the ${linkName} link`}
                    className="w-11 h-11 rounded-xl text-neutral-400 hover:text-white hover:bg-neutral-800 flex items-center justify-center shrink-0"><X className="w-4 h-4" /></button>
                </li>
              )}
              {files.map((f, i) => {
                const kind = kindOf(f.file);
                const Icon = kind === 'image' ? ImageIcon : kind === 'audio' ? Mic : Film;
                return (
                  <li key={f.preview} className="relative flex items-center gap-3.5 p-2.5 rounded-xl bg-neutral-900 border border-neutral-800 overflow-hidden">
                    <span className="relative w-14 h-11 rounded-lg bg-neutral-800 overflow-hidden flex items-center justify-center shrink-0">
                      {kind === 'image' ? <img src={f.preview} alt="" className="absolute inset-0 w-full h-full object-cover" />
                        : kind === 'video' ? <video src={f.preview} muted playsInline preload="metadata" aria-hidden="true" className="absolute inset-0 w-full h-full object-cover" />
                        : <Icon className="w-5 h-5 text-amber-400" />}
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block text-[15px] font-semibold text-white truncate">{f.file.name}</span>
                      <span className="block text-[13px] text-neutral-400">
                        {kind === 'image' ? 'Photo' : kind === 'audio' ? 'Voiceover' : 'Video'}{f.durationS ? ` · ${formatSeconds(f.durationS)}` : ''}
                      </span>
                    </span>
                    <button type="button" disabled={busy} onClick={() => remove(f)} aria-label={`Remove ${f.file.name}`}
                      className="w-11 h-11 rounded-xl text-neutral-400 hover:text-white hover:bg-neutral-800 flex items-center justify-center shrink-0"><X className="w-4 h-4" /></button>
                    {progress && <span className="absolute left-0 bottom-0 h-0.5 bg-amber-400" style={{ width: `${(progress[i] ?? 0) * 100}%` }} />}
                  </li>
                );
              })}
            </ul>
          </div>
        )}

        {/* Optional note */}
        <div className="flex flex-col gap-2">
          <label htmlFor="footage-intent" className="text-[13px] font-semibold text-neutral-300">
            Anything we should know? <span className="font-normal text-neutral-500">(optional)</span>
          </label>
          <input id="footage-intent" value={intent} onChange={(e) => setIntent(e.target.value)} maxLength={INTENT_MAX} disabled={busy}
            placeholder="e.g. Keep the part about pricing, make it punchy" className={field} />
        </div>

        {/* Go */}
        <button type="submit" disabled={!canSubmit}
          className={`h-14 rounded-2xl text-[17px] font-bold flex items-center justify-center gap-2.5 transition-colors ${
            hasSource ? 'bg-amber-500 hover:bg-amber-400 text-neutral-950 disabled:opacity-50' : 'bg-neutral-800 text-neutral-400 cursor-not-allowed'
          }`}>
          {busy ? <Loader2 className="w-5 h-5 animate-spin" /> : hasSource ? <ArrowRight className="w-5 h-5" /> : null}
          {busy ? (progress && uploaded < 1 ? `Uploading ${Math.round(uploaded * 100)}%` : 'Starting…')
            : hasSource ? 'Create my reel' : 'Add a video, photo or link to start'}
        </button>
        <p className="flex items-center justify-center gap-2 text-[13px] text-neutral-400 text-center">
          <Sparkles className="w-4 h-4 text-amber-400 shrink-0" aria-hidden="true" />
          {link && !footage.length ? 'Edited by GPT-Astra · credits are based on the video\'s length; long videos give several reels, each extra one costs less'
            : `Edited by GPT-Astra · about ${estimate} credits, each extra reel costs less${entitlements ? ` · you have ${entitlements.credit_minutes_remaining}` : ''}`}
        </p>
        {error && <p role="alert" className="text-sm text-rose-300 text-center">{error}</p>}
      </form>
    </section>
  );
}
