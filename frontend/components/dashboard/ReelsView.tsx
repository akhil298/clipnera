'use client';

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Clapperboard, Download, Film, Image as ImageIcon, Loader2, Mic, RotateCcw, Sparkles, Type, Video, X } from 'lucide-react';
import {
  REEL_AUDIO_TYPES,
  REEL_IMAGE_TYPES,
  ReelAssetType,
  ReelResponse,
  ReelScene,
  ReelSceneUpdate,
  ReelStatus,
  ReelStyle,
  ReelSummary,
  AI_SHOT_CREDITS,
  EditSummary,
  editsApi,
  reelsApi,
} from '@/lib/api';
import { useEntitlements } from '@/hooks/useEntitlements';
import { useFeatureFlags } from '@/hooks/useFeatureFlags';
import { formatRelativeTime } from '@/lib/utils/dates';
import { PageHeader } from '@/components/ui/PageHeader';
import { StatusPill, type StatusTone } from '@/components/ui/StatusPill';
import { EDIT_STATUS } from '@/lib/utils/footageReels';
import { FootageReelBoard } from './FootageReelBoard';
import { COMPOSER, FootageReelForm } from './FootageReelForm';

const LANGUAGES = [
  ['en', 'English'], ['hi', 'Hindi'], ['te', 'Telugu'], ['hinglish', 'Hinglish'], ['tenglish', 'Tenglish'],
] as const;
const STYLES: [ReelStyle, string][] = [['clean', 'Clean'], ['bold', 'Bold'], ['neon', 'Neon'], ['warm', 'Warm']];
const BUSY: ReelResponse['status'][] = ['planning', 'rendering'];
const field = 'w-full h-11 px-3.5 rounded-xl bg-neutral-900 border border-neutral-800 text-sm text-white placeholder:text-neutral-600 focus:outline-none focus:border-amber-400';
const label = 'block text-[13px] font-semibold text-neutral-400';

const REEL_STATUS: Record<ReelStatus, { tone: StatusTone; label: string }> = {
  draft: { tone: 'neutral', label: 'Draft' },
  planning: { tone: 'processing', label: 'Planning' },
  ready: { tone: 'scheduled', label: 'Ready to render' },
  rendering: { tone: 'processing', label: 'Rendering' },
  done: { tone: 'ready', label: 'Done' },
  failed: { tone: 'failed', label: 'Failed' },
};

const formatSeconds = (s: number) => `${Math.floor(s / 60)}:${String(Math.round(s % 60)).padStart(2, '0')}`;

const card = 'rounded-[22px] border border-neutral-800 bg-neutral-950';
const pill = (on: boolean) =>
  `h-11 px-4 rounded-full border text-sm font-semibold transition-colors inline-flex items-center gap-1.5 ${
    on ? 'border-amber-500 bg-amber-500/15 text-amber-200' : 'border-neutral-800 bg-neutral-900 text-neutral-300 hover:text-white'
  }`;

function NewReelForm({ onCreated }: { onCreated: (id: string) => void }) {
  const { entitlements } = useEntitlements();
  const maxImages = entitlements?.pro_ai_provider ? 30 : 5;
  const [title, setTitle] = useState('');
  const [mode, setMode] = useState<'topic' | 'script'>('topic');
  const [text, setText] = useState('');
  const [language, setLanguage] = useState('en');
  const [style, setStyle] = useState<ReelStyle>('bold');
  const [images, setImages] = useState<File[]>([]);
  const [voice, setVoice] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Thumbnails of the chosen images; revoked when the selection changes.
  const previews = useMemo(() => images.map((file) => URL.createObjectURL(file)), [images]);
  useEffect(() => () => previews.forEach((url) => URL.revokeObjectURL(url)), [previews]);

  const addImages = (files: FileList | File[] | null) => {
    const picked = Array.from(files || []).filter((f) => REEL_IMAGE_TYPES.includes(f.type as ReelAssetType));
    setImages((prev) => [...prev, ...picked].slice(0, maxImages));
  };

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const reel = await reelsApi.create({
        title: title.trim() || 'Untitled reel',
        topic: mode === 'topic' ? text.trim() : null,
        script: mode === 'script' ? text.trim() : null,
        language,
        style,
      });
      const files = [...images, ...(voice ? [voice] : [])];
      if (files.length) await reelsApi.uploadAssets(reel.id, files);
      await reelsApi.plan(reel.id);
      onCreated(reel.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not create the reel');
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={submit} className="flex flex-col gap-2.5" aria-labelledby="new-reel-title">
      <h2 id="new-reel-title" className="sr-only">New reel from photos</h2>
      <div className="flex flex-wrap gap-2.5">
        <div className={`${card} flex-[1_1_420px] min-w-0 p-5 sm:p-6 flex flex-col gap-3`}>
          <label htmlFor="reel-text" className="text-[17px] font-semibold text-white">
            {mode === 'topic' ? 'What is the reel about?' : 'Your voiceover script'}
          </label>
          <textarea id="reel-text" value={text} onChange={(e) => setText(e.target.value)} rows={mode === 'script' ? 7 : 4} required
            placeholder={mode === 'topic' ? 'e.g. How I saved ₹10,000 by making coffee at home' : 'Paste the voiceover script'}
            className="w-full resize-y bg-transparent border-0 p-0 text-lg leading-relaxed text-white placeholder:text-neutral-600 focus:outline-none" />
          <div role="group" aria-label="Script source" className="flex flex-wrap gap-2">
            {(['topic', 'script'] as const).map((m) => (
              <button key={m} type="button" onClick={() => setMode(m)} aria-pressed={mode === m} className={pill(mode === m)}>
                {m === 'topic' ? <><Sparkles className="w-4 h-4" /> Write it for me</> : <><Type className="w-4 h-4" /> My own script</>}
              </button>
            ))}
          </div>
        </div>
        <div className="flex-[1_1_420px] min-w-0 flex flex-col gap-2.5">
          <label
            className="flex-1 rounded-[22px] border-2 border-dashed border-neutral-800 hover:border-amber-500/40 bg-neutral-950 p-5 sm:p-6 flex flex-col gap-4 cursor-pointer transition-colors"
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => {
              e.preventDefault();
              addImages(e.dataTransfer.files);
            }}
          >
            <span className="flex items-center gap-3.5">
              <span className="w-12 h-12 rounded-2xl bg-amber-500/10 text-amber-400 flex items-center justify-center shrink-0"><ImageIcon className="w-5 h-5" /></span>
              <span>
                <span className="block text-[17px] font-semibold text-white">Photos <span className="font-normal text-sm text-neutral-400">· {images.length} of {maxImages}</span></span>
                <span className="block text-sm text-neutral-400">JPG, PNG or WebP · drop them here or tap to choose</span>
              </span>
            </span>
            <input type="file" multiple accept={REEL_IMAGE_TYPES.join(',')} className="sr-only" onChange={(e) => addImages(e.target.files)} />
            {images.length > 0 && (
              <span className="grid grid-cols-[repeat(auto-fill,minmax(72px,1fr))] gap-2" aria-label="Chosen images">
                {previews.map((url, i) => (
                  <span key={url} className="relative aspect-[3/4] rounded-xl overflow-hidden border border-neutral-800">
                    <img src={url} alt="" className="w-full h-full object-cover" />
                    <button type="button" onClick={(e) => { e.preventDefault(); setImages((prev) => prev.filter((_, j) => j !== i)); }}
                      className="absolute top-1 right-1 w-7 h-7 rounded-full bg-black/70 text-white flex items-center justify-center"
                      aria-label={`Remove image ${i + 1}`}>
                      <X className="w-3.5 h-3.5" />
                    </button>
                  </span>
                ))}
              </span>
            )}
          </label>
          <label className={`${card} flex items-center gap-3.5 p-4 sm:px-5 cursor-pointer hover:border-amber-500/40 transition-colors`}>
            <span className="w-11 h-11 rounded-xl bg-amber-500/10 text-amber-400 flex items-center justify-center shrink-0"><Mic className="w-4 h-4" /></span>
            <span className="min-w-0 flex-1">
              <span className="block text-[15px] font-semibold text-white truncate">{voice ? voice.name : 'Add your voiceover'} <span className="font-normal text-[13px] text-neutral-500">· optional</span></span>
              <span className="text-[13px] text-neutral-400">Without one, an AI voice reads the script (or captions only)</span>
            </span>
            {voice && (
              <button type="button" onClick={(e) => { e.preventDefault(); setVoice(null); }} className="w-11 h-11 rounded-xl text-neutral-400 hover:text-white flex items-center justify-center" aria-label="Remove voiceover">
                <X className="w-4 h-4" />
              </button>
            )}
            <input type="file" accept={REEL_AUDIO_TYPES.join(',')} className="sr-only" onChange={(e) => setVoice(e.target.files?.[0] ?? null)} />
          </label>
        </div>
      </div>

      <div className={`${card} p-5 sm:px-6 flex flex-wrap items-end gap-x-6 gap-y-4`}>
        <div className="space-y-2 flex-[1_1_220px] min-w-0">
          <label htmlFor="reel-title" className={label}>Title <span className="font-normal text-neutral-500">· optional</span></label>
          <input id="reel-title" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. Morning routine explainer" className={field} />
        </div>
        <div className="space-y-2">
          <label htmlFor="reel-language" className={label}>Language</label>
          <select id="reel-language" value={language} onChange={(e) => setLanguage(e.target.value)} className={field}>
            {LANGUAGES.map(([value, name]) => <option key={value} value={value}>{name}</option>)}
          </select>
        </div>
        <div className="space-y-2">
          <span className={label}>Style</span>
          <div role="group" aria-label="Style" className="flex flex-wrap gap-1.5">
            {STYLES.map(([value, name]) => (
              <button key={value} type="button" onClick={() => setStyle(value)} aria-pressed={style === value} className={pill(style === value)}>{name}</button>
            ))}
          </div>
        </div>
        <div className="ml-auto flex flex-col items-end gap-2">
          <button type="submit" disabled={busy || !text.trim()}
            className="inline-flex items-center gap-2.5 h-14 px-7 rounded-2xl bg-amber-500 hover:bg-amber-400 text-neutral-950 text-[17px] font-bold disabled:opacity-40 transition-colors">
            {busy ? <Loader2 className="w-5 h-5 animate-spin" /> : <Clapperboard className="w-5 h-5" />} {busy ? 'Building…' : 'Build scene board'}
          </button>
          {!text.trim() && !busy && (
            <span className="text-[13px] text-neutral-400">{mode === 'topic' ? 'Describe the reel to continue.' : 'Paste a script to continue.'}</span>
          )}
        </div>
        {error && <p role="alert" className="w-full text-sm text-rose-300">{error}</p>}
      </div>
    </form>
  );
}

const KIND_OPTIONS = [
  ['image', ImageIcon, 'Image'],
  ['broll', Video, 'B-roll'],
  ['text', Type, 'Text'],
] as const;

function SceneCard({ reel, scene, number, isPro, aiShots, onChange, onGenerate }: {
  reel: ReelResponse; scene: ReelScene; number: number; isPro: boolean; aiShots: boolean;
  onChange: (u: ReelSceneUpdate) => void; onGenerate: () => void;
}) {
  const [headline, setHeadline] = useState(scene.headline || scene.text.split(' ').slice(0, 5).join(' '));
  const preview = scene.kind === 'image' ? scene.image_url : scene.kind === 'broll' ? scene.footage?.thumb_url : null;
  return (
    <article className="rounded-2xl bg-neutral-900/80 border border-neutral-800 overflow-hidden flex flex-col" aria-label={`Scene ${number}`}>
      <div className="relative aspect-[9/16] bg-neutral-950 flex items-center justify-center">
        {preview ? <img src={preview} alt="" className="w-full h-full object-cover" /> : (
          <span className="px-3 text-center text-lg font-black text-amber-300 uppercase leading-tight">{scene.headline || scene.text}</span>
        )}
        <span className="absolute top-2 left-2 px-1.5 py-0.5 rounded-md bg-black/70 text-[10px] font-bold text-white">{number}</span>
        <span className="absolute top-2 right-2 px-1.5 py-0.5 rounded-md bg-black/70 font-mono text-[10px] text-white">
          {scene.start.toFixed(1)}–{scene.end.toFixed(1)}s
        </span>
        {scene.generating && (
          <div className="absolute inset-0 bg-black/60 flex items-center justify-center gap-2 text-xs text-amber-300">
            <Loader2 className="w-4 h-4 animate-spin" /> Generating AI shot…
          </div>
        )}
      </div>
      <div className="p-3 space-y-2.5 flex-1 flex flex-col">
        <p className="text-sm text-neutral-200 line-clamp-3">“{scene.text}”</p>
        <div className="flex gap-1" aria-label={`Scene shows: ${scene.kind}`}>
          {KIND_OPTIONS.map(([kind, Icon, name]) => (
            <span key={kind} className={`flex-1 h-6 rounded-md flex items-center justify-center gap-1 text-[10px] font-semibold ${scene.kind === kind ? 'bg-amber-500/15 text-amber-300' : 'text-neutral-600'}`}>
              <Icon className="w-3 h-3" /> {name}
            </span>
          ))}
        </div>
        {reel.image_urls.length > 0 && (
          <div className="flex gap-1.5 overflow-x-auto [scrollbar-width:none]" role="group" aria-label="Use an image">
            {reel.image_urls.map((url, i) => (
              <button key={url} type="button" onClick={() => onChange({ kind: 'image', image_index: i })}
                aria-pressed={scene.kind === 'image' && scene.image_index === i} aria-label={`Use image ${i + 1}`}
                className={`w-12 aspect-[3/4] rounded-lg overflow-hidden border-2 shrink-0 ${scene.kind === 'image' && scene.image_index === i ? 'border-amber-400' : 'border-transparent opacity-70 hover:opacity-100'}`}>
                <img src={url} alt="" className="w-full h-full object-cover" />
              </button>
            ))}
          </div>
        )}
        {scene.alternates.length > 0 && (
          <div className="flex gap-1.5 overflow-x-auto [scrollbar-width:none]" role="group" aria-label="Use B-roll footage">
            {[...(scene.footage ? [scene.footage] : []), ...scene.alternates].map((alt) => (
              <button key={alt.id} type="button" title={alt.attribution_text ?? alt.title} onClick={() => onChange({ kind: 'broll', asset_id: alt.id })}
                aria-pressed={scene.kind === 'broll' && scene.footage?.id === alt.id} aria-label={`Use footage: ${alt.title}`}
                className={`w-12 aspect-[9/16] rounded-lg overflow-hidden border-2 shrink-0 bg-neutral-800 ${scene.kind === 'broll' && scene.footage?.id === alt.id ? 'border-amber-400' : 'border-transparent opacity-70 hover:opacity-100'}`}>
                {alt.thumb_url && <img src={alt.thumb_url} alt="" className="w-full h-full object-cover" />}
              </button>
            ))}
          </div>
        )}
        <form className="flex gap-1.5" onSubmit={(e) => { e.preventDefault(); onChange({ kind: 'text', headline }); }}>
          <label htmlFor={`scene-headline-${scene.index}`} className="sr-only">Headline for scene {number}</label>
          <input id={`scene-headline-${scene.index}`} value={headline} onChange={(e) => setHeadline(e.target.value)} maxLength={60}
            className="flex-1 min-w-0 h-10 px-3 rounded-xl bg-neutral-950 border border-neutral-800 text-sm text-white focus:outline-none focus:border-amber-400" />
          <button type="submit" className="h-10 px-3 rounded-xl border border-neutral-700 text-[13px] font-semibold text-neutral-200 hover:text-white hover:bg-neutral-800">
            Use text
          </button>
        </form>
        {aiShots && (
          <button type="button" onClick={onGenerate} disabled={!isPro || scene.generating}
            title={isPro ? 'Generate a new shot for this scene with AI' : 'AI shots are a Pro feature'}
            className="mt-auto w-full h-10 rounded-xl border border-violet-500/30 text-[13px] font-semibold text-violet-300 hover:bg-violet-500/10 disabled:opacity-40 flex items-center justify-center gap-1.5">
            <Sparkles className="w-3.5 h-3.5" /> AI shot · {AI_SHOT_CREDITS} credits{isPro ? '' : ' (Pro)'}
          </button>
        )}
      </div>
    </article>
  );
}

function ReelBoard({ reelId, onBack }: { reelId: string; onBack: () => void }) {
  const { entitlements } = useEntitlements();
  const { flags } = useFeatureFlags();
  const [reel, setReel] = useState<ReelResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => reelsApi.get(reelId).then(setReel).catch((e: Error) => setError(e.message)), [reelId]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (!reel || !(BUSY.includes(reel.status) || reel.scenes.some((s) => s.generating))) return;
    const id = setInterval(load, 2000);
    return () => clearInterval(id);
  }, [reel, load]);

  const act = async (call: () => Promise<ReelResponse>) => {
    setError(null);
    try {
      setReel(await call());
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong');
    }
  };

  if (!reel) {
    return (
      <div className="space-y-4">
        <PageHeader back={{ label: 'Reels', onClick: onBack }} title="Loading reel…" />
        {error ? <p role="alert" className="text-xs text-rose-300">{error}</p> : <Loader2 className="w-6 h-6 text-amber-400 animate-spin" />}
      </div>
    );
  }

  const status = REEL_STATUS[reel.status];
  const canRender = reel.status === 'ready' || reel.status === 'done';
  return (
    <div className="space-y-5">
      <PageHeader
        back={{ label: 'Reels', onClick: onBack }}
        title={reel.title}
        eyebrow={<StatusPill tone={status.tone}>{status.label}</StatusPill>}
        description={
          <>
            {reel.status === 'planning' && 'Writing, voicing and laying out the scenes…'}
            {reel.status === 'ready' && `${reel.scenes.length} scenes · ${formatSeconds(reel.duration_s)} · ${reel.style} style${reel.has_voiceover ? ' · your voiceover' : ''}. Pick a thumbnail to change a scene.`}
            {reel.status === 'rendering' && 'Rendering your reel. This page updates by itself.'}
            {reel.status === 'done' && `Rendered · ${reel.credits_charged} credits used`}
            {reel.status === 'failed' && (reel.error ?? 'Something went wrong while building this reel.')}
          </>
        }
        actions={
          <>
            {reel.status === 'done' && reel.output_url && (
              <a href={reel.output_url} download className="inline-flex items-center gap-2 h-9 px-3.5 rounded-xl border border-neutral-700 bg-neutral-900 hover:bg-neutral-800 text-[13px] font-semibold text-white">
                <Download className="w-4 h-4" /> Download
              </a>
            )}
            {canRender && (
              <button type="button" onClick={() => act(() => reelsApi.render(reel.id))}
                className="inline-flex items-center gap-2 h-9 px-3.5 rounded-xl bg-amber-500 hover:bg-amber-400 text-neutral-950 text-[13px] font-bold shadow-md shadow-amber-500/20">
                <Clapperboard className="w-4 h-4" />
                {reel.status === 'done' ? 'Render again' : 'Render'} · {reel.credits_estimate} credits
              </button>
            )}
            {reel.status === 'failed' && (
              <button type="button" onClick={() => act(() => reelsApi.plan(reel.id))}
                className="inline-flex items-center gap-2 h-9 px-3.5 rounded-xl border border-neutral-700 text-[13px] font-semibold text-white hover:bg-neutral-800">
                <RotateCcw className="w-4 h-4" /> Try again
              </button>
            )}
          </>
        }
      />

      {error && <p role="alert" className="text-xs text-rose-300">{error}</p>}
      {BUSY.includes(reel.status) && (
        <div className="flex items-center gap-3 rounded-2xl border border-amber-500/25 bg-neutral-900/80 p-4 text-sm text-neutral-300">
          <Loader2 className="w-5 h-5 text-amber-400 animate-spin" />
          {reel.status === 'planning' ? 'Planning scenes…' : 'Rendering…'}
        </div>
      )}

      {reel.status === 'done' && reel.output_url && (
        <video src={reel.output_url} controls playsInline className="w-full max-w-[280px] aspect-[9/16] rounded-2xl bg-black border border-neutral-800" />
      )}

      {canRender && reel.scenes.length > 0 && (
        <>
          {/* How the scenes add up to the reel */}
          <div className="flex h-8 rounded-lg overflow-hidden border border-neutral-800" aria-label="Scene timeline">
            {reel.scenes.map((scene, i) => (
              <div key={scene.index}
                style={{ flexGrow: Math.max(0.5, scene.end - scene.start) }}
                className={`min-w-0 flex items-center px-2 text-[10.5px] font-semibold truncate ${i ? 'border-l border-neutral-950' : ''} ${
                  scene.kind === 'text' ? 'bg-amber-500/15 text-amber-200' : scene.kind === 'broll' ? 'bg-sky-500/15 text-sky-200' : 'bg-neutral-800 text-neutral-200'
                }`}
                title={`Scene ${i + 1} · ${scene.kind} · ${(scene.end - scene.start).toFixed(1)}s`}>
                {i + 1}{scene.headline ? ` · ${scene.headline}` : ''}
              </div>
            ))}
          </div>
          <div className="grid grid-cols-[repeat(auto-fill,minmax(220px,1fr))] gap-4">
            {reel.scenes.map((scene, i) => (
              <SceneCard key={`${scene.index}:${scene.kind}:${scene.image_index}:${scene.footage?.id}:${scene.headline}`} reel={reel} scene={scene}
                number={i + 1}
                isPro={Boolean(entitlements?.pro_ai_provider)}
                aiShots={flags['broll_studio.ai_shots']}
                onChange={(update) => act(() => reelsApi.updateScene(reel.id, scene.index, update))}
                onGenerate={() => act(() => reelsApi.generateScene(reel.id, scene.index))} />
            ))}
          </div>
        </>
      )}
    </div>
  );
}

type ReelCard = {
  id: string; title: string; kind: 'footage' | 'images'; duration_s: number; created_at: string;
  cover_url: string | null; status: { tone: StatusTone; label: string }; href: string;
};

const imageCard = (r: ReelSummary): ReelCard => ({
  ...r, kind: 'images', status: REEL_STATUS[r.status], href: `/dashboard/reels/${r.id}`,
});
const footageCard = (e: EditSummary): ReelCard => ({
  ...e, kind: 'footage', cover_url: null, status: EDIT_STATUS[e.status], href: `/dashboard/reels/footage/${e.id}`,
});

const FILTERS = [
  ['all', 'All'], ['active', 'In progress'], ['done', 'Done'],
] as const;
type Filter = typeof FILTERS[number][0];
const matches = (r: ReelCard, filter: Filter) =>
  filter === 'all' || (filter === 'done' ? r.status.tone === 'ready' : r.status.tone !== 'ready' && r.status.tone !== 'failed');

export function ReelsView({ reelId, editId }: { reelId?: string; editId?: string }) {
  const router = useRouter();
  const { flags } = useFeatureFlags();
  const footage = flags['broll_studio.reels.footage'];
  const [mode, setMode] = useState<'footage' | 'images'>('footage');
  const [reels, setReels] = useState<ReelCard[] | null>(null);
  const [filter, setFilter] = useState<Filter>('all');

  useEffect(() => {
    if (reelId || editId) return;
    Promise.all([
      reelsApi.list().then((list) => list.map(imageCard)).catch(() => []),
      footage ? editsApi.list().then((list) => list.map(footageCard)).catch(() => []) : Promise.resolve([] as ReelCard[]),
    ]).then(([images, edits]) => setReels([...images, ...edits].sort((a, b) => b.created_at.localeCompare(a.created_at))));
  }, [reelId, editId, footage]);

  if (editId) return <FootageReelBoard editId={editId} onBack={() => router.push('/dashboard/reels')} />;
  if (reelId) return <ReelBoard reelId={reelId} onBack={() => router.push('/dashboard/reels')} />;
  const showFootage = footage && mode === 'footage';
  const shown = reels?.filter((r) => matches(r, filter)) ?? [];
  const tabs = footage && (
    <div role="group" aria-label="How to make the reel" className="inline-flex flex-wrap gap-1 p-1 rounded-[18px] bg-neutral-950">
      {([['footage', Film, 'Edit my footage'], ['images', ImageIcon, 'Photos + script']] as const).map(([m, Icon, name]) => (
        <button key={m} type="button" onClick={() => setMode(m)} aria-pressed={mode === m}
          className={`h-11 px-5 rounded-[14px] text-sm font-semibold flex items-center gap-2 transition-colors ${mode === m ? 'bg-neutral-800 text-white' : 'text-neutral-400 hover:text-white'}`}>
          <Icon className={`w-4 h-4 ${mode === m ? 'text-amber-400' : ''}`} /> {name}
        </button>
      ))}
    </div>
  );
  return (
    <div className="space-y-12 pb-8">
      <section className="space-y-3.5 max-w-3xl pt-2">
        <span className="inline-flex items-center gap-2 h-8 px-3 rounded-full bg-amber-500/10 text-[13px] font-semibold text-amber-300">
          <Sparkles className="w-3.5 h-3.5" /> AI reel editor
        </span>
        <h1 className="font-syne text-4xl sm:text-5xl font-extrabold leading-[1.04] tracking-tight text-white">
          {footage ? <>Drop your raw footage.<br />Say how you want it.<br /><span className="text-amber-400">Get a finished reel.</span></>
            : <>Photos and a script.<br /><span className="text-amber-400">A narrated reel.</span></>}
        </h1>
        <p className="text-lg text-neutral-400 max-w-2xl">
          {footage
            ? 'The AI watches every clip, keeps your best takes, plans the cut and shows it to you before anything is rendered. Planning and previews are free.'
            : 'Turn your photos and a short script into a narrated reel with scenes you can change.'}
        </p>
      </section>

      {showFootage ? <FootageReelForm tabs={tabs} onCreated={(id) => router.push(`/dashboard/reels/footage/${id}`)} /> : (
        <section aria-label="New reel" className={COMPOSER}>
          {tabs}
          <NewReelForm onCreated={(id) => router.push(`/dashboard/reels/${id}`)} />
        </section>
      )}

      <section className="space-y-4" aria-labelledby="your-reels">
        <div className="flex flex-wrap items-center gap-3">
          <h2 id="your-reels" className="font-syne text-2xl font-bold text-white">Your reels</h2>
          {reels && <span className="rounded-full bg-neutral-800 px-2.5 py-0.5 text-[13px] font-semibold text-neutral-300 tabular-nums">{reels.length}</span>}
          <div role="group" aria-label="Show" className="ml-auto flex flex-wrap gap-1.5">
            {FILTERS.map(([id, name]) => (
              <button key={id} type="button" onClick={() => setFilter(id)} aria-pressed={filter === id}
                className={`h-10 px-4 rounded-full border text-[13px] font-semibold transition-colors ${filter === id ? 'border-neutral-600 bg-neutral-800 text-white' : 'border-neutral-800 text-neutral-400 hover:text-white'}`}>
                {name}
              </button>
            ))}
          </div>
        </div>
        {reels === null ? (
          <div className="flex items-center gap-2 text-sm text-neutral-500"><Loader2 className="w-4 h-4 animate-spin" /> Loading reels…</div>
        ) : shown.length === 0 ? (
          <div className="rounded-3xl border border-dashed border-neutral-800 p-10 text-center">
            <Clapperboard className="w-9 h-9 text-neutral-600 mx-auto mb-3" />
            <p className="text-base font-semibold text-neutral-200">{reels.length ? 'Nothing here' : 'No reels yet'}</p>
            <p className="text-sm text-neutral-500 mt-1">{reels.length ? 'Try another filter.' : 'Your reels show up here with their status.'}</p>
          </div>
        ) : (
          <div className="grid grid-cols-[repeat(auto-fill,minmax(200px,1fr))] gap-4">
            {shown.map((r) => (
              <button key={r.href} type="button" onClick={() => router.push(r.href)}
                className="group text-left rounded-[20px] bg-neutral-900/80 border border-neutral-800 hover:border-neutral-600 overflow-hidden transition-colors">
                <span className="relative block aspect-[9/14] bg-neutral-950">
                  {r.cover_url ? (
                    <img src={r.cover_url} alt="" loading="lazy" className="absolute inset-0 w-full h-full object-cover group-hover:scale-[1.03] transition-transform duration-500" />
                  ) : (
                    <span className="absolute inset-0 flex items-center justify-center px-4 text-center font-syne text-xl font-extrabold uppercase leading-none text-amber-300/85 bg-[radial-gradient(circle_at_50%_30%,rgba(245,158,11,0.15),transparent_65%)]">
                      {r.title}
                    </span>
                  )}
                  <span className="absolute inset-0 bg-gradient-to-t from-black/60 via-transparent to-black/20" />
                  <span className="absolute top-2.5 left-2.5"><StatusPill tone={r.status.tone}>{r.status.label}</StatusPill></span>
                  {footage && (
                    <span className="absolute top-2.5 right-2.5 rounded-md bg-black/70 px-2 py-0.5 text-[11px] font-semibold text-neutral-200">
                      {r.kind === 'footage' ? 'Footage' : 'Photos'}
                    </span>
                  )}
                  {r.duration_s > 0 && (
                    <span className="absolute bottom-2.5 right-2.5 rounded-md bg-black/70 px-2 py-0.5 font-mono text-xs font-semibold text-white">
                      {formatSeconds(r.duration_s)}
                    </span>
                  )}
                </span>
                <span className="block px-3.5 pt-3 pb-3.5">
                  <span className="block text-[15px] font-semibold text-white truncate">{r.title}</span>
                  <span className="block text-[13px] text-neutral-400">{formatRelativeTime(r.created_at)}</span>
                </span>
              </button>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
