'use client';

import React, { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Clapperboard, Download, Image as ImageIcon, Loader2, Mic, Sparkles, Type, Video } from 'lucide-react';
import {
  REEL_AUDIO_TYPES,
  REEL_IMAGE_TYPES,
  ReelAssetType,
  ReelResponse,
  ReelScene,
  ReelSceneUpdate,
  ReelStyle,
  ReelSummary,
  AI_SHOT_CREDITS,
  reelsApi,
} from '@/lib/api';
import { useEntitlements } from '@/hooks/useEntitlements';
import { useFeatureFlags } from '@/hooks/useFeatureFlags';

const LANGUAGES = [
  ['en', 'English'], ['hi', 'Hindi'], ['te', 'Telugu'], ['hinglish', 'Hinglish'], ['tenglish', 'Tenglish'],
] as const;
const STYLES: [ReelStyle, string][] = [['clean', 'Clean'], ['bold', 'Bold'], ['neon', 'Neon'], ['warm', 'Warm']];
const BUSY: ReelResponse['status'][] = ['planning', 'rendering'];
const field = 'w-full px-3 py-2 rounded-lg bg-neutral-950 border border-neutral-800 text-xs text-white focus:outline-none focus:border-amber-400';

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
    <form onSubmit={submit} className="p-5 rounded-2xl bg-neutral-900/90 border border-neutral-800 space-y-3">
      <h3 className="text-sm font-bold text-white flex items-center gap-2"><Sparkles className="w-4 h-4 text-amber-400" /> New reel</h3>
      <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Title" className={field} />
      <div className="flex gap-1 p-1 rounded-lg bg-neutral-950 border border-neutral-800 w-fit">
        {(['topic', 'script'] as const).map((m) => (
          <button key={m} type="button" onClick={() => setMode(m)}
            className={`px-3 py-1 rounded-md text-[11px] font-semibold ${mode === m ? 'bg-amber-500/20 text-amber-300' : 'text-neutral-400'}`}>
            {m === 'topic' ? 'Write it for me' : 'My own script'}
          </button>
        ))}
      </div>
      <textarea value={text} onChange={(e) => setText(e.target.value)} rows={mode === 'script' ? 6 : 2} required
        placeholder={mode === 'topic' ? 'What is the reel about? e.g. How I saved ₹10,000 by making coffee at home' : 'Paste the voiceover script'}
        className={field} />
      <div className="grid grid-cols-2 gap-2">
        <select value={language} onChange={(e) => setLanguage(e.target.value)} className={field}>
          {LANGUAGES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select>
        <select value={style} onChange={(e) => setStyle(e.target.value as ReelStyle)} className={field}>
          {STYLES.map(([value, label]) => <option key={value} value={value}>{label} style</option>)}
        </select>
      </div>
      <label className="flex items-center gap-2 p-3 rounded-lg border border-dashed border-neutral-700 text-[11px] text-neutral-300 cursor-pointer">
        <ImageIcon className="w-4 h-4 text-amber-400" />
        <span>{images.length ? `${images.length} image(s) chosen` : `Your images (up to ${maxImages})`}</span>
        <input type="file" multiple accept={REEL_IMAGE_TYPES.join(',')} className="sr-only"
          onChange={(e) => setImages(Array.from(e.target.files || []).filter((f) => REEL_IMAGE_TYPES.includes(f.type as ReelAssetType)).slice(0, maxImages))} />
      </label>
      <label className="flex items-center gap-2 p-3 rounded-lg border border-dashed border-neutral-700 text-[11px] text-neutral-300 cursor-pointer">
        <Mic className="w-4 h-4 text-amber-400" />
        <span>{voice ? voice.name : 'Your voiceover (optional; otherwise AI voice or captions only)'}</span>
        <input type="file" accept={REEL_AUDIO_TYPES.join(',')} className="sr-only" onChange={(e) => setVoice(e.target.files?.[0] ?? null)} />
      </label>
      {error && <p className="text-[11px] text-rose-400">{error}</p>}
      <button type="submit" disabled={busy || !text.trim()}
        className="px-4 py-2 rounded-xl bg-gradient-to-r from-amber-500 via-rose-500 to-violet-600 text-white text-xs font-bold disabled:opacity-40 flex items-center gap-2">
        {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Clapperboard className="w-4 h-4" />} Build scene board
      </button>
    </form>
  );
}

function SceneCard({ reel, scene, isPro, aiShots, onChange, onGenerate }: {
  reel: ReelResponse; scene: ReelScene; isPro: boolean; aiShots: boolean; onChange: (u: ReelSceneUpdate) => void; onGenerate: () => void;
}) {
  const [headline, setHeadline] = useState(scene.headline || scene.text.split(' ').slice(0, 5).join(' '));
  const preview = scene.kind === 'image' ? scene.image_url : scene.kind === 'broll' ? scene.footage?.thumb_url : null;
  return (
    <div className="rounded-2xl bg-neutral-900/90 border border-neutral-800 overflow-hidden">
      <div className="relative aspect-[9/16] bg-neutral-950 flex items-center justify-center">
        {preview ? <img src={preview} alt="" className="w-full h-full object-cover" /> : (
          <span className="px-3 text-center text-lg font-black text-amber-300 uppercase">{scene.headline || scene.text}</span>
        )}
        <span className="absolute top-2 left-2 px-1.5 py-0.5 rounded bg-black/70 text-[10px] font-mono text-white">
          {scene.start.toFixed(1)}–{scene.end.toFixed(1)}s
        </span>
        {scene.generating && (
          <div className="absolute inset-0 bg-black/60 flex items-center justify-center gap-2 text-[11px] text-amber-300">
            <Loader2 className="w-4 h-4 animate-spin" /> Generating AI shot…
          </div>
        )}
      </div>
      <div className="p-3 space-y-2">
        <p className="text-[11px] text-neutral-300 line-clamp-3">{scene.text}</p>
        <div className="flex gap-1">
          {([['image', ImageIcon], ['broll', Video], ['text', Type]] as const).map(([kind, Icon]) => (
            <span key={kind} className={`p-1 rounded ${scene.kind === kind ? 'bg-amber-500/20 text-amber-300' : 'text-neutral-600'}`}><Icon className="w-3.5 h-3.5" /></span>
          ))}
        </div>
        {reel.image_urls.length > 0 && (
          <div className="flex gap-1 overflow-x-auto">
            {reel.image_urls.map((url, i) => (
              <button key={url} type="button" onClick={() => onChange({ kind: 'image', image_index: i })}
                className={`w-9 aspect-square rounded overflow-hidden border shrink-0 ${scene.kind === 'image' && scene.image_index === i ? 'border-amber-400' : 'border-neutral-800'}`}>
                <img src={url} alt="" className="w-full h-full object-cover" />
              </button>
            ))}
          </div>
        )}
        {scene.alternates.length > 0 && (
          <div className="flex gap-1 overflow-x-auto">
            {[...(scene.footage ? [scene.footage] : []), ...scene.alternates].map((alt) => (
              <button key={alt.id} type="button" title={alt.attribution_text ?? alt.title} onClick={() => onChange({ kind: 'broll', asset_id: alt.id })}
                className={`w-9 aspect-[9/16] rounded overflow-hidden border shrink-0 ${scene.kind === 'broll' && scene.footage?.id === alt.id ? 'border-amber-400' : 'border-neutral-800'}`}>
                {alt.thumb_url && <img src={alt.thumb_url} alt="" className="w-full h-full object-cover" />}
              </button>
            ))}
          </div>
        )}
        <div className="flex gap-1">
          <input value={headline} onChange={(e) => setHeadline(e.target.value)} maxLength={60} className={`${field} py-1 text-[11px]`} />
          <button type="button" onClick={() => onChange({ kind: 'text', headline })} className="px-2 rounded-lg border border-neutral-800 text-[10px] text-neutral-300 hover:text-white">Text</button>
        </div>
        {aiShots && <button type="button" onClick={onGenerate} disabled={!isPro || scene.generating}
          title={isPro ? 'Generate a new shot for this scene with AI' : 'AI shots are a Pro feature'}
          className="w-full py-1 rounded-lg border border-violet-500/30 text-[10px] font-semibold text-violet-300 hover:bg-violet-500/10 disabled:opacity-40 flex items-center justify-center gap-1">
          <Sparkles className="w-3 h-3" /> AI shot · {AI_SHOT_CREDITS} credits{isPro ? '' : ' (Pro)'}
        </button>}
      </div>
    </div>
  );
}

function ReelBoard({ reelId }: { reelId: string }) {
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

  if (!reel) return <p className="text-xs text-neutral-400">{error ?? 'Loading…'}</p>;
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-bold text-white">{reel.title}</h2>
          <p className="text-[11px] text-neutral-400">
            {reel.status === 'planning' && 'Writing, voicing and laying out scenes…'}
            {reel.status === 'ready' && `${reel.scenes.length} scenes · ${reel.duration_s.toFixed(0)}s · tap a thumbnail to change a scene`}
            {reel.status === 'rendering' && 'Rendering your reel…'}
            {reel.status === 'done' && `Rendered · ${reel.credits_charged} credits`}
            {reel.status === 'failed' && (reel.error ?? 'Failed')}
          </p>
        </div>
        {(reel.status === 'ready' || reel.status === 'done') && (
          <button type="button" onClick={() => act(() => reelsApi.render(reel.id))}
            className="px-4 py-2 rounded-xl bg-gradient-to-r from-amber-500 via-rose-500 to-violet-600 text-white text-xs font-bold">
            {reel.status === 'done' ? 'Render again' : 'Render'} · {reel.credits_estimate} credits
          </button>
        )}
        {reel.status === 'failed' && (
          <button type="button" onClick={() => act(() => reelsApi.plan(reel.id))} className="px-4 py-2 rounded-xl border border-neutral-700 text-xs text-white">Try again</button>
        )}
      </div>
      {error && <p className="text-[11px] text-rose-400">{error}</p>}
      {BUSY.includes(reel.status) && <Loader2 className="w-6 h-6 text-amber-400 animate-spin" />}
      {reel.status === 'done' && reel.output_url && (
        <div className="flex flex-col sm:flex-row gap-4 items-start">
          <video src={reel.output_url} controls playsInline className="w-full max-w-[280px] aspect-[9/16] rounded-2xl bg-black" />
          <a href={reel.output_url} download className="px-4 py-2 rounded-xl border border-neutral-700 text-xs text-white flex items-center gap-2">
            <Download className="w-4 h-4" /> Download
          </a>
        </div>
      )}
      {(reel.status === 'ready' || reel.status === 'done') && (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
          {reel.scenes.map((scene) => (
            <SceneCard key={`${scene.index}:${scene.kind}:${scene.image_index}:${scene.footage?.id}:${scene.headline}`} reel={reel} scene={scene}
              isPro={Boolean(entitlements?.pro_ai_provider)}
              aiShots={flags['broll_studio.ai_shots']}
              onChange={(update) => act(() => reelsApi.updateScene(reel.id, scene.index, update))}
              onGenerate={() => act(() => reelsApi.generateScene(reel.id, scene.index))} />
          ))}
        </div>
      )}
    </div>
  );
}

export function ReelsView({ reelId }: { reelId?: string }) {
  const router = useRouter();
  const [reels, setReels] = useState<ReelSummary[]>([]);

  useEffect(() => {
    if (!reelId) reelsApi.list().then(setReels).catch(() => setReels([]));
  }, [reelId]);

  if (reelId) return <ReelBoard reelId={reelId} />;
  return (
    <div className="grid lg:grid-cols-[minmax(0,420px)_1fr] gap-6">
      <NewReelForm onCreated={(id) => router.push(`/dashboard/reels/${id}`)} />
      <div className="space-y-2">
        <h3 className="text-xs font-bold uppercase tracking-wider text-neutral-400">Your reels</h3>
        {reels.length === 0 && <p className="text-xs text-neutral-500">No reels yet.</p>}
        {reels.map((r) => (
          <button key={r.id} type="button" onClick={() => router.push(`/dashboard/reels/${r.id}`)}
            className="w-full flex items-center justify-between p-3 rounded-xl bg-neutral-900/90 border border-neutral-800 hover:border-neutral-600 text-left">
            <span className="text-xs font-bold text-white">{r.title}</span>
            <span className="text-[10px] text-neutral-400">{r.status} · {r.duration_s.toFixed(0)}s</span>
          </button>
        ))}
      </div>
    </div>
  );
}
