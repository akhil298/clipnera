'use client';

import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Film, Link2, Loader2, Mic, Plus, ScrollText, Sparkles, Upload, X } from 'lucide-react';
import {
  EDIT_AUDIO_TYPES,
  EDIT_IMAGE_TYPES,
  EDIT_VIDEO_TYPES,
  EditLimitsResponse,
  EditScriptMode,
  EditSourceType,
  EditTargetSeconds,
  editsApi,
  type EditEngine,
} from '@/lib/api';
import { canUseCaptionStyle, useEntitlements } from '@/hooks/useEntitlements';
import { DEFAULT_CAPTION_PRESET, getAllCaptionStyles } from '@/lib/utils/captionStyles';
import {
  BRIEF_IDEAS,
  BRIEF_STARTERS,
  INTENT_MAX,
  REFERENCE_MAX_SECONDS,
  SCRIPT_MODE_OPTIONS,
  TARGET_OPTIONS,
  estimateEditCredits,
  formatSeconds,
  isReferenceLink,
  mediaDuration,
} from '@/lib/utils/footageReels';
import { ReelModelPicker, useReelPick } from './ReelModelPicker';

const LANGUAGES = [
  ['en', 'English'], ['hi', 'Hindi'], ['te', 'Telugu'], ['hinglish', 'Hinglish'], ['tenglish', 'Tenglish'],
] as const;
const MEDIA_TYPES = [...EDIT_VIDEO_TYPES, ...EDIT_IMAGE_TYPES];
const field = 'h-11 px-3.5 rounded-xl bg-neutral-900 border border-neutral-800 text-sm text-white placeholder:text-neutral-600 focus:outline-none focus:border-amber-400';
/** The big card a new reel is made in, shared with the photos form. */
export const COMPOSER = 'rounded-[28px] border border-neutral-800 bg-neutral-900/80 p-2.5 space-y-2.5';
const card = 'rounded-[22px] border border-neutral-800 bg-neutral-950';
const label = 'block text-[13px] font-semibold text-neutral-400';
const ghost = 'inline-flex items-center gap-2 h-11 px-4 rounded-xl border border-neutral-800 text-sm font-semibold text-neutral-200 hover:bg-neutral-800 transition-colors';
const pill = (on: boolean) =>
  `h-11 px-4 rounded-full border text-sm font-semibold transition-colors disabled:opacity-40 ${
    on ? 'border-amber-500 bg-amber-500 text-neutral-950' : 'border-neutral-800 bg-neutral-900 text-neutral-300 hover:text-white hover:border-neutral-700'
  }`;

interface Picked {
  file: File;
  durationS: number | null;
  preview: string;
}

type Reference = ({ kind: 'file' } & Picked) | { kind: 'link'; url: string };

const pick = async (file: File): Promise<Picked> => ({ file, durationS: await mediaDuration(file), preview: URL.createObjectURL(file) });

function Thumb({ item }: { item: Picked }) {
  return item.file.type.startsWith('image/')
    ? <img src={item.preview} alt="" className="absolute inset-0 w-full h-full object-cover" />
    : <video src={item.preview} muted playsInline preload="metadata" aria-hidden="true" className="absolute inset-0 w-full h-full object-cover" />;
}

/** Start a footage reel: drop the clips, say how to edit them, optionally show a reel to copy, pick the model. */
export function FootageReelForm({ tabs, onCreated }: { tabs?: React.ReactNode; onCreated: (id: string) => void }) {
  const { entitlements } = useEntitlements();
  const pickModel = useReelPick();
  const isPro = Boolean(entitlements?.pro_ai_provider);
  const [limits, setLimits] = useState<EditLimitsResponse | null>(null);
  const [title, setTitle] = useState('');
  const [media, setMedia] = useState<Picked[]>([]);
  const [voice, setVoice] = useState<File | null>(null);
  const [script, setScript] = useState('');
  const [scriptMode, setScriptMode] = useState<EditScriptMode>('auto');
  const [intent, setIntent] = useState('');
  const [reference, setReference] = useState<Reference | null>(null);
  const [linkDraft, setLinkDraft] = useState<string | null>(null);
  const [language, setLanguage] = useState('en');
  const [captionStyle, setCaptionStyle] = useState<string>(DEFAULT_CAPTION_PRESET);
  const [target, setTarget] = useState<EditTargetSeconds>(0);
  const [autopilot, setAutopilot] = useState(false);
  // Pro defaults to the premium edit; anyone can still choose to plan, review and render themselves.
  const [engine, setEngine] = useState<EditEngine | null>(null);
  const chosenEngine: EditEngine = engine ?? (isPro ? 'premium' : 'classic');
  const [showScript, setShowScript] = useState(false);
  const [showVoice, setShowVoice] = useState(false);
  const [progress, setProgress] = useState<number[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    editsApi.limits().then(setLimits).catch(() => setLimits(null));
  }, []);
  // Thumbnails are freed when their file is removed, and the rest when the form goes away.
  const shown = useRef<string[]>([]);
  shown.current = [...media.map((m) => m.preview), ...(reference?.kind === 'file' ? [reference.preview] : [])];
  useEffect(() => () => shown.current.forEach((url) => URL.revokeObjectURL(url)), []);
  const removeMedia = (item: Picked) => {
    URL.revokeObjectURL(item.preview);
    setMedia((prev) => prev.filter((m) => m !== item));
  };
  const removeReference = () => {
    if (reference?.kind === 'file') URL.revokeObjectURL(reference.preview);
    setReference(null);
  };

  const rawSeconds = media.reduce((sum, m) => sum + (m.durationS ?? 0), 0);
  const fileCount = media.length + (voice ? 1 : 0);
  const overFootage = limits ? rawSeconds > limits.max_raw_seconds : false;
  const overFiles = limits ? fileCount > limits.max_files : false;
  const used = limits ? Math.min(1, rawSeconds / limits.max_raw_seconds) : 0;
  const captionOptions = useMemo(
    () => getAllCaptionStyles().filter((s) => !entitlements || canUseCaptionStyle(entitlements, s.id)),
    [entitlements],
  );
  const estimate = chosenEngine === 'premium'
    ? estimateEditCredits(target || 45, rawSeconds, true)
    : estimateEditCredits(target || 30, rawSeconds, isPro && Boolean(limits?.opus_director) && !pickModel.ai_model);

  const addMedia = async (files: FileList | File[] | null) => {
    const picked = await Promise.all(Array.from(files || []).filter((f) => MEDIA_TYPES.includes(f.type as EditSourceType)).map(pick));
    setMedia((prev) => [...prev, ...picked]);
  };

  const addReference = async (file: File | undefined) => {
    if (!file || !EDIT_VIDEO_TYPES.includes(file.type as EditSourceType)) return;
    const picked = await pick(file);
    if ((picked.durationS ?? 0) > REFERENCE_MAX_SECONDS) {
      URL.revokeObjectURL(picked.preview);
      setError(`Use a reference reel under ${REFERENCE_MAX_SECONDS / 60} minutes.`);
      return;
    }
    setError(null);
    removeReference();
    setReference({ kind: 'file', ...picked });
  };

  const applyLink = () => {
    const url = (linkDraft ?? '').trim();
    if (!isReferenceLink(url)) {
      setError('Paste a YouTube or Shorts link. For an Instagram reel, upload the video instead.');
      return;
    }
    setError(null);
    setReference({ kind: 'link', url });
    setLinkDraft(null);
  };

  const addIdea = (idea: string) => setIntent((prev) => (prev.trim() ? `${prev.trim().replace(/\.$/, '')}. ${idea}.` : `${idea}.`).slice(0, INTENT_MAX));

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
        ...pickModel,
        reference_url: reference?.kind === 'link' ? reference.url : null,
        engine: chosenEngine,
      });
      const files = [
        ...media.map(({ file, durationS }) => ({ file, durationS })),
        ...(voice ? [{ file: voice, durationS: await mediaDuration(voice) }] : []),
        ...(reference?.kind === 'file' ? [{ file: reference.file, durationS: reference.durationS, reference: true }] : []),
      ];
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
  const referenceProgress = progress && reference?.kind === 'file' ? progress[progress.length - 1] : null;
  const canSubmit = media.length > 0 && !overFootage && !overFiles && !busy;

  return (
    <>
      <section aria-label="New reel" className={COMPOSER}>
        {tabs}
        <form onSubmit={submit} className="flex flex-col gap-2.5" aria-labelledby="new-footage-reel">
          <h2 id="new-footage-reel" className="sr-only">Edit my footage</h2>
          <div className="flex flex-wrap gap-2.5">
            {/* The footage */}
            <div
              className="flex-[1_1_420px] min-w-0 rounded-[22px] border-2 border-dashed border-neutral-800 hover:border-amber-500/40 bg-neutral-950 p-5 sm:p-6 flex flex-col gap-5 transition-colors"
              onDragOver={(e) => e.preventDefault()}
              onDrop={(e) => {
                e.preventDefault();
                addMedia(e.dataTransfer.files);
              }}
            >
              <div className="flex items-center gap-3.5">
                <span className="w-12 h-12 rounded-2xl bg-amber-500/10 text-amber-400 flex items-center justify-center shrink-0"><Upload className="w-5 h-5" /></span>
                <div className="min-w-0">
                  <p className="text-[17px] font-semibold text-white">Drop raw videos, clips and photos</p>
                  <p className="text-sm text-neutral-400">
                    MP4, MOV, JPG, PNG · up to {limits ? `${Math.round(limits.max_raw_seconds / 60)} min of footage` : '…'} on your plan
                  </p>
                </div>
                <label className={`${ghost} ml-auto shrink-0 cursor-pointer`}>
                  Browse
                  <input type="file" multiple accept={MEDIA_TYPES.join(',')} className="sr-only" onChange={(e) => addMedia(e.target.files)} />
                </label>
              </div>

              {media.length > 0 && (
                <>
                  <ul aria-label="Your files" className="grid grid-cols-[repeat(auto-fill,minmax(112px,1fr))] gap-3">
                    {media.map((m, i) => (
                      <li key={m.preview} className="min-w-0 space-y-1.5">
                        <div className="relative aspect-[9/16] rounded-2xl overflow-hidden bg-neutral-900 border border-neutral-800">
                          <Thumb item={m} />
                          <span className="absolute left-2 bottom-2 px-1.5 py-0.5 rounded-md bg-black/70 font-mono text-xs font-semibold text-white">
                            {m.durationS !== null ? formatSeconds(m.durationS) : 'Photo'}
                          </span>
                          <button type="button" disabled={busy} onClick={() => removeMedia(m)}
                            className="absolute top-1.5 right-1.5 w-8 h-8 rounded-full bg-black/70 text-white flex items-center justify-center hover:bg-black"
                            aria-label={`Remove ${m.file.name}`}>
                            <X className="w-3.5 h-3.5" />
                          </button>
                          {progress && <span className="absolute left-0 bottom-0 h-1 bg-amber-400" style={{ width: `${(progress[i] ?? 0) * 100}%` }} />}
                        </div>
                        <p className="text-[13px] font-semibold text-neutral-200 truncate">{m.file.name}</p>
                      </li>
                    ))}
                    <li>
                      <label className="h-full min-h-[180px] rounded-2xl border-[1.5px] border-dashed border-neutral-700 hover:border-amber-500/50 flex flex-col items-center justify-center gap-1.5 text-[13px] font-semibold text-neutral-400 cursor-pointer">
                        <Plus className="w-5 h-5" /> Add more
                        <input type="file" multiple accept={MEDIA_TYPES.join(',')} className="sr-only" onChange={(e) => addMedia(e.target.files)} />
                      </label>
                    </li>
                  </ul>
                  <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5 text-sm">
                    <span className={`font-semibold ${overFootage || overFiles ? 'text-rose-300' : 'text-emerald-300'}`}>
                      {fileCount} file{fileCount === 1 ? '' : 's'} · {formatSeconds(rawSeconds)} of footage
                    </span>
                    {limits && (
                      <span className="flex-[1_1_120px] h-1.5 rounded-full bg-neutral-800 overflow-hidden" aria-hidden="true">
                        <span className={`block h-full ${overFootage ? 'bg-rose-400' : 'bg-emerald-400'}`} style={{ width: `${used * 100}%` }} />
                      </span>
                    )}
                    <span className="text-neutral-400">
                      {overFootage ? 'Too much footage for your plan' : overFiles ? `Your plan takes up to ${limits?.max_files} files`
                        : limits ? `${Math.round(used * 100)}% of your plan's limit` : ''}
                    </span>
                  </div>
                </>
              )}
            </div>

            {/* How to edit it */}
            <div className="flex-[1_1_420px] min-w-0 flex flex-col gap-2.5">
              <div className={`${card} p-5 sm:p-6 flex flex-col gap-3 flex-1`}>
                <div className="flex items-center gap-3">
                  <label htmlFor="footage-intent" className="text-[17px] font-semibold text-white">How should it be edited?</label>
                  <span className="ml-auto text-xs text-neutral-500 tabular-nums">{intent.length}/{INTENT_MAX}</span>
                </div>
                <textarea id="footage-intent" value={intent} onChange={(e) => setIntent(e.target.value)} rows={4} maxLength={INTENT_MAX}
                  placeholder="e.g. A 30-second travel reel. Open on the cliff jump, keep it fast and upbeat, captions on everything I say."
                  className="w-full resize-y bg-transparent border-0 p-0 text-lg leading-relaxed text-white placeholder:text-neutral-600 focus:outline-none" />
                <div className="flex flex-wrap gap-2">
                  {BRIEF_IDEAS.map((idea) => (
                    <button key={idea} type="button" onClick={() => addIdea(idea)}
                      className="h-9 px-3 rounded-full border border-neutral-800 bg-neutral-900 text-[13px] text-neutral-300 hover:text-white hover:border-neutral-700">
                      + {idea}
                    </button>
                  ))}
                </div>
              </div>

              <div className={`${card} p-5 sm:px-6 flex flex-col gap-3`}>
                <p className="text-[15px] font-semibold text-white">
                  Edit it like this <span className="font-normal text-[13px] text-neutral-400">· optional: a reel whose style you want</span>
                </p>
                {reference ? (
                  <div className="flex items-center gap-3.5 p-2.5 rounded-2xl bg-amber-500/[0.07] border border-amber-500/35">
                    <span className="relative w-11 aspect-[9/16] rounded-lg overflow-hidden bg-neutral-900 shrink-0 flex items-center justify-center">
                      {reference.kind === 'file' ? <Thumb item={reference} /> : <Link2 className="w-4 h-4 text-amber-300" />}
                      {referenceProgress !== null && <span className="absolute left-0 bottom-0 h-1 bg-amber-400" style={{ width: `${referenceProgress * 100}%` }} />}
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block text-sm font-semibold text-white truncate">
                        {reference.kind === 'file' ? `${reference.file.name}${reference.durationS ? ` · ${formatSeconds(reference.durationS)}` : ''}` : reference.url}
                      </span>
                      <span className="block text-[13px] text-amber-100/70">We copy its pacing, captions, music energy and look. Nothing of it goes in your reel.</span>
                    </span>
                    <button type="button" disabled={busy} onClick={removeReference} aria-label="Remove the reference reel"
                      className="w-11 h-11 rounded-xl text-neutral-400 hover:text-white flex items-center justify-center shrink-0">
                      <X className="w-4 h-4" />
                    </button>
                  </div>
                ) : linkDraft !== null ? (
                  <div className="flex gap-2">
                    <label htmlFor="reference-link" className="sr-only">Reference reel link</label>
                    <input id="reference-link" autoFocus value={linkDraft} onChange={(e) => setLinkDraft(e.target.value)} maxLength={1000}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') {
                          e.preventDefault();
                          applyLink();
                        }
                      }}
                      placeholder="https://youtube.com/shorts/…" className={`${field} flex-1 min-w-0`} />
                    <button type="button" onClick={applyLink} className="h-11 px-4 rounded-xl bg-neutral-800 hover:bg-neutral-700 text-sm font-semibold text-white">Use</button>
                    <button type="button" onClick={() => setLinkDraft(null)} aria-label="Cancel" className="w-11 h-11 rounded-xl text-neutral-400 hover:text-white flex items-center justify-center">
                      <X className="w-4 h-4" />
                    </button>
                  </div>
                ) : (
                  <div className="flex flex-wrap gap-2">
                    <button type="button" onClick={() => setLinkDraft('')} className={ghost}><Link2 className="w-4 h-4" /> Paste a YouTube link</button>
                    <label className={`${ghost} cursor-pointer`}>
                      <Upload className="w-4 h-4" /> Upload a reference
                      <input type="file" accept={EDIT_VIDEO_TYPES.join(',')} className="sr-only" onChange={(e) => addReference(e.target.files?.[0])} />
                    </label>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Settings */}
          <div className={`${card} p-5 sm:px-6 flex flex-wrap items-end gap-x-8 gap-y-4`}>
            <div className="w-full space-y-2">
              <span className={label}>How should we edit?</span>
              <div role="radiogroup" aria-label="How should we edit?" className="grid gap-2 sm:grid-cols-2">
                {([
                  ['premium', 'Premium AI edit', 'Cleans your footage, directs the story, designs the graphics and music, reviews its own work. Pro.'],
                  ['classic', 'Plan, then render', 'See the plan first, change it, then render it yourself.'],
                ] as [EditEngine, string, string][]).map(([value, name, about]) => {
                  const locked = value === 'premium' && !isPro;
                  const on = chosenEngine === value;
                  return (
                    <button key={value} type="button" role="radio" aria-checked={on} disabled={locked || busy} onClick={() => setEngine(value)}
                      className={`text-left rounded-2xl border p-3.5 transition-colors disabled:opacity-50 ${on ? 'border-amber-500/60 bg-amber-500/[0.08]' : 'border-neutral-800 hover:border-neutral-600'}`}>
                      <span className="flex items-center gap-2 text-[15px] font-semibold text-white">
                        {value === 'premium' && <Sparkles className="w-4 h-4 text-amber-300" />} {name}{locked ? ' · Pro' : ''}
                      </span>
                      <span className="block mt-1 text-[13px] text-neutral-400">{about}</span>
                    </button>
                  );
                })}
              </div>
            </div>
            <div className="space-y-2">
              <span className={label}>Length</span>
              <div role="group" aria-label="Reel length" className="flex flex-wrap gap-1.5">
                {TARGET_OPTIONS.map((seconds) => {
                  const locked = limits ? seconds > limits.max_output_seconds : false;
                  return (
                    <button key={seconds} type="button" disabled={locked} onClick={() => setTarget(seconds)} aria-pressed={target === seconds} className={pill(target === seconds)}>
                      {seconds === 0 ? 'Auto' : `${seconds} s`}{locked ? ' · Pro' : ''}
                    </button>
                  );
                })}
              </div>
            </div>
            <div className="space-y-2">
              <label htmlFor="footage-language" className={label}>Language</label>
              <select id="footage-language" value={language} onChange={(e) => setLanguage(e.target.value)} className={field}>
                {LANGUAGES.map(([value, name]) => <option key={value} value={value}>{name}</option>)}
              </select>
            </div>
            <div className="space-y-2">
              <label htmlFor="footage-captions" className={label}>Captions</label>
              <select id="footage-captions" value={captionStyle} onChange={(e) => setCaptionStyle(e.target.value)} className={field}>
                {captionOptions.map((style) => <option key={style.id} value={style.id}>{style.name}</option>)}
              </select>
            </div>
            <div className="space-y-2 flex-[1_1_200px] min-w-0">
              <label htmlFor="footage-title" className={label}>Title <span className="font-normal text-neutral-500">· optional</span></label>
              <input id="footage-title" value={title} onChange={(e) => setTitle(e.target.value)} maxLength={300} placeholder="We'll name it from your footage" className={`${field} w-full`} />
            </div>
            <div className="w-full flex flex-wrap items-center gap-2">
              <button type="button" onClick={() => setShowScript((v) => !v)} aria-expanded={showScript} aria-controls="footage-script"
                className={`${ghost} ${showScript || script ? 'border-amber-500/50 text-amber-200' : ''}`}>
                <ScrollText className="w-4 h-4" /> {script ? 'Script added' : 'Add a script'}
              </button>
              <button type="button" onClick={() => setShowVoice((v) => !v)} aria-expanded={showVoice} aria-controls="footage-voice"
                className={`${ghost} ${showVoice || voice ? 'border-amber-500/50 text-amber-200' : ''}`}>
                <Mic className="w-4 h-4" /> {voice ? 'Voiceover added' : 'Add a voiceover'}
              </button>
              <label className={`ml-auto flex items-center gap-3 h-11 cursor-pointer ${chosenEngine === 'premium' ? 'hidden' : ''}`}>
                <input type="checkbox" checked={autopilot} onChange={(e) => setAutopilot(e.target.checked)} className="peer sr-only" />
                <span className="relative w-10 h-6 rounded-full bg-neutral-700 peer-checked:bg-amber-500 peer-focus-visible:ring-2 peer-focus-visible:ring-amber-400 transition-colors after:absolute after:top-1 after:left-1 after:w-4 after:h-4 after:rounded-full after:bg-white after:transition-transform peer-checked:after:translate-x-4" />
                <span className="text-sm text-neutral-300">Render as soon as the plan is ready</span>
              </label>
            </div>
            {showScript && (
              <div id="footage-script" className="w-full grid gap-3 sm:grid-cols-[minmax(0,1fr)_240px]">
                <label htmlFor="footage-script-text" className="sr-only">Script</label>
                <textarea id="footage-script-text" value={script} onChange={(e) => setScript(e.target.value)} rows={5} maxLength={6000}
                  placeholder="Paste what you say in the video, a voiceover to read, or notes. We follow it exactly when it's what you said."
                  className={`${field} h-auto py-3 resize-y leading-relaxed`} />
                <div className="space-y-2">
                  <label htmlFor="footage-script-mode" className={label}>How should we use it?</label>
                  <select id="footage-script-mode" value={scriptMode} onChange={(e) => setScriptMode(e.target.value as EditScriptMode)} className={`${field} w-full`}>
                    {SCRIPT_MODE_OPTIONS.map(([value, name]) => <option key={value} value={value}>{name}</option>)}
                  </select>
                </div>
              </div>
            )}
            {showVoice && (
              <label id="footage-voice" className="w-full flex items-center gap-3.5 p-3.5 rounded-2xl border-2 border-dashed border-neutral-800 hover:border-amber-500/50 cursor-pointer transition-colors">
                <span className="w-11 h-11 rounded-xl bg-amber-500/10 text-amber-400 flex items-center justify-center shrink-0"><Mic className="w-4 h-4" /></span>
                <span className="min-w-0 flex-1">
                  <span className="block text-sm font-semibold text-white truncate">{voice ? voice.name : 'Add a voiceover recording'}</span>
                  <span className="text-[13px] text-neutral-400">It becomes the spine of the reel; your clips illustrate it</span>
                </span>
                {voice && (
                  <button type="button" onClick={(e) => { e.preventDefault(); setVoice(null); }} className="w-11 h-11 rounded-xl text-neutral-400 hover:text-white flex items-center justify-center" aria-label="Remove voiceover">
                    <X className="w-4 h-4" />
                  </button>
                )}
                <input type="file" accept={EDIT_AUDIO_TYPES.join(',')} className="sr-only" onChange={(e) => setVoice(e.target.files?.[0] ?? null)} />
              </label>
            )}
          </div>

          {/* Model and go */}
          <div className={`${card} p-5 sm:px-6 flex flex-wrap items-end gap-x-8 gap-y-5`}>
            <ReelModelPicker disabled={busy} />
            <div className="ml-auto flex flex-col items-end gap-2">
              <button type="submit" disabled={!canSubmit}
                className="inline-flex items-center gap-2.5 h-14 px-7 rounded-2xl bg-amber-500 hover:bg-amber-400 text-neutral-950 text-[17px] font-bold disabled:opacity-40 transition-colors">
                {busy ? <Loader2 className="w-5 h-5 animate-spin" /> : <Sparkles className="w-5 h-5" />}
                {busy ? (progress && uploaded < 1 ? `Uploading ${Math.round(uploaded * 100)}%` : 'Starting…') : chosenEngine === 'premium' ? 'Edit my reel' : 'Plan my reel'}
              </button>
              <span className="text-[13px] text-neutral-400 flex items-center gap-1.5">
                {media.length === 0 ? <><Film className="w-3.5 h-3.5" /> Add at least one video or photo</> : (
                  chosenEngine === 'premium'
                    ? <>About {estimate} credits when it starts, refunded if it fails{entitlements ? ` · you have ${entitlements.credit_minutes_remaining}` : ''}</>
                    : <>Free to plan · about {estimate} credits when you render{entitlements ? ` · you have ${entitlements.credit_minutes_remaining}` : ''}</>
                )}
              </span>
            </div>
            {error && <p role="alert" className="w-full text-sm text-rose-300">{error}</p>}
          </div>
        </form>
      </section>

      <section aria-labelledby="starters" className="space-y-4">
        <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
          <h2 id="starters" className="font-syne text-2xl font-bold text-white">Not sure what to ask for?</h2>
          <p className="text-[15px] text-neutral-400">Tap one to fill in the brief. The AI still picks the format from your footage.</p>
        </div>
        <div className="grid grid-cols-[repeat(auto-fill,minmax(170px,1fr))] gap-3.5">
          {BRIEF_STARTERS.map((s) => (
            <button key={s.title} type="button" onClick={() => setIntent(s.brief)} aria-pressed={intent === s.brief}
              className={`text-left rounded-[20px] overflow-hidden bg-neutral-900 border-2 transition-colors ${intent === s.brief ? 'border-amber-500' : 'border-neutral-800 hover:border-neutral-700'}`}>
              <span className="flex aspect-[4/5] items-center justify-center px-3 bg-[radial-gradient(circle_at_50%_35%,rgba(245,158,11,0.16),transparent_70%)]">
                <span className="font-syne text-lg font-extrabold uppercase leading-none text-center text-white">{s.sample}</span>
              </span>
              <span className="block px-3.5 pt-3 pb-3.5">
                <span className="block text-[15px] font-semibold text-white">{s.title}</span>
                <span className="block text-[13px] text-neutral-400 mt-0.5">{s.hint}</span>
              </span>
            </button>
          ))}
        </div>
      </section>
    </>
  );
}
