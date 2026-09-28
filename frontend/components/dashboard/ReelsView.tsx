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
import { FootageReelForm } from './FootageReelForm';

const LANGUAGES = [
  ['en', 'English'], ['hi', 'Hindi'], ['te', 'Telugu'], ['hinglish', 'Hinglish'], ['tenglish', 'Tenglish'],
] as const;
const STYLES: [ReelStyle, string][] = [['clean', 'Clean'], ['bold', 'Bold'], ['neon', 'Neon'], ['warm', 'Warm']];
const BUSY: ReelResponse['status'][] = ['planning', 'rendering'];
const field = 'w-full h-10 px-3 rounded-xl bg-neutral-950 border border-neutral-800 text-[13px] text-white placeholder:text-neutral-600 focus:outline-none focus:border-amber-400';
const label = 'block text-xs font-semibold text-neutral-300 mb-1.5';

const REEL_STATUS: Record<ReelStatus, { tone: StatusTone; label: string }> = {
  draft: { tone: 'neutral', label: 'Draft' },
  planning: { tone: 'processing', label: 'Planning' },
  ready: { tone: 'scheduled', label: 'Ready to render' },
  rendering: { tone: 'processing', label: 'Rendering' },
  done: { tone: 'ready', label: 'Done' },
  failed: { tone: 'failed', label: 'Failed' },
};

const formatSeconds = (s: number) => `${Math.floor(s / 60)}:${String(Math.round(s % 60)).padStart(2, '0')}`;

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
    <form onSubmit={submit} className="p-4 sm:p-5 rounded-2xl bg-neutral-900/80 border border-neutral-800 space-y-4" aria-labelledby="new-reel-title">
      <h2 id="new-reel-title" className="text-sm font-bold text-white flex items-center gap-2">
        <Sparkles className="w-4 h-4 text-amber-400" /> New reel
      </h2>

      <div>
        <label htmlFor="reel-title" className={label}>Title</label>
        <input id="reel-title" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. Morning routine explainer" className={field} />
      </div>

      <div>
        <div className="grid grid-cols-2 gap-1 p-1 rounded-xl bg-neutral-950 border border-neutral-800 mb-2" role="group" aria-label="Script source">
          {(['topic', 'script'] as const).map((m) => (
            <button key={m} type="button" onClick={() => setMode(m)} aria-pressed={mode === m}
              className={`h-8 rounded-lg text-xs font-semibold flex items-center justify-center gap-1.5 transition-colors ${mode === m ? 'bg-neutral-800 text-white' : 'text-neutral-400 hover:text-white'}`}>
              {m === 'topic' ? <><Sparkles className="w-3.5 h-3.5 text-amber-400" /> Write it for me</> : <><Type className="w-3.5 h-3.5" /> My own script</>}
            </button>
          ))}
        </div>
        <label htmlFor="reel-text" className="sr-only">{mode === 'topic' ? 'What the reel is about' : 'Voiceover script'}</label>
        <textarea id="reel-text" value={text} onChange={(e) => setText(e.target.value)} rows={mode === 'script' ? 6 : 3} required
          placeholder={mode === 'topic' ? 'What is the reel about? e.g. How I saved ₹10,000 by making coffee at home' : 'Paste the voiceover script'}
          className={`${field} h-auto py-2.5 resize-y leading-relaxed`} />
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label htmlFor="reel-language" className={label}>Language</label>
          <select id="reel-language" value={language} onChange={(e) => setLanguage(e.target.value)} className={field}>
            {LANGUAGES.map(([value, name]) => <option key={value} value={value}>{name}</option>)}
          </select>
        </div>
        <div>
          <label htmlFor="reel-style" className={label}>Style</label>
          <select id="reel-style" value={style} onChange={(e) => setStyle(e.target.value as ReelStyle)} className={field}>
            {STYLES.map(([value, name]) => <option key={value} value={value}>{name}</option>)}
          </select>
        </div>
      </div>

      <div>
        <span className={label}>Images <span className="font-normal text-neutral-500">· {images.length} of {maxImages}</span></span>
        <label
          className="flex items-center gap-3 p-3 rounded-xl border-2 border-dashed border-neutral-800 hover:border-amber-500/50 bg-neutral-950/60 cursor-pointer transition-colors"
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => {
            e.preventDefault();
            addImages(e.dataTransfer.files);
          }}
        >
          <span className="w-9 h-9 rounded-lg bg-amber-500/10 text-amber-400 flex items-center justify-center shrink-0"><ImageIcon className="w-4 h-4" /></span>
          <span className="text-xs">
            <span className="block font-semibold text-white">Add images</span>
            <span className="text-neutral-500">JPG, PNG or WebP · drop them here or tap to choose</span>
          </span>
          <input type="file" multiple accept={REEL_IMAGE_TYPES.join(',')} className="sr-only" onChange={(e) => addImages(e.target.files)} />
        </label>
        {images.length > 0 && (
          <ul className="mt-2 flex flex-wrap gap-2" aria-label="Chosen images">
            {previews.map((url, i) => (
              <li key={url} className="relative w-12 aspect-[3/4] rounded-lg overflow-hidden border border-neutral-800">
                <img src={url} alt="" className="w-full h-full object-cover" />
                <button type="button" onClick={() => setImages((prev) => prev.filter((_, j) => j !== i))}
                  className="absolute top-0.5 right-0.5 w-5 h-5 rounded-full bg-black/70 text-white flex items-center justify-center"
                  aria-label={`Remove image ${i + 1}`}>
                  <X className="w-3 h-3" />
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div>
        <span className={label}>Voiceover <span className="font-normal text-neutral-500">· optional</span></span>
        <label className="flex items-center gap-3 p-3 rounded-xl border-2 border-dashed border-neutral-800 hover:border-amber-500/50 bg-neutral-950/60 cursor-pointer transition-colors">
          <span className="w-9 h-9 rounded-lg bg-amber-500/10 text-amber-400 flex items-center justify-center shrink-0"><Mic className="w-4 h-4" /></span>
          <span className="text-xs min-w-0 flex-1">
            <span className="block font-semibold text-white truncate">{voice ? voice.name : 'Add your voiceover'}</span>
            <span className="text-neutral-500">Without one, an AI voice reads the script (or captions only)</span>
          </span>
          {voice && (
            <button type="button" onClick={(e) => { e.preventDefault(); setVoice(null); }} className="p-1 text-neutral-400 hover:text-white" aria-label="Remove voiceover">
              <X className="w-4 h-4" />
            </button>
          )}
          <input type="file" accept={REEL_AUDIO_TYPES.join(',')} className="sr-only" onChange={(e) => setVoice(e.target.files?.[0] ?? null)} />
        </label>
      </div>

      {error && <p role="alert" className="text-xs text-rose-300">{error}</p>}
      <button type="submit" disabled={busy || !text.trim()}
        className="w-full h-10 rounded-xl bg-amber-500 hover:bg-amber-400 text-neutral-950 text-[13px] font-bold disabled:opacity-40 flex items-center justify-center gap-2 transition-colors">
        {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Clapperboard className="w-4 h-4" />} {busy ? 'Building…' : 'Build scene board'}
      </button>
      {!text.trim() && !busy && (
        <p className="text-[11.5px] text-neutral-500 text-center -mt-2">
          {mode === 'topic' ? 'Describe the reel to continue.' : 'Paste a script to continue.'}
        </p>
      )}
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
        <p className="text-[11.5px] text-neutral-300 line-clamp-3">“{scene.text}”</p>
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
                className={`w-9 aspect-[3/4] rounded-md overflow-hidden border-2 shrink-0 ${scene.kind === 'image' && scene.image_index === i ? 'border-amber-400' : 'border-transparent opacity-70 hover:opacity-100'}`}>
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
                className={`w-9 aspect-[9/16] rounded-md overflow-hidden border-2 shrink-0 bg-neutral-800 ${scene.kind === 'broll' && scene.footage?.id === alt.id ? 'border-amber-400' : 'border-transparent opacity-70 hover:opacity-100'}`}>
                {alt.thumb_url && <img src={alt.thumb_url} alt="" className="w-full h-full object-cover" />}
              </button>
            ))}
          </div>
        )}
        <form className="flex gap-1.5" onSubmit={(e) => { e.preventDefault(); onChange({ kind: 'text', headline }); }}>
          <label htmlFor={`scene-headline-${scene.index}`} className="sr-only">Headline for scene {number}</label>
          <input id={`scene-headline-${scene.index}`} value={headline} onChange={(e) => setHeadline(e.target.value)} maxLength={60}
            className="flex-1 min-w-0 h-8 px-2.5 rounded-lg bg-neutral-950 border border-neutral-800 text-xs text-white focus:outline-none focus:border-amber-400" />
          <button type="submit" className="h-8 px-2.5 rounded-lg border border-neutral-700 text-[11px] font-semibold text-neutral-200 hover:text-white hover:bg-neutral-800">
            Use text
          </button>
        </form>
        {aiShots && (
          <button type="button" onClick={onGenerate} disabled={!isPro || scene.generating}
            title={isPro ? 'Generate a new shot for this scene with AI' : 'AI shots are a Pro feature'}
            className="mt-auto w-full h-8 rounded-lg border border-violet-500/30 text-[11px] font-semibold text-violet-300 hover:bg-violet-500/10 disabled:opacity-40 flex items-center justify-center gap-1.5">
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
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-3">
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

export function ReelsView({ reelId, editId }: { reelId?: string; editId?: string }) {
  const router = useRouter();
  const { flags } = useFeatureFlags();
  const footage = flags['broll_studio.reels.footage'];
  const [mode, setMode] = useState<'footage' | 'images'>('footage');
  const [reels, setReels] = useState<ReelCard[] | null>(null);

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
  return (
    <div className="space-y-6">
      <PageHeader
        title={footage ? 'Reels' : 'Reels from images'}
        description={footage
          ? 'Drop your raw footage and we edit it into a finished reel: best takes, cuts, B-roll, captions, music and colour. Or build one from photos and a script.'
          : 'Turn your photos and a short script into a narrated reel with scenes you can change.'} />
      <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,420px)_minmax(0,1fr)] gap-6 items-start">
        <div className="space-y-3">
          {footage && (
            <div className="grid grid-cols-2 gap-1 p-1 rounded-xl bg-neutral-950 border border-neutral-800" role="group" aria-label="How to make the reel">
              {([['footage', Film, 'Edit my footage'], ['images', ImageIcon, 'Build from images']] as const).map(([m, Icon, name]) => (
                <button key={m} type="button" onClick={() => setMode(m)} aria-pressed={mode === m}
                  className={`h-9 rounded-lg text-xs font-semibold flex items-center justify-center gap-1.5 transition-colors ${mode === m ? 'bg-neutral-800 text-white' : 'text-neutral-400 hover:text-white'}`}>
                  <Icon className={`w-3.5 h-3.5 ${mode === m ? 'text-amber-400' : ''}`} /> {name}
                </button>
              ))}
            </div>
          )}
          {showFootage
            ? <FootageReelForm onCreated={(id) => router.push(`/dashboard/reels/footage/${id}`)} />
            : <NewReelForm onCreated={(id) => router.push(`/dashboard/reels/${id}`)} />}
        </div>
        <section className="space-y-3" aria-labelledby="your-reels">
          <div className="flex items-center gap-2">
            <h2 id="your-reels" className="text-sm font-bold text-white">Your reels</h2>
            {reels && <span className="rounded-full bg-neutral-800 px-2 py-0.5 text-xs font-semibold text-neutral-300 tabular-nums">{reels.length}</span>}
          </div>
          {reels === null ? (
            <div className="flex items-center gap-2 text-xs text-neutral-500"><Loader2 className="w-4 h-4 animate-spin" /> Loading reels…</div>
          ) : reels.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-neutral-800 p-8 text-center">
              <Clapperboard className="w-8 h-8 text-neutral-600 mx-auto mb-2" />
              <p className="text-sm font-semibold text-neutral-200">No reels yet</p>
              <p className="text-xs text-neutral-500 mt-1">Your reels show up here with their cover and status.</p>
            </div>
          ) : (
            <div className="grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-4 gap-3">
              {reels.map((r) => (
                <button key={r.href} type="button" onClick={() => router.push(r.href)}
                  className="group text-left rounded-2xl bg-neutral-900/80 border border-neutral-800 hover:border-neutral-700 overflow-hidden transition-colors">
                  <span className="relative block aspect-[9/16] bg-neutral-950">
                    {r.cover_url ? (
                      <img src={r.cover_url} alt="" loading="lazy" className="absolute inset-0 w-full h-full object-cover group-hover:scale-[1.03] transition-transform duration-500" />
                    ) : (
                      <span className="absolute inset-0 flex items-center justify-center px-3 text-center text-sm font-black uppercase text-amber-300/80 bg-[radial-gradient(circle_at_50%_30%,rgba(245,158,11,0.15),transparent_65%)]">
                        {r.title}
                      </span>
                    )}
                    <span className="absolute inset-0 bg-gradient-to-t from-black/70 via-transparent to-black/20" />
                    <span className="absolute top-2 left-2"><StatusPill tone={r.status.tone}>{r.status.label}</StatusPill></span>
                    {footage && (
                      <span className="absolute top-2 right-2 rounded-md bg-black/70 px-1.5 py-0.5 text-[10px] font-semibold text-neutral-200">
                        {r.kind === 'footage' ? 'Footage' : 'Images'}
                      </span>
                    )}
                    {r.duration_s > 0 && (
                      <span className="absolute bottom-2 right-2 rounded-md bg-black/70 px-1.5 py-0.5 font-mono text-[10.5px] font-semibold text-white">
                        {formatSeconds(r.duration_s)}
                      </span>
                    )}
                  </span>
                  <span className="block p-3">
                    <span className="block text-[13px] font-semibold text-white truncate">{r.title}</span>
                    <span className="block text-[11px] text-neutral-500">{formatRelativeTime(r.created_at)}</span>
                  </span>
                </button>
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
