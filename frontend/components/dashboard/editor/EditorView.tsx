'use client';

import React, { useCallback, useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { ArrowUp, Clapperboard, Film, Loader2, Paperclip, Sparkles, Trash2, UploadCloud, X } from 'lucide-react';
import {
  editorApi,
  editsApi,
  type EditorAspect,
  type EditorProjectResponse,
  type EditorProjectSummary,
  type EditSummary,
} from '@/lib/api';
import { setStudioHandoff } from '@/lib/editor/handoff';
import { applyOps, duration, itemEnd, normalise, TimelineError, type Item, type Timeline, type TimelineOp } from '@/lib/editor/timeline';
import { formatRelativeTime } from '@/lib/utils/dates';
import { PageHeader } from '@/components/ui/PageHeader';

const ASPECTS: EditorAspect[] = ['9:16', '1:1', '4:5', '16:9'];
const START_FILE_TYPES = 'video/mp4,video/quicktime,video/webm,image/*,audio/*';
const TITLE_CHARS = 60;
const START_IDEAS = ['A 45-second reel of the best moments', 'Cut the dead air and add captions', 'Three short clips for Instagram', 'A punchy trailer cut to the music'];
const OPENABLE_REELS: EditSummary['status'][] = ['planned', 'done'];
const ITEM_COLOURS: Record<Item['type'], string> = {
  clip: 'bg-sky-500/30 border-sky-400/70',
  text: 'bg-violet-500/30 border-violet-400/70',
  music: 'bg-amber-500/25 border-amber-400/70',
  sfx: 'bg-rose-500/30 border-rose-400/70',
  graphic: 'bg-emerald-500/25 border-emerald-400/70',
};
const errorText = (err: unknown, fallback: string) => (err instanceof Error ? err.message : fallback);
const studioHref = (id: string) => `/studio/${encodeURIComponent(id)}`;

/** /dashboard/editor: the project list, or one open project. */
export function EditorView({ projectId }: { projectId?: string }) {
  return projectId ? <EditorProject projectId={projectId} /> : <EditorHome />;
}

function EditorHome() {
  const router = useRouter();
  const brief = useSearchParams().get('brief') ?? '';
  const [projects, setProjects] = useState<EditorProjectSummary[] | null>(null);
  const [reels, setReels] = useState<EditSummary[]>([]);
  const [prompt, setPrompt] = useState(brief.slice(0, 2000));
  const [files, setFiles] = useState<File[]>([]);
  const [dragging, setDragging] = useState(false);
  const picker = useRef<HTMLInputElement>(null);
  const [aspect, setAspect] = useState<EditorAspect>('9:16');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    editorApi.list().then(setProjects).catch((err) => setError(errorText(err, 'Could not load your projects')));
    // Reels are optional here: without the footage-reel feature the list is simply empty.
    editsApi.list().then((rows) => setReels(rows.filter((r) => OPENABLE_REELS.includes(r.status)))).catch(() => setReels([]));
  }, []);

  const open = (id: string) => router.push(`/dashboard/editor/${encodeURIComponent(id)}`);
  const openInStudio = (id: string) => router.push(studioHref(id));

  const addFiles = (added: File[]) => setFiles((current) => [...current, ...added]);

  /** Make the project in the background and open it in the studio with the files and prompt. */
  const start = () => {
    const text = prompt.trim();
    const title = (files[0]?.name.replace(/\.[^.]+$/, '') || text || 'Untitled project').slice(0, TITLE_CHARS);
    void run(
      () => editorApi.create({ title, aspect }),
      (id) => {
        setStudioHandoff({ projectId: id, files, prompt: text });
        openInStudio(id);
      },
    );
  };

  const run = async (work: () => Promise<EditorProjectResponse>, then: (id: string) => void = open) => {
    setBusy(true);
    setError(null);
    try {
      then((await work()).id);
    } catch (err) {
      setError(errorText(err, 'Could not open the project'));
      setBusy(false);
    }
  };

  return (
    <div className="space-y-6">
      <header className="pt-4 text-center sm:pt-8">
        <p className="mx-auto inline-flex items-center gap-1.5 rounded-full border border-amber-400/30 bg-amber-500/10 px-3 py-1 text-[11px] font-bold uppercase tracking-wider text-amber-300">
          <Sparkles className="h-3.5 w-3.5" aria-hidden />
          AI editor
        </p>
        <h1 className="mt-4 text-3xl font-black tracking-tight text-white sm:text-5xl">
          What are we <span className="bg-gradient-to-r from-amber-300 to-amber-500 bg-clip-text text-transparent">making today?</span>
        </h1>
        <p className="mx-auto mt-3 max-w-xl text-sm text-neutral-400">
          Drop in your footage and say what you want. The AI watches it, tells you what it found, and edits it on a timeline you can change by hand.
        </p>
      </header>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          start();
        }}
        onDragOver={(e) => {
          if (!e.dataTransfer.types.includes('Files')) return;
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          addFiles([...e.dataTransfer.files]);
        }}
        className={`relative mx-auto max-w-3xl space-y-3 rounded-3xl border bg-neutral-900/70 p-4 shadow-[0_30px_80px_-40px_rgba(245,158,11,0.45)] backdrop-blur transition-colors ${dragging ? 'border-amber-400 bg-amber-500/5' : 'border-neutral-800 focus-within:border-amber-400/50'}`}
      >
        <label className="block">
          <span className="sr-only">What do you want to make?</span>
          <textarea
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                start();
              }
            }}
            maxLength={2000}
            rows={3}
            placeholder="Drop your videos here and say what you want, e.g. “a 45-second reel of the best moments, with captions”"
            className="w-full resize-none bg-transparent px-2 py-1.5 text-[15px] text-white placeholder:text-neutral-500 focus:outline-none focus-visible:outline-none"
          />
        </label>

        {files.length === 0 && (
          <button
            type="button"
            onClick={() => picker.current?.click()}
            className="flex w-full items-center justify-center gap-3 rounded-2xl border border-dashed border-neutral-700 px-4 py-5 text-left text-neutral-400 transition-colors hover:border-amber-400/60 hover:bg-amber-500/5 hover:text-neutral-200"
          >
            <UploadCloud className="h-6 w-6 shrink-0 text-amber-400" aria-hidden />
            <span>
              <span className="block text-sm font-semibold text-neutral-200">Drop videos, music or images here</span>
              <span className="block text-xs">or click to choose · MP4, MOV, WebM, MP3, WAV, JPG, PNG</span>
            </span>
          </button>
        )}

        {files.length > 0 && (
          <ul className="flex flex-wrap gap-1.5" aria-label="Files to start with">
            {files.map((file, index) => (
              <li key={`${file.name}-${file.size}-${index}`} className="inline-flex items-center gap-1.5 rounded-full border border-neutral-700 bg-neutral-800/80 py-1 pl-2.5 pr-2 text-xs text-neutral-200">
                <Film className="h-3.5 w-3.5 text-amber-400" aria-hidden />
                <span className="max-w-[14rem] truncate">{file.name}</span>
                <button type="button" aria-label={`Remove ${file.name}`} onClick={() => setFiles(files.filter((_, i) => i !== index))} className="text-neutral-500 hover:text-rose-400">
                  <X className="h-3.5 w-3.5" aria-hidden />
                </button>
              </li>
            ))}
          </ul>
        )}

        <div className="flex flex-wrap items-center gap-2">
          <input
            ref={picker}
            type="file"
            multiple
            accept={START_FILE_TYPES}
            className="hidden"
            onChange={(e) => {
              addFiles([...(e.target.files ?? [])]);
              e.target.value = '';
            }}
          />
          <button type="button" onClick={() => picker.current?.click()} className="inline-flex h-9 items-center gap-2 rounded-full border border-neutral-800 px-3 text-xs font-bold text-neutral-300 hover:border-neutral-600 hover:text-white">
            <Paperclip className="h-4 w-4" aria-hidden />
            Add files
          </button>
          <div role="radiogroup" aria-label="Shape" className="flex gap-1.5">
            {ASPECTS.map((a) => (
              <button
                key={a}
                type="button"
                role="radio"
                aria-checked={aspect === a}
                onClick={() => setAspect(a)}
                className={`h-9 rounded-full border px-3 text-xs font-bold ${aspect === a ? 'border-amber-400 bg-amber-500/10 text-amber-300' : 'border-neutral-800 text-neutral-400 hover:text-white'}`}
              >
                {a}
              </button>
            ))}
          </div>
          <button type="submit" disabled={busy} className="ml-auto inline-flex h-10 items-center justify-center gap-2 rounded-full bg-gradient-to-r from-amber-400 to-amber-500 px-5 text-sm font-bold text-neutral-950 shadow-lg shadow-amber-500/20 hover:from-amber-300 hover:to-amber-400 disabled:opacity-60">
            {busy ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> : <ArrowUp className="h-4 w-4" aria-hidden />}
            Start
          </button>
        </div>
      </form>

      <div className="mx-auto flex max-w-3xl flex-wrap justify-center gap-2">
        {START_IDEAS.map((idea) => (
          <button key={idea} type="button" onClick={() => setPrompt(idea)} className="rounded-full border border-neutral-800 bg-neutral-900/60 px-3 py-1.5 text-xs text-neutral-300 transition-colors hover:border-amber-400/50 hover:text-white">
            {idea}
          </button>
        ))}
      </div>

      {error && <p role="alert" className="text-sm text-rose-400">{error}</p>}

      {reels.length > 0 && (
        <section aria-labelledby="open-reel" className="space-y-2">
          <h2 id="open-reel" className="text-sm font-semibold text-neutral-300">Keep editing a reel</h2>
          <div className="flex flex-wrap gap-2">
            {reels.map((reel) => (
              <span key={reel.id} className="inline-flex items-stretch overflow-hidden rounded-xl border border-neutral-800 bg-neutral-900">
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => run(() => editorApi.openReel(reel.id))}
                  className="inline-flex items-center gap-2 px-3 py-2 text-[13px] text-neutral-200 hover:text-amber-300"
                >
                  <Clapperboard className="h-4 w-4 text-neutral-500" aria-hidden />
                  {reel.title}
                </button>
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => run(() => editorApi.openReel(reel.id), openInStudio)}
                  aria-label={`Open ${reel.title} in Studio`}
                  className="border-l border-neutral-800 px-3 text-xs font-semibold text-amber-400 hover:bg-amber-500/10 hover:text-amber-300"
                >
                  Open in Studio
                </button>
              </span>
            ))}
          </div>
        </section>
      )}

      <section aria-labelledby="your-projects" className="space-y-2">
        <h2 id="your-projects" className="text-sm font-semibold text-neutral-300">Your projects</h2>
        {projects === null ? (
          <p className="text-sm text-neutral-500">Loading…</p>
        ) : projects.length === 0 ? (
          <p className="text-sm text-neutral-500">No projects yet. Start one above.</p>
        ) : (
          <ul className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
            {projects.map((p) => (
              <li key={p.id} className="relative">
                <Link
                  href={studioHref(p.id)}
                  aria-label={`Open ${p.title} in Studio`}
                  className="absolute right-3 top-3 z-10 rounded-lg border border-neutral-700 px-2 py-1 text-[11px] font-semibold text-amber-400 hover:border-amber-400 hover:text-amber-300"
                >
                  Open in Studio
                </Link>
                <button type="button" onClick={() => open(p.id)} className="w-full rounded-2xl border border-neutral-800 bg-neutral-900 p-4 pr-32 text-left hover:border-neutral-600">
                  <span className="block truncate font-semibold text-white">{p.title}</span>
                  <span className="mt-1 block text-xs text-neutral-500">
                    {p.duration_s.toFixed(1)} s · version {p.version} · edited {formatRelativeTime(p.updated_at)}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

function EditorProject({ projectId }: { projectId: string }) {
  const router = useRouter();
  const [project, setProject] = useState<EditorProjectResponse | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    editorApi
      .get(projectId)
      .then((p) => setProject({ ...p, timeline: normalise(p.timeline) }))
      .catch((err) => setError(errorText(err, 'Could not load the project')));
  }, [projectId]);

  useEffect(load, [load]);

  /** Applies ops in the browser at once, then saves them; a refused save puts the last saved version back. */
  const edit = async (ops: TimelineOp[]) => {
    if (!project) return;
    let next: Timeline;
    try {
      next = applyOps(project.timeline, ops);
    } catch (err) {
      setError(err instanceof TimelineError ? err.message : errorText(err, 'That edit did not work'));
      return;
    }
    const saved = project;
    setProject({ ...project, timeline: next });
    setSelected(null);
    setSaving(true);
    setError(null);
    try {
      const result = await editorApi.applyOps(project.id, { base_version: project.version, ops });
      setProject({ ...saved, version: result.version, timeline: normalise(result.timeline) });
    } catch (err) {
      setProject(saved);
      setError(errorText(err, 'Could not save that edit'));
      load();
    } finally {
      setSaving(false);
    }
  };

  if (!project) {
    return error ? <p role="alert" className="text-sm text-rose-400">{error}</p> : <p className="text-sm text-neutral-500">Loading…</p>;
  }

  const { timeline } = project;
  const item = selected ? timeline.tracks.flatMap((t) => t.items).find((i) => i.id === selected) : undefined;

  return (
    <div className="space-y-5">
      <PageHeader
        back={{ label: 'All projects', onClick: () => router.push('/dashboard/editor') }}
        title={project.title}
        description={`${timeline.width}×${timeline.height} · ${(duration(timeline) / timeline.fps).toFixed(1)} s · version ${project.version}${saving ? ' · saving…' : ''}`}
      />
      {error && <p role="alert" className="text-sm text-rose-400">{error}</p>}

      <TimelineView timeline={timeline} selected={selected} onSelect={setSelected} />

      {item && (
        <div className="flex flex-wrap items-center gap-3 rounded-2xl border border-neutral-800 bg-neutral-900 p-4 text-sm">
          <span className="font-semibold text-white">{describeItem(item)}</span>
          <span className="text-neutral-500">
            {(item.at / timeline.fps).toFixed(2)}–{(itemEnd(item) / timeline.fps).toFixed(2)} s
          </span>
          <div className="ml-auto flex gap-2">
            <button type="button" onClick={() => edit([{ op: 'remove_item', item: item.id }])} className="inline-flex items-center gap-1.5 rounded-xl border border-neutral-700 px-3 py-1.5 text-neutral-200 hover:border-rose-400">
              <Trash2 className="h-4 w-4" aria-hidden /> Delete
            </button>
            <button type="button" onClick={() => edit([{ op: 'remove_item', item: item.id, ripple: true }])} className="rounded-xl border border-neutral-700 px-3 py-1.5 text-neutral-200 hover:border-rose-400">
              Delete and close the gap
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function describeItem(item: Item): string {
  switch (item.type) {
    case 'clip':
      return `Clip ${item.id} · ${item.asset}${item.speed !== 1 ? ` · ${item.speed}×` : ''}`;
    case 'text':
      return `“${item.text}”`;
    case 'music':
      return `Music · ${item.track}`;
    case 'sfx':
      return `Sound · ${item.name}`;
    case 'graphic':
      return `Graphic ${item.id}`;
  }
}

/** Every track as a row, every item placed by its frames; click an item to select it. */
function TimelineView({ timeline, selected, onSelect }: { timeline: Timeline; selected: string | null; onSelect: (id: string | null) => void }) {
  const frames = Math.max(duration(timeline), timeline.fps * 10);
  const seconds = Math.ceil(frames / timeline.fps);
  const step = seconds > 60 ? 10 : seconds > 20 ? 5 : 1;
  const share = (f: number) => `${(f / frames) * 100}%`;

  return (
    <div className="overflow-x-auto rounded-2xl border border-neutral-800 bg-neutral-950">
      <div className="min-w-[640px]">
        <div className="relative ml-28 h-7 border-b border-neutral-800 font-jetbrains text-[10px] text-neutral-500">
          {Array.from({ length: Math.floor(seconds / step) + 1 }, (_, i) => i * step).map((s) => (
            <span key={s} className="absolute top-2" style={{ left: share(s * timeline.fps) }}>
              {Math.floor(s / 60)}:{String(s % 60).padStart(2, '0')}
            </span>
          ))}
        </div>
        {timeline.tracks.map((track) => (
          <div key={track.id} className="flex h-11 border-b border-neutral-900">
            <div className="flex w-28 shrink-0 items-center gap-1.5 border-r border-neutral-800 px-3 text-xs font-semibold text-neutral-400">
              <span className="truncate">{track.id}</span>
              <span className="text-[10px] font-normal text-neutral-600">{track.kind}</span>
            </div>
            <div className="relative flex-1">
              {track.items.map((i) => (
                <button
                  key={i.id}
                  type="button"
                  aria-pressed={selected === i.id}
                  onClick={() => onSelect(selected === i.id ? null : i.id)}
                  title={describeItem(i)}
                  className={`absolute bottom-1.5 top-1.5 truncate rounded-md border px-1.5 text-left text-[10.5px] font-semibold text-white ${ITEM_COLOURS[i.type]} ${selected === i.id ? 'ring-2 ring-amber-400' : ''}`}
                  style={{ left: share(i.at), width: share(itemEnd(i) - i.at) }}
                >
                  {i.type === 'text' ? i.text : i.id}
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
