'use client';

import React, { useEffect, useMemo, useState } from 'react';
import { ChevronDown, Clapperboard, Film, Image as ImageIcon, Loader2, Mic, Sparkles, X } from 'lucide-react';
import {
  EDIT_AUDIO_TYPES,
  EDIT_IMAGE_TYPES,
  EDIT_VIDEO_TYPES,
  EditLimitsResponse,
  EditScriptMode,
  EditSourceType,
  EditTargetSeconds,
  editsApi,
} from '@/lib/api';
import { canUseCaptionStyle, useEntitlements } from '@/hooks/useEntitlements';
import { DEFAULT_CAPTION_PRESET, getAllCaptionStyles } from '@/lib/utils/captionStyles';
import {
  SCRIPT_MODE_OPTIONS,
  TARGET_OPTIONS,
  estimateEditCredits,
  formatSeconds,
  mediaDuration,
} from '@/lib/utils/footageReels';

const LANGUAGES = [
  ['en', 'English'], ['hi', 'Hindi'], ['te', 'Telugu'], ['hinglish', 'Hinglish'], ['tenglish', 'Tenglish'],
] as const;
const field = 'w-full h-10 px-3 rounded-xl bg-neutral-950 border border-neutral-800 text-[13px] text-white placeholder:text-neutral-600 focus:outline-none focus:border-amber-400';
const label = 'block text-xs font-semibold text-neutral-300 mb-1.5';
const MEDIA_TYPES = [...EDIT_VIDEO_TYPES, ...EDIT_IMAGE_TYPES];

interface Picked {
  file: File;
  durationS: number | null;
  preview: string | null;
}

function Collapsible({ id, title, hint, open, onToggle, children }: {
  id: string; title: string; hint: string; open: boolean; onToggle: () => void; children: React.ReactNode;
}) {
  return (
    <div className="rounded-xl border border-neutral-800 bg-neutral-950/40">
      <button type="button" onClick={onToggle} aria-expanded={open} aria-controls={id}
        className="w-full flex items-center justify-between gap-2 px-3 h-10 text-left">
        <span className="text-xs font-semibold text-white">{title} <span className="font-normal text-neutral-500">· {hint}</span></span>
        <ChevronDown className={`w-4 h-4 text-neutral-400 transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>
      {open && <div id={id} className="px-3 pb-3 space-y-2">{children}</div>}
    </div>
  );
}

export function FootageReelForm({ onCreated }: { onCreated: (id: string) => void }) {
  const { entitlements } = useEntitlements();
  const isPro = Boolean(entitlements?.pro_ai_provider);
  const [limits, setLimits] = useState<EditLimitsResponse | null>(null);
  const [title, setTitle] = useState('');
  const [media, setMedia] = useState<Picked[]>([]);
  const [voice, setVoice] = useState<File | null>(null);
  const [script, setScript] = useState('');
  const [scriptMode, setScriptMode] = useState<EditScriptMode>('auto');
  const [intent, setIntent] = useState('');
  const [language, setLanguage] = useState('en');
  const [captionStyle, setCaptionStyle] = useState<string>(DEFAULT_CAPTION_PRESET);
  const [target, setTarget] = useState<EditTargetSeconds>(0);
  const [autopilot, setAutopilot] = useState(false);
  const [showScript, setShowScript] = useState(false);
  const [showVoice, setShowVoice] = useState(false);
  const [progress, setProgress] = useState<number[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    editsApi.limits().then(setLimits).catch(() => setLimits(null));
  }, []);
  useEffect(() => () => media.forEach((m) => m.preview && URL.revokeObjectURL(m.preview)), [media]);

  const rawSeconds = media.reduce((sum, m) => sum + (m.durationS ?? 0), 0);
  const fileCount = media.length + (voice ? 1 : 0);
  const overFootage = limits ? rawSeconds > limits.max_raw_seconds : false;
  const overFiles = limits ? fileCount > limits.max_files : false;
  const captionOptions = useMemo(
    () => getAllCaptionStyles().filter((s) => !entitlements || canUseCaptionStyle(entitlements, s.id)),
    [entitlements],
  );
  const estimate = estimateEditCredits(target || 30, rawSeconds, isPro && Boolean(limits?.opus_director));

  const addMedia = async (files: FileList | File[] | null) => {
    const picked = Array.from(files || []).filter((f) => MEDIA_TYPES.includes(f.type as EditSourceType));
    const read = await Promise.all(picked.map(async (file) => ({
      file,
      durationS: await mediaDuration(file),
      preview: file.type.startsWith('image/') ? URL.createObjectURL(file) : null,
    })));
    setMedia((prev) => [...prev, ...read]);
  };

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const edit = await editsApi.create({
        title: title.trim() || 'Untitled reel',
        script: script.trim() || null,
        script_mode: scriptMode,
        intent: intent.trim() || null,
        language,
        caption_style: captionStyle,
        target_seconds: target,
        autopilot,
      });
      const files = [...media.map(({ file, durationS }) => ({ file, durationS })), ...(voice ? [{ file: voice, durationS: await mediaDuration(voice) }] : [])];
      setProgress(files.map(() => 0));
      await editsApi.uploadSources(edit.id, files, (i, f) => setProgress((prev) => prev && prev.map((v, j) => (j === i ? f : v))));
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
  const canSubmit = media.length > 0 && !overFootage && !overFiles && !busy;

  return (
    <form onSubmit={submit} className="p-4 sm:p-5 rounded-2xl bg-neutral-900/80 border border-neutral-800 space-y-4" aria-labelledby="new-footage-reel">
      <h2 id="new-footage-reel" className="sr-only">Edit my footage</h2>
      <div>
        <label htmlFor="footage-title" className={label}>Title <span className="font-normal text-neutral-500">· optional</span></label>
        <input id="footage-title" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="We'll name it from your footage" className={field} />
      </div>

      <div>
        <span className={label}>Videos and photos</span>
        <label
          className="flex items-center gap-3 p-3 rounded-xl border-2 border-dashed border-neutral-800 hover:border-amber-500/50 bg-neutral-950/60 cursor-pointer transition-colors"
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => {
            e.preventDefault();
            addMedia(e.dataTransfer.files);
          }}
        >
          <span className="w-9 h-9 rounded-lg bg-amber-500/10 text-amber-400 flex items-center justify-center shrink-0"><Film className="w-4 h-4" /></span>
          <span className="text-xs">
            <span className="block font-semibold text-white">Drop your raw videos and photos</span>
            <span className="text-neutral-500">
              MP4, MOV, JPG, PNG · up to {limits ? `${Math.round(limits.max_raw_seconds / 60)} min of footage` : '…'} on your plan
            </span>
          </span>
          <input type="file" multiple accept={MEDIA_TYPES.join(',')} className="sr-only" onChange={(e) => addMedia(e.target.files)} />
        </label>
        {media.length > 0 && (
          <>
            <ul className="mt-2 flex flex-wrap gap-2" aria-label="Chosen files">
              {media.map((m, i) => (
                <li key={`${m.file.name}-${i}`} className="relative w-12 aspect-[9/16] rounded-lg overflow-hidden border border-neutral-800 bg-gradient-to-b from-neutral-700 to-neutral-900">
                  {m.preview ? <img src={m.preview} alt="" className="w-full h-full object-cover" /> : (
                    <span className="absolute inset-0 flex items-center justify-center"><Film className="w-4 h-4 text-neutral-400" /></span>
                  )}
                  {m.durationS !== null && (
                    <span className="absolute bottom-0.5 inset-x-0 text-center font-mono text-[9.5px] font-semibold text-white">{formatSeconds(m.durationS)}</span>
                  )}
                  {progress && (
                    <span className="absolute bottom-0 left-0 h-0.5 bg-amber-400" style={{ width: `${(progress[i] ?? 0) * 100}%` }} />
                  )}
                  <button type="button" disabled={busy} onClick={() => setMedia((prev) => prev.filter((_, j) => j !== i))}
                    className="absolute top-0.5 right-0.5 w-5 h-5 rounded-full bg-black/70 text-white flex items-center justify-center"
                    aria-label={`Remove ${m.file.name}`}>
                    <X className="w-3 h-3" />
                  </button>
                </li>
              ))}
            </ul>
            <p className={`mt-1.5 text-[11.5px] ${overFootage || overFiles ? 'text-rose-300' : 'text-emerald-300'}`}>
              {fileCount} file{fileCount === 1 ? '' : 's'} · {formatSeconds(rawSeconds)}
              {limits ? ` of ${formatSeconds(limits.max_raw_seconds)} used` : ''}
              {overFootage && ' · too much footage for your plan'}
              {overFiles && ` · your plan takes up to ${limits?.max_files} files`}
            </p>
          </>
        )}
      </div>

      <div>
        <span className={label}>Length</span>
        <div className="flex flex-wrap gap-1.5" role="group" aria-label="Reel length">
          {TARGET_OPTIONS.map((seconds) => {
            const locked = limits ? seconds > limits.max_output_seconds : false;
            return (
              <button key={seconds} type="button" disabled={locked} onClick={() => setTarget(seconds)} aria-pressed={target === seconds}
                className={`h-8 px-3 rounded-full border text-xs font-semibold transition-colors disabled:opacity-50 ${
                  target === seconds ? 'border-amber-400 text-amber-300 bg-amber-500/10' : 'border-neutral-700 text-neutral-300 hover:text-white'
                }`}>
                {seconds === 0 ? 'Auto' : `${seconds} s`}{locked ? ' · Pro' : ''}
              </button>
            );
          })}
        </div>
      </div>

      <Collapsible id="footage-script" title="Add a script" hint="optional" open={showScript} onToggle={() => setShowScript((v) => !v)}>
        <label htmlFor="footage-script-text" className="sr-only">Script</label>
        <textarea id="footage-script-text" value={script} onChange={(e) => setScript(e.target.value)} rows={5} maxLength={6000}
          placeholder="Paste what you say in the video, a voiceover to read, or notes. We follow it exactly when it's what you said."
          className={`${field} h-auto py-2.5 resize-y leading-relaxed`} />
        <label htmlFor="footage-script-mode" className={label}>How should we use it?</label>
        <select id="footage-script-mode" value={scriptMode} onChange={(e) => setScriptMode(e.target.value as EditScriptMode)} className={field}>
          {SCRIPT_MODE_OPTIONS.map(([value, name]) => <option key={value} value={value}>{name}</option>)}
        </select>
      </Collapsible>

      <Collapsible id="footage-voice" title="Add a voiceover" hint="optional" open={showVoice} onToggle={() => setShowVoice((v) => !v)}>
        <label className="flex items-center gap-3 p-3 rounded-xl border-2 border-dashed border-neutral-800 hover:border-amber-500/50 bg-neutral-950/60 cursor-pointer transition-colors">
          <span className="w-9 h-9 rounded-lg bg-amber-500/10 text-amber-400 flex items-center justify-center shrink-0"><Mic className="w-4 h-4" /></span>
          <span className="text-xs min-w-0 flex-1">
            <span className="block font-semibold text-white truncate">{voice ? voice.name : 'Add a voiceover recording'}</span>
            <span className="text-neutral-500">It becomes the spine of the reel; your clips illustrate it</span>
          </span>
          {voice && (
            <button type="button" onClick={(e) => { e.preventDefault(); setVoice(null); }} className="p-1 text-neutral-400 hover:text-white" aria-label="Remove voiceover">
              <X className="w-4 h-4" />
            </button>
          )}
          <input type="file" accept={EDIT_AUDIO_TYPES.join(',')} className="sr-only" onChange={(e) => setVoice(e.target.files?.[0] ?? null)} />
        </label>
      </Collapsible>

      <div>
        <label htmlFor="footage-intent" className={label}>What should it feel like? <span className="font-normal text-neutral-500">· optional</span></label>
        <input id="footage-intent" value={intent} onChange={(e) => setIntent(e.target.value)} maxLength={300}
          placeholder="e.g. funny, calm, sell the product" className={field} />
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label htmlFor="footage-language" className={label}>Language</label>
          <select id="footage-language" value={language} onChange={(e) => setLanguage(e.target.value)} className={field}>
            {LANGUAGES.map(([value, name]) => <option key={value} value={value}>{name}</option>)}
          </select>
        </div>
        <div>
          <label htmlFor="footage-captions" className={label}>Captions</label>
          <select id="footage-captions" value={captionStyle} onChange={(e) => setCaptionStyle(e.target.value)} className={field}>
            {captionOptions.map((style) => <option key={style.id} value={style.id}>{style.name}</option>)}
          </select>
        </div>
      </div>

      <label className="flex items-center gap-3 cursor-pointer">
        <input type="checkbox" checked={autopilot} onChange={(e) => setAutopilot(e.target.checked)} className="peer sr-only" />
        <span className="relative w-9 h-5 rounded-full bg-neutral-700 peer-checked:bg-amber-500 transition-colors after:absolute after:top-0.5 after:left-0.5 after:w-4 after:h-4 after:rounded-full after:bg-white after:transition-transform peer-checked:after:translate-x-4 peer-focus-visible:ring-2 peer-focus-visible:ring-amber-400" />
        <span className="text-xs text-neutral-300">Autopilot: render as soon as the plan is ready</span>
      </label>

      {error && <p role="alert" className="text-xs text-rose-300">{error}</p>}
      <button type="submit" disabled={!canSubmit}
        className="w-full h-10 rounded-xl bg-amber-500 hover:bg-amber-400 text-neutral-950 text-[13px] font-bold disabled:opacity-40 flex items-center justify-center gap-2 transition-colors">
        {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Clapperboard className="w-4 h-4" />}
        {busy ? (progress && uploaded < 1 ? `Uploading ${Math.round(uploaded * 100)}%` : 'Starting…') : 'Analyse footage'}
      </button>
      <p className="text-[11.5px] text-neutral-500 text-center -mt-2 flex items-center justify-center gap-1.5">
        {media.length === 0 ? <><ImageIcon className="w-3.5 h-3.5" /> Add at least one video or photo to continue.</> : (
          <><Sparkles className="w-3.5 h-3.5 text-amber-400" /> Planning and previews are free. About {estimate} credits when you render
            {entitlements ? ` · you have ${entitlements.credit_minutes_remaining}` : ''}.</>
        )}
      </p>
    </form>
  );
}
