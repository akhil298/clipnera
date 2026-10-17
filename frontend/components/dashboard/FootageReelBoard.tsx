'use client';

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Clapperboard, Loader2, RotateCcw, Undo2 } from 'lucide-react';
import { EditChange, EditResponse, EditSourceResponse, EditTimelineResponse, editsApi } from '@/lib/api';
import { canUseCaptionStyle, useEntitlements } from '@/hooks/useEntitlements';
import { getAllCaptionStyles } from '@/lib/utils/captionStyles';
import { EDIT_STATUS, formatSeconds, listWords, planDiff } from '@/lib/utils/footageReels';
import { PageHeader } from '@/components/ui/PageHeader';
import { StatusPill } from '@/components/ui/StatusPill';
import { FootageReelPlanning } from './FootageReelPlanning';
import { FootageReelReady } from './FootageReelReady';
import { type ChatMessage, FootageReelReview } from './FootageReelReview';
import { useReelPick } from './ReelModelPicker';

const BUSY: EditResponse['status'][] = ['analyzing', 'rendering'];
const HISTORY = 20;
const ghost = 'inline-flex items-center gap-2 h-11 px-4 rounded-xl border border-neutral-700 bg-neutral-900 hover:bg-neutral-800 text-sm font-semibold text-white disabled:opacity-40';

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
  const pickModel = useReelPick();
  const [edit, setEdit] = useState<EditResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [working, setWorking] = useState(false);
  // A finished reel opens on the result; "Make changes" brings the plan back.
  const [editing, setEditing] = useState(false);
  // The reel before each change, newest last: what Undo goes back to.
  const [history, setHistory] = useState<EditResponse[]>([]);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [maxOutput, setMaxOutput] = useState(45);
  const preview = useStablePreview(edit);

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
    editsApi.limits().then((l) => setMaxOutput(l.max_output_seconds)).catch(() => undefined);
  }, []);

  const captionOptions = useMemo(
    () => getAllCaptionStyles().filter((s) => !entitlements || canUseCaptionStyle(entitlements, s.id)),
    [entitlements],
  );

  const remember = (before: EditResponse | null) => before && setHistory((prev) => [...prev.slice(1 - HISTORY), before]);

  /** Runs a call that returns the reel; ``undoable`` keeps the version before it for Undo. */
  const act = async (call: () => Promise<EditResponse>, undoable = false): Promise<EditResponse | null> => {
    const before = edit;
    setError(null);
    setWorking(true);
    try {
      const next = await call();
      setEdit(next);
      if (undoable) remember(before);
      return next;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong');
      return null;
    } finally {
      setWorking(false);
    }
  };
  const change = (...changes: EditChange[]) => act(() => editsApi.change(editId, changes), true);

  const undoChanges = edit && history.length ? planDiff(history[history.length - 1], edit).undo : [];
  const undo = async () => {
    if (undoChanges.length && await act(() => editsApi.change(editId, undoChanges))) setHistory((prev) => prev.slice(0, -1));
  };

  const send = async (message: string): Promise<boolean> => {
    const before = edit;
    setMessages((prev) => [...prev, { role: 'user', text: message }]);
    setWorking(true);
    try {
      const next = await editsApi.chat(editId, { message, ...pickModel });
      setEdit(next);
      remember(before);
      const { changed } = before ? planDiff(before, next) : { changed: [] };
      setMessages((prev) => [...prev, {
        role: 'editor', changed,
        text: changed.length ? `Done. I changed the ${listWords(changed)}. Undo puts it back.` : 'Done, though nothing visible changed. Try being more specific.',
      }]);
      return true;
    } catch (err) {
      setMessages((prev) => [...prev, { role: 'editor', text: err instanceof Error ? err.message : "I couldn't make that change." }]);
      return false;
    } finally {
      setWorking(false);
    }
  };

  const render = async () => {
    if (await act(() => editsApi.render(editId))) setEditing(false);
  };
  const replan = async () => {
    if (await act(() => editsApi.replan(editId))) {
      setHistory([]);
      setMessages([]);
    }
  };

  if (!edit) {
    return (
      <div className="space-y-4">
        <PageHeader back={{ label: 'Reels', onClick: onBack }} title="Loading reel…" />
        {error ? <p role="alert" className="text-sm text-rose-300">{error}</p> : <Loader2 className="w-6 h-6 text-amber-400 animate-spin" />}
      </div>
    );
  }

  const status = EDIT_STATUS[edit.status];
  const plan = edit.plan;
  const canEdit = (edit.status === 'planned' || edit.status === 'done') && !working;
  const showReady = edit.status === 'done' && Boolean(edit.output_url) && !editing;
  const showReview = Boolean(plan && preview) && edit.status !== 'analyzing' && !showReady;

  return (
    <div className="space-y-6">
      <PageHeader
        back={{ label: 'Reels', onClick: onBack }}
        title={edit.title}
        eyebrow={<StatusPill tone={status.tone}>{status.label}</StatusPill>}
        description={
          <>
            {edit.status === 'analyzing' && 'Reading your footage and planning the edit.'}
            {edit.status === 'planned' && plan && `${formatSeconds(edit.duration_s)} cut from ${formatSeconds(edit.raw_seconds)} of footage. Changes and previews are free.`}
            {edit.status === 'rendering' && 'Rendering your reel. This page updates by itself.'}
            {edit.status === 'done' && `Rendered · ${edit.credits_charged} credits used`}
            {edit.status === 'failed' && (edit.error ?? 'Something went wrong while planning this reel.')}
          </>
        }
        actions={
          <>
            {showReview && (
              <>
                <button type="button" onClick={undo} disabled={!canEdit || undoChanges.length === 0} aria-label="Undo the last change" title="Undo the last change"
                  className="w-11 h-11 rounded-xl border border-neutral-700 bg-neutral-900 hover:bg-neutral-800 text-white flex items-center justify-center disabled:opacity-40">
                  <Undo2 className="w-4 h-4" />
                </button>
                <button type="button" onClick={replan} disabled={!canEdit || edit.replans_left === 0} className={ghost}>
                  <RotateCcw className="w-4 h-4" /> New plan · {edit.replans_left} left
                </button>
                <button type="button" disabled={!canEdit} onClick={render}
                  className="inline-flex items-center gap-2 h-11 px-5 rounded-xl bg-amber-500 hover:bg-amber-400 text-neutral-950 text-[15px] font-bold shadow-md shadow-amber-500/20 disabled:opacity-50">
                  <Clapperboard className="w-4 h-4" />
                  {edit.renders ? 'Render again' : 'Render'} · {edit.credits_estimate} credits
                </button>
              </>
            )}
            {edit.status === 'failed' && (
              <button type="button" onClick={() => act(() => editsApi.analyze(edit.id))} className={ghost}>
                <RotateCcw className="w-4 h-4" /> Try again
              </button>
            )}
          </>
        }
      />

      {error && <p role="alert" className="text-sm text-rose-300">{error}</p>}
      {edit.status !== 'failed' && edit.error && <p className="text-sm text-amber-300">{edit.error}</p>}
      {edit.status === 'rendering' && (
        <div className="flex items-center gap-3 rounded-2xl border border-amber-500/25 bg-neutral-900/80 p-4 text-[15px] text-neutral-200">
          <Loader2 className="w-5 h-5 text-amber-400 animate-spin" /> Rendering your reel. You can leave this page; we'll notify you when it's done.
        </div>
      )}

      {edit.status === 'analyzing' && <FootageReelPlanning edit={edit} />}
      {showReady && <FootageReelReady edit={edit} onEdit={() => setEditing(true)} onNew={onBack} />}
      {showReview && plan && preview && (
        <FootageReelReview edit={edit} preview={preview} canEdit={canEdit} busy={working} maxOutput={maxOutput}
          captionOptions={captionOptions} change={change} messages={messages} onSend={send} />
      )}
    </div>
  );
}
