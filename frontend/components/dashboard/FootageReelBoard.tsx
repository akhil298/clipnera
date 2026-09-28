'use client';

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Check, Clapperboard, Copy, Download, Loader2, MessageSquare, RotateCcw, Send, Sparkles, Undo2 } from 'lucide-react';
import {
  EDIT_LOOKS,
  EDIT_MOODS,
  EditChange,
  EditResponse,
  EditSourceResponse,
  EditTimelineResponse,
  editsApi,
} from '@/lib/api';
import { canUseCaptionStyle, useEntitlements } from '@/hooks/useEntitlements';
import { getAllCaptionStyles } from '@/lib/utils/captionStyles';
import {
  ANALYSIS_STEPS,
  CONTENT_TYPE_LABEL,
  EDIT_STATUS,
  RESOLVED_SCRIPT_LABEL,
  TARGET_OPTIONS,
  formatSeconds,
} from '@/lib/utils/footageReels';
import { PageHeader } from '@/components/ui/PageHeader';
import { StatusPill } from '@/components/ui/StatusPill';
import { ReelPreviewPlayer } from './ReelPreviewPlayer';

const BUSY: EditResponse['status'][] = ['analyzing', 'rendering'];
const select = 'h-8 px-2 rounded-lg bg-neutral-950 border border-neutral-800 text-xs text-white focus:outline-none focus:border-amber-400';

function Row({ name, children }: { name: string; children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[76px_minmax(0,1fr)] gap-2 items-center py-1.5 border-b border-neutral-800/70 last:border-0">
      <span className="text-[11px] font-semibold uppercase tracking-wide text-neutral-500">{name}</span>
      <div className="min-w-0 text-xs text-neutral-200 flex flex-wrap items-center gap-2">{children}</div>
    </div>
  );
}

function CopyButton({ text, labelText }: { text: string; labelText: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button type="button" aria-label={labelText}
      onClick={() => navigator.clipboard.writeText(text).then(() => { setCopied(true); setTimeout(() => setCopied(false), 1500); }).catch(() => undefined)}
      className="inline-flex items-center gap-1 h-7 px-2 rounded-lg border border-neutral-700 text-[11px] font-semibold text-neutral-200 hover:bg-neutral-800">
      {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />} {copied ? 'Copied' : 'Copy'}
    </button>
  );
}

function Progress({ progress }: { progress: string | null }) {
  // Uploading is always finished by the time analysis reports progress.
  const active = Math.max(1, (progress ? ANALYSIS_STEPS.indexOf(progress) : -1) + 1);
  return (
    <div className="rounded-2xl border border-amber-500/25 bg-neutral-900/80 p-5 max-w-md space-y-3">
      <ol className="space-y-2">
        {['Uploading your files', ...ANALYSIS_STEPS].map((step, i) => {
          const state = i < active ? 'done' : i === active ? 'run' : 'todo';
          return (
            <li key={step} className={`flex items-center gap-2.5 text-sm ${state === 'todo' ? 'text-neutral-500' : state === 'run' ? 'text-amber-300' : 'text-neutral-200'}`}>
              {state === 'done' ? <Check className="w-4 h-4 text-emerald-400" /> : state === 'run' ? <Loader2 className="w-4 h-4 animate-spin" /> : <span className="w-4 h-4 rounded-full border border-neutral-700" />}
              {step}
            </li>
          );
        })}
      </ol>
      <p className="text-xs text-neutral-500">Usually 2–3 minutes. You can leave this page; we'll notify you when the plan is ready.</p>
    </div>
  );
}

/** The preview keeps its media while polling refreshes signed URLs, and only reloads when the plan itself changes. */
function useStablePreview(edit: EditResponse | null) {
  const [preview, setPreview] = useState<{ key: string; timeline: EditTimelineResponse; sources: EditSourceResponse[]; music: string | null } | null>(null);
  useEffect(() => {
    if (!edit?.timeline) return;
    const key = JSON.stringify(edit.timeline);
    setPreview((prev) => (prev?.key === key ? prev : {
      key, timeline: edit.timeline as EditTimelineResponse, sources: edit.sources, music: edit.plan?.music?.url ?? null,
    }));
  }, [edit]);
  return preview;
}

export function FootageReelBoard({ editId, onBack }: { editId: string; onBack: () => void }) {
  const { entitlements } = useEntitlements();
  const [edit, setEdit] = useState<EditResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [working, setWorking] = useState(false);
  const [hook, setHook] = useState('');
  const [message, setMessage] = useState('');
  const preview = useStablePreview(edit);
  const [maxOutput, setMaxOutput] = useState(45);
  const planHook = edit?.plan?.hook;

  const load = useCallback(() => editsApi.get(editId).then(setEdit).catch((e: Error) => setError(e.message)), [editId]);
  useEffect(() => {
    load();
  }, [load]);
  useEffect(() => {
    if (!edit || !BUSY.includes(edit.status)) return;
    const id = setInterval(load, 2500);
    return () => clearInterval(id);
  }, [edit, load]);
  useEffect(() => {
    if (planHook !== undefined) setHook(planHook);
  }, [planHook]);
  useEffect(() => {
    editsApi.limits().then((l) => setMaxOutput(l.max_output_seconds)).catch(() => undefined);
  }, []);

  const act = async (call: () => Promise<EditResponse>): Promise<boolean> => {
    setError(null);
    setWorking(true);
    try {
      setEdit(await call());
      return true;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong');
      return false;
    } finally {
      setWorking(false);
    }
  };
  const change = (...changes: EditChange[]) => act(() => editsApi.change(editId, changes));

  const captionOptions = useMemo(
    () => getAllCaptionStyles().filter((s) => !entitlements || canUseCaptionStyle(entitlements, s.id)),
    [entitlements],
  );

  if (!edit) {
    return (
      <div className="space-y-4">
        <PageHeader back={{ label: 'Reels', onClick: onBack }} title="Loading reel…" />
        {error ? <p role="alert" className="text-xs text-rose-300">{error}</p> : <Loader2 className="w-6 h-6 text-amber-400 animate-spin" />}
      </div>
    );
  }

  const status = EDIT_STATUS[edit.status];
  const plan = edit.plan;
  const canEdit = (edit.status === 'planned' || edit.status === 'done') && !working;

  return (
    <div className="space-y-5">
      <PageHeader
        back={{ label: 'Reels', onClick: onBack }}
        title={edit.title}
        eyebrow={<StatusPill tone={status.tone}>{status.label}</StatusPill>}
        description={
          <>
            {edit.status === 'analyzing' && (edit.progress ?? 'Getting started…')}
            {edit.status === 'planned' && plan && `${formatSeconds(edit.duration_s)} · planned from ${formatSeconds(edit.raw_seconds)} of footage. Change anything below; the preview updates instantly.`}
            {edit.status === 'rendering' && 'Rendering your reel. This page updates by itself.'}
            {edit.status === 'done' && `Rendered · ${edit.credits_charged} credits used`}
            {edit.status === 'failed' && (edit.error ?? 'Something went wrong while planning this reel.')}
          </>
        }
        actions={
          <>
            {edit.status === 'done' && edit.output_url && (
              <a href={edit.output_url} download className="inline-flex items-center gap-2 h-9 px-3.5 rounded-xl border border-neutral-700 bg-neutral-900 hover:bg-neutral-800 text-[13px] font-semibold text-white">
                <Download className="w-4 h-4" /> Download
              </a>
            )}
            {plan && (edit.status === 'planned' || edit.status === 'done') && (
              <button type="button" disabled={working} onClick={() => act(() => editsApi.render(edit.id))}
                className="inline-flex items-center gap-2 h-9 px-3.5 rounded-xl bg-amber-500 hover:bg-amber-400 text-neutral-950 text-[13px] font-bold shadow-md shadow-amber-500/20 disabled:opacity-50">
                <Clapperboard className="w-4 h-4" />
                {edit.renders ? 'Render again' : 'Render'} · {edit.credits_estimate} credits
              </button>
            )}
            {edit.status === 'failed' && (
              <button type="button" onClick={() => act(() => editsApi.analyze(edit.id))}
                className="inline-flex items-center gap-2 h-9 px-3.5 rounded-xl border border-neutral-700 text-[13px] font-semibold text-white hover:bg-neutral-800">
                <RotateCcw className="w-4 h-4" /> Try again
              </button>
            )}
          </>
        }
      />

      {error && <p role="alert" className="text-xs text-rose-300">{error}</p>}
      {edit.status !== 'failed' && edit.error && <p className="text-xs text-amber-300">{edit.error}</p>}
      {edit.status === 'analyzing' && <Progress progress={edit.progress} />}

      {edit.status === 'done' && edit.output_url && (
        <section className="flex flex-col md:flex-row gap-5 items-start" aria-label="Your finished reel">
          <video src={edit.output_url} controls playsInline className="w-full max-w-[280px] aspect-[9/16] rounded-2xl bg-black border border-neutral-800" />
          <div className="space-y-3 max-w-md">
            {edit.music_credit && (
              <div className="rounded-xl border border-neutral-800 bg-neutral-900/80 p-3 space-y-2">
                <p className="text-xs font-semibold text-white">Music credit</p>
                <p className="text-xs text-neutral-300">{edit.music_credit}</p>
                <p className="text-[11px] text-neutral-500">The track's licence asks for this credit. It's already in the caption below.</p>
                <CopyButton text={edit.music_credit} labelText="Copy the music credit" />
              </div>
            )}
            {plan && (plan.caption || plan.hashtags.length > 0) && (
              <div className="rounded-xl border border-neutral-800 bg-neutral-900/80 p-3 space-y-2">
                <p className="text-xs font-semibold text-white">Instagram caption</p>
                <p className="text-xs text-neutral-300 whitespace-pre-line">
                  {[plan.caption, plan.hashtags.join(' '), edit.music_credit].filter(Boolean).join('\n\n')}
                </p>
                <CopyButton text={[plan.caption, plan.hashtags.join(' '), edit.music_credit].filter(Boolean).join('\n\n')} labelText="Copy the caption" />
              </div>
            )}
          </div>
        </section>
      )}

      {plan && preview && edit.status !== 'analyzing' && (
        <section className="grid grid-cols-1 lg:grid-cols-[300px_minmax(0,1fr)] gap-6 items-start" aria-label="Plan and preview">
          <ReelPreviewPlayer timeline={preview.timeline} sources={preview.sources} musicUrl={preview.music} />

          <div className="space-y-4 max-w-2xl">
            <div className="rounded-2xl border border-neutral-800 bg-neutral-900/80 p-4">
              <h2 className="text-sm font-bold text-white mb-2 flex items-center gap-2"><Sparkles className="w-4 h-4 text-amber-400" /> The plan</h2>
              <Row name="Type">{CONTENT_TYPE_LABEL[plan.content_type] ?? plan.content_type}</Row>
              <Row name="Length">
                <span className="font-mono tabular-nums">{formatSeconds(edit.duration_s)}</span>
                <label htmlFor="plan-length" className="sr-only">Target length</label>
                <select id="plan-length" className={select} disabled={!canEdit} value={edit.target_seconds}
                  onChange={(e) => change({ op: 'set_length', value: e.target.value })}>
                  {TARGET_OPTIONS.filter((s) => s <= maxOutput).map((s) => <option key={s} value={s}>{s === 0 ? 'Auto length' : `About ${s} s`}</option>)}
                </select>
              </Row>
              <Row name="Script">
                <span>
                  {RESOLVED_SCRIPT_LABEL[plan.script_mode]}
                  {plan.script_mode === 'spoken' && ` · ${plan.script_lines_found} of ${plan.script_lines_total} lines found`}
                </span>
              </Row>
              {plan.missing_lines.length > 0 && (
                <div className="my-2 rounded-lg border border-amber-500/30 bg-amber-500/10 p-2.5 text-xs text-amber-100 space-y-1.5">
                  <p>{plan.missing_lines.length} script line{plan.missing_lines.length > 1 ? 's weren’t' : ' wasn’t'} said on camera
                    {plan.skip_missing ? ' and will be left out.' : ' and will show as a text card.'}</p>
                  <ul className="list-disc pl-4 text-amber-200/80">{plan.missing_lines.map((l) => <li key={l}>{l}</li>)}</ul>
                  <button type="button" disabled={!canEdit} onClick={() => change({ op: 'skip_missing_lines', value: plan.skip_missing ? 'false' : 'true' })}
                    className="font-semibold text-amber-300 hover:text-amber-200">
                    {plan.skip_missing ? 'Show them as text cards' : 'Leave them out'}
                  </button>
                </div>
              )}
              {plan.removed_lines.length > 0 && (
                <div className="my-2 rounded-lg border border-neutral-800 bg-neutral-950/60 p-2.5 text-xs space-y-1.5">
                  <p className="text-neutral-300">{plan.removed_lines.length} line{plan.removed_lines.length > 1 ? 's' : ''} left out (retakes, off-script or trimmed):</p>
                  <ul className="space-y-1">
                    {plan.removed_lines.slice(0, 8).map((line) => (
                      <li key={line.id} className="flex items-start justify-between gap-2">
                        <span className="text-neutral-400 line-clamp-2">“{line.text}”</span>
                        <button type="button" disabled={!canEdit} onClick={() => change({ op: 'restore_line', value: line.id })}
                          className="shrink-0 inline-flex items-center gap-1 font-semibold text-amber-300 hover:text-amber-200 disabled:opacity-50">
                          <Undo2 className="w-3.5 h-3.5" /> Restore
                        </button>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              <Row name="Hook">
                <form className="flex gap-1.5 flex-1 min-w-0" onSubmit={(e) => { e.preventDefault(); change({ op: 'set_hook', value: hook }); }}>
                  <label htmlFor="plan-hook" className="sr-only">Hook headline</label>
                  <input id="plan-hook" value={hook} onChange={(e) => setHook(e.target.value)} maxLength={60} disabled={!canEdit}
                    className="flex-1 min-w-0 h-8 px-2.5 rounded-lg bg-neutral-950 border border-neutral-800 text-xs text-white focus:outline-none focus:border-amber-400" />
                  {hook !== plan.hook && (
                    <button type="submit" disabled={!canEdit} className="h-8 px-2.5 rounded-lg border border-neutral-700 text-[11px] font-semibold text-neutral-200 hover:bg-neutral-800">Save</button>
                  )}
                </form>
              </Row>
              <Row name="Music">
                {plan.music ? (
                  <span className="truncate">{plan.music.title} · {plan.music.artist}
                    <span className="ml-1.5 rounded-md border border-neutral-700 px-1.5 py-0.5 font-mono text-[10px] text-neutral-300">{plan.music.licence}</span>
                  </span>
                ) : <span className="text-neutral-500">No music</span>}
                <label htmlFor="plan-music" className="sr-only">Music mood</label>
                <select id="plan-music" className={select} disabled={!canEdit} value=""
                  onChange={(e) => e.target.value && change({ op: 'set_music', value: e.target.value })}>
                  <option value="">Change…</option>
                  {EDIT_MOODS.map((mood) => <option key={mood} value={mood}>{mood[0].toUpperCase() + mood.slice(1)}</option>)}
                  <option value="none">No music</option>
                </select>
              </Row>
              <Row name="Look">
                <label htmlFor="plan-look" className="sr-only">Colour look</label>
                <select id="plan-look" className={select} disabled={!canEdit} value={plan.look} onChange={(e) => change({ op: 'set_look', value: e.target.value })}>
                  {Object.entries(EDIT_LOOKS).map(([id, name]) => <option key={id} value={id}>{name}</option>)}
                </select>
              </Row>
              <Row name="Captions">
                <label htmlFor="plan-captions" className="sr-only">Caption style</label>
                <select id="plan-captions" className={select} disabled={!canEdit} value={plan.caption_style}
                  onChange={(e) => change({ op: 'set_caption_style', value: e.target.value })}>
                  {captionOptions.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
                </select>
              </Row>
              <Row name="Extras">
                <span>{plan.broll_count} B-roll shot{plan.broll_count === 1 ? '' : 's'} from your footage · {plan.pop_count} pop-up{plan.pop_count === 1 ? '' : 's'}</span>
              </Row>
            </div>

            <form className="rounded-2xl border border-neutral-800 bg-neutral-900/80 p-3 space-y-2"
              onSubmit={(e) => {
                e.preventDefault();
                if (message.trim()) act(() => editsApi.chat(edit.id, message.trim())).then((done) => done && setMessage(''));
              }}>
              <label htmlFor="plan-chat" className="text-xs font-semibold text-white flex items-center gap-2">
                <MessageSquare className="w-4 h-4 text-amber-400" /> Tell the editor what to change
                <span className="font-normal text-neutral-500">· {edit.chat_edits_left} left</span>
              </label>
              <div className="flex gap-2">
                <input id="plan-chat" value={message} onChange={(e) => setMessage(e.target.value)} maxLength={300} disabled={!canEdit || edit.chat_edits_left === 0}
                  placeholder="e.g. make the hook punchier and use calmer music"
                  className="flex-1 min-w-0 h-9 px-3 rounded-xl bg-neutral-950 border border-neutral-800 text-[13px] text-white placeholder:text-neutral-600 focus:outline-none focus:border-amber-400" />
                <button type="submit" disabled={!canEdit || !message.trim() || edit.chat_edits_left === 0} aria-label="Send"
                  className="h-9 w-9 rounded-xl bg-neutral-800 hover:bg-neutral-700 text-white flex items-center justify-center disabled:opacity-40">
                  {working ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                </button>
              </div>
            </form>

            <div className="flex flex-wrap items-center gap-3 text-[11.5px] text-neutral-500">
              <button type="button" disabled={!canEdit || edit.replans_left === 0} onClick={() => act(() => editsApi.replan(edit.id))}
                className="inline-flex items-center gap-1.5 h-8 px-3 rounded-lg border border-neutral-700 font-semibold text-neutral-200 hover:bg-neutral-800 disabled:opacity-40">
                <RotateCcw className="w-3.5 h-3.5" /> Try a different plan · {edit.replans_left} left
              </button>
              <span>Changes and previews are free. {edit.renders ? 'Re-renders cost a quarter of the first render.' : 'Credits are taken only when you render, and refunded if it fails.'}</span>
            </div>
          </div>
        </section>
      )}
    </div>
  );
}
