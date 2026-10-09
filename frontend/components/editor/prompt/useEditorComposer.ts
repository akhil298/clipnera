'use client';

import { useQuery } from '@tanstack/react-query';
import { useCallback, useMemo, useRef, useState } from 'react';

import { useOnline } from '@/components/home/useOnline';
import { useIsClient } from '@/components/ui/Portal';
import type { PromptContext } from '@/components/ui/ContextChip';
import type { QueuedPrompt } from '@/components/ui/PromptQueue';
import { createRun, estimateRun, removeQueuedRun, stopRun, updateQueuedRun } from '@/lib/api/editor/runs';
import type { RunCreate, RunEstimate, RunMode } from '@/lib/api/editor/types';
import { isApiError } from '@/lib/api/errors';
import { editorMessage } from '@/lib/api/messages/editor';
import type { RunSimulator } from '@/lib/editor/dev/simulator';
import { selectFps, selectReadOnly, useDoc, type DocStore } from '@/lib/editor/store';
import { selectActiveTurn, selectLockedIds, selectQueue, selectTurns, useRun, type RunStore, type Turn } from '@/lib/editor/run-store';
import { chipsFor, selectSelected, toWireChip, useSelection, type Chip, type SelectionStore } from '@/lib/editor/selection';
import { editorKeys } from '@/lib/query/keys/editor';

import {
  type Block,
  composerBlock,
  composerHint,
  composerPlaceholder,
  diffQueue,
  isShortOfCredits,
  nextMode,
  queueItems,
  type SendIssue,
  sendIssue,
  wantsEstimate,
} from './composer-logic';
import { useDebouncedValue } from './useDebouncedValue';

export interface EditorComposerStores {
  runs: RunStore;
  selection: SelectionStore;
  doc: DocStore;
  /** Null until the project is known; sending stays off. */
  projectId: string | null;
  /** Dev run simulator (`?sim=1`): when set, Send, Stop and the queue drive it instead of EB-3. */
  sim?: RunSimulator | null;
  /** The editor's connection state; falls back to the browser's when left out. */
  connection?: 'online' | 'offline' | 'reconnecting';
}

interface SentPayload {
  body: RunCreate;
  idempotencyKey: string;
}

const ESTIMATE_DELAY_MS = 400;

const describe = (code?: string, message?: string) => editorMessage(code, message).text;
const errorOf = (err: unknown) => (isApiError(err) ? { code: err.code, message: err.message } : { code: 'UNKNOWN', message: '' });
/** Which scripted run the simulator plays for each mode. */
const SIM_SCENARIO: Record<RunMode, string> = { edit: 'happy', ask: 'ask', plan: 'plan' };

const plainChip = ({ id, kind, label, meta, thumbnailUrl }: PromptContext): PromptContext => ({ id, kind, label, meta, thumbnailUrl });
const lastFailedSend = (turns: Turn[]): Turn | undefined => turns.findLast((turn) => turn.status === 'send_failed');

/**
 * Everything the docked composer does, over the editor's stores: the draft, the mode, chips from
 * the selection, the EB-4 estimate, send → `runs.dispatch(send)` → `POST /runs`, the queue, Stop,
 * and every reason Send is off. The view is `EditorComposer`.
 */
export function useEditorComposer({ runs, selection, doc, projectId, sim = null, connection }: EditorComposerStores) {
  const hydrated = useIsClient();
  const browserOnline = useOnline();
  const online = connection ? connection !== 'offline' : browserOnline;
  const [value, setValue] = useState('');
  const [mode, setMode] = useState<RunMode>('edit');
  const [queueEdits, setQueueEdits] = useState<Record<string, string>>({});
  const [actionError, setActionError] = useState<string | null>(null);
  const payloads = useRef(new Map<string, SentPayload>());

  const fps = useDoc(doc, selectFps);
  const readOnly = useDoc(doc, selectReadOnly);
  const projectReady = useDoc(doc, (s) => s.view !== null) && projectId !== null;
  const selected = useSelection(selection, selectSelected);
  const lockedIds = useRun(runs, selectLockedIds);
  const turns = useRun(runs, selectTurns);
  const active = useRun(runs, selectActiveTurn);
  const queue = useRun(runs, selectQueue);

  const chips: Chip[] = useMemo(() => {
    const locked = new Set(lockedIds);
    return chipsFor(selected, fps, (itemId) => locked.has(itemId));
  }, [selected, fps, lockedIds]);
  const wireChips = useMemo(() => selected.map((sel) => toWireChip(sel, fps)), [selected, fps]);

  const prompt = useDebouncedValue(value.trim(), ESTIMATE_DELAY_MS);
  const chipsKey = useMemo(() => JSON.stringify(wireChips), [wireChips]);
  const estimateQuery = useQuery<RunEstimate>({
    queryKey: editorKeys.estimate(projectId ?? '', mode, prompt, chipsKey),
    // NEEDS-BACKEND: EB-4. Until it exists the call fails and no hint shows.
    queryFn: ({ signal }) => estimateRun(projectId!, { prompt, mode, chips: wireChips }, signal),
    enabled: projectReady && online && !readOnly && wantsEstimate(prompt),
    retry: false,
    staleTime: 60_000,
  });
  const estimate = wantsEstimate(value) ? estimateQuery.data : undefined;

  const failedTurn = lastFailedSend(turns);
  const failure: SendIssue | null = failedTurn?.sendError ? sendIssue(failedTurn.sendError, describe) : null;
  const shortOfCredits = isShortOfCredits(estimate);
  const block: Block | null = composerBlock({ hydrated, projectReady, online, readOnly, shortOfCredits });

  const post = useCallback(
    (payload: SentPayload, turnChips: ReadonlyArray<PromptContext>) => {
      if (!projectId) return;
      const turnId = crypto.randomUUID();
      payloads.current.set(turnId, payload);
      runs.dispatch({ kind: 'send', turnId, prompt: payload.body.prompt, chips: turnChips.map(plainChip), mode: payload.body.mode, at: Date.now() });
      createRun(projectId, payload.body, payload.idempotencyKey)
        .then((run) => {
          payloads.current.delete(turnId);
          runs.dispatch({ kind: 'bind', turnId, run });
        })
        .catch((err: unknown) => {
          runs.dispatch({ kind: 'send.failed', turnId, error: errorOf(err) });
          // The text stays: it comes back into an empty box so nothing typed is lost.
          setValue((current) => (current.trim() ? current : payload.body.prompt));
        });
    },
    [projectId, runs],
  );

  const send = useCallback(() => {
    const text = value.trim();
    if (block || (!text && chips.length === 0)) return;
    setActionError(null);
    setValue('');
    if (sim) {
      if (active) sim.enqueue(text, wireChips);
      else sim.start(SIM_SCENARIO[mode], { keep: true, prompt: text });
      return;
    }
    post({ body: { prompt: text, mode, chips: wireChips }, idempotencyKey: crypto.randomUUID() }, chips);
  }, [active, block, chips, mode, post, sim, value, wireChips]);

  const retry = useCallback(() => {
    if (!failedTurn) return;
    // The same idempotency key, so a request that did arrive is not run twice.
    const payload = payloads.current.get(failedTurn.id) ?? { body: { prompt: failedTurn.prompt, mode: failedTurn.mode }, idempotencyKey: crypto.randomUUID() };
    payloads.current.delete(failedTurn.id);
    runs.dispatch({ kind: 'remove', turnId: failedTurn.id });
    post(payload, failedTurn.chips);
    setValue((current) => (current.trim() === failedTurn.prompt ? '' : current));
  }, [failedTurn, post, runs]);

  const stop = useCallback(() => {
    if (!active?.runId || active.stopping) return;
    if (sim) return sim.stop();
    const runId = active.runId;
    runs.dispatch({ kind: 'stop', runId });
    stopRun(runId).catch((err: unknown) => setActionError(`Couldn't stop. ${describe(errorOf(err).code)}`));
  }, [active, runs, sim]);

  const items = useMemo(() => queueItems(queue, queueEdits), [queue, queueEdits]);

  const changeQueue = useCallback(
    (next: QueuedPrompt[]) => {
      const change = diffQueue(items, next);
      // The simulator's queue is local only; real runs are changed on the server (EB-3).
      const runIdOf = (turnId: string) => (sim ? null : (queue.find((turn) => turn.id === turnId)?.runId ?? null));
      const fail = (err: unknown) => setActionError(`Couldn't change the queue. ${describe(errorOf(err).code)}`);
      setActionError(null);
      for (const id of change.removed) {
        const runId = runIdOf(id);
        runs.dispatch({ kind: 'remove', turnId: id });
        if (runId) removeQueuedRun(runId).catch(fail);
      }
      if (change.edited.length > 0) setQueueEdits((edits) => ({ ...edits, ...Object.fromEntries(change.edited.map((edit) => [edit.id, edit.prompt])) }));
      for (const edit of change.edited) {
        const runId = runIdOf(edit.id);
        if (runId) updateQueuedRun(runId, { prompt: edit.prompt }).catch(fail);
      }
      for (const move of change.moved) {
        const runId = runIdOf(move.id);
        if (runId) updateQueuedRun(runId, { queue_position: move.position }).then((run) => runs.dispatch({ kind: 'bind', turnId: move.id, run }), fail);
      }
    },
    [items, queue, runs, sim],
  );

  const removeContext = useCallback(
    (key: string) => {
      if (!chips.find((chip) => chip.id === key)?.locked) selection.remove(key);
    },
    [chips, selection],
  );

  return {
    value,
    setValue,
    mode,
    setMode,
    cycleMode: () => setMode(nextMode),
    chips,
    removeContext,
    running: active !== undefined,
    /** Present only while the active run can be stopped. */
    stop: active?.runId && !active.stopping ? stop : undefined,
    send,
    retry,
    failure,
    actionError,
    dismissActionError: () => setActionError(null),
    queue: items,
    changeQueue,
    estimate,
    shortOfCredits,
    hint: composerHint(estimate, active ? items.length : 0),
    placeholder: composerPlaceholder(turns.at(-1), chips.length),
    block,
    online,
    readOnly,
    backToLatest: doc.backToLatest,
  };
}

export type EditorComposerState = ReturnType<typeof useEditorComposer>;
