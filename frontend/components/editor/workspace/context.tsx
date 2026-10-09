'use client';

import { createContext, type ReactNode, type RefObject, useContext, useEffect, useMemo, useRef, useState } from 'react';

import { useToast } from '@/components/ui/Toast';
import { droppedEditMessage } from '@/lib/api/messages/editor';
import type { EditorProject, EditorProjectSummary } from '@/lib/api/editor/types';
import { editorTransport } from '@/lib/api/editor/transport';
import { createRunSimulator, type RunSimulator } from '@/lib/editor/dev/simulator';
import { createRunStore, type RunStore } from '@/lib/editor/run-store';
import { createSelectionStore, type SelectionStore } from '@/lib/editor/selection';
import { createDocStore, type DocStore, idbPendingStorage, selectShown } from '@/lib/editor/store';
import { PreviewEngine } from '@/lib/media';

import { resolveEditorMedia } from './mediaUrls';
import type { WorkspaceLayout } from './useWorkspaceLayout';

export type Connection = 'online' | 'offline' | 'reconnecting';

/**
 * Everything a zone needs, from one context (`useEditor()`). Stores are Zustand vanilla stores:
 * read them with `useDoc` / `useRun` / `useSelection` and a stable selector (04-editor-stores-api.md).
 * The engine is the P1 PreviewEngine for this project; the frame keeps its timeline in step with
 * the doc store's shown document, so zones only mount it (`engine.mount(el)`) and read its clock.
 */
export interface EditorContextValue {
  /** As loaded; the live title/version come from the doc store. */
  project: EditorProjectSummary;
  doc: DocStore;
  runs: RunStore;
  selection: SelectionStore;
  engine: PreviewEngine;
  /** The dev run simulator (`?sim=1`, not in production). The composer calls `sim.start(…)` when set. */
  sim: RunSimulator | null;
  /** In-page flags: the conversation zone exists (`prompt_streaming_v2` or `?sim=1`); `new_ui_editor_timeline` for P2/T1 stand-ins. */
  features: { conversation: boolean; timeline: boolean };
  connection: Connection;
  layout: WorkspaceLayout;
  /** E3 attaches this to the composer's textarea so ⌘K and / can focus it. */
  promptRef: RefObject<HTMLTextAreaElement | null>;
  focusPrompt: () => void;
  /** Flushes pending edits, then opens the export dialog on the acked version (⌘E). */
  openExport: () => void;
  history: { open: boolean; setOpen: (open: boolean) => void };
  shortcuts: { open: boolean; setOpen: (open: boolean) => void };
}

const EditorContext = createContext<EditorContextValue | null>(null);

export function useEditor(): EditorContextValue {
  const value = useContext(EditorContext);
  if (!value) throw new Error('useEditor must be used inside <EditorProvider>');
  return value;
}

export interface EditorSession {
  doc: DocStore;
  runs: RunStore;
  selection: SelectionStore;
  engine: PreviewEngine;
  sim: RunSimulator | null;
  connection: Connection;
}

/**
 * Creates one editor's stores, engine and (in dev) simulator, hydrates the doc store, keeps the
 * engine on the shown document, retries saving when the browser comes back online and toasts
 * edits a rebase dropped. Returns null for the one frame before the engine exists.
 */
export function useEditorSession(project: EditorProject, simulate: boolean): EditorSession | null {
  const toast = useToast();
  const [stores] = useState(() => {
    const runs = createRunStore();
    return { runs, selection: createSelectionStore(), doc: createDocStore({ transport: editorTransport, storage: idbPendingStorage, isLocked: runs.isLocked }) };
  });
  const [engine, setEngine] = useState<PreviewEngine | null>(null);
  const [sim, setSim] = useState<RunSimulator | null>(null);
  const [online, setOnline] = useState(true);
  const [streamUp, setStreamUp] = useState(true);
  const { doc, runs } = stores;

  useEffect(() => {
    void doc.hydrate(project.id, { timeline: project.timeline, version: project.version });
  }, [doc, project]);

  // The engine touches the DOM, so it is made after mount and destroyed with the editor.
  useEffect(() => {
    const next = new PreviewEngine({ timeline: selectShown(doc.store.getState()) ?? project.timeline, resolveUrl: resolveEditorMedia });
    setEngine(next);
    const unsubscribe = doc.store.subscribe((state, prev) => {
      const shown = selectShown(state);
      if (shown && shown !== selectShown(prev)) next.setTimeline(shown);
    });
    return () => {
      unsubscribe();
      next.destroy();
    };
  }, [doc, project.timeline]);

  useEffect(() => {
    if (!simulate) return;
    // Scripted ops are empty, so they are not fed to the doc store (04 §Dev simulator).
    const next = createRunSimulator({
      runs,
      onSideEvent: (event) => {
        if (event.type === 'client.connection') setStreamUp(event.data.online);
        if (event.type === 'sync.reset') void doc.resync();
      },
    });
    setSim(next);
    return () => next.dispose();
  }, [doc, runs, simulate]);

  useEffect(() => {
    const update = () => {
      setOnline(navigator.onLine);
      if (navigator.onLine) void doc.retry();
    };
    setOnline(navigator.onLine);
    window.addEventListener('online', update);
    window.addEventListener('offline', update);
    return () => {
      window.removeEventListener('online', update);
      window.removeEventListener('offline', update);
    };
  }, [doc]);

  // Toast each edit a rebase threw away once, then clear it (dismissing re-enters this listener).
  useEffect(() => {
    const shown = new Set<string>();
    return doc.store.subscribe((state, prev) => {
      if (state.dropped === prev.dropped) return;
      for (const dropped of state.dropped) {
        if (shown.has(dropped.batch.id)) continue;
        shown.add(dropped.batch.id);
        toast.show({ title: droppedEditMessage(dropped.batch.label) });
        doc.dismissDropped(dropped.batch.id);
      }
    });
  }, [doc, toast]);

  return useMemo(
    () => (engine ? { ...stores, engine, sim, connection: !online ? 'offline' : streamUp ? 'online' : 'reconnecting' } : null),
    [engine, online, sim, stores, streamUp],
  );
}

export function EditorProvider({ value, children }: { value: EditorContextValue; children: ReactNode }) {
  return <EditorContext.Provider value={value}>{children}</EditorContext.Provider>;
}

/** A stable ref for the composer's textarea, plus the focus helper that also reveals the Chat tab on phones. */
export function usePromptFocus(layout: WorkspaceLayout): { promptRef: RefObject<HTMLTextAreaElement | null>; focusPrompt: () => void } {
  const promptRef = useRef<HTMLTextAreaElement | null>(null);
  const { arrangement, setConversationOpen } = layout;
  return useMemo(
    () => ({
      promptRef,
      focusPrompt: () => {
        if (arrangement === 'phone') setConversationOpen(true);
        requestAnimationFrame(() => promptRef.current?.focus());
      },
    }),
    [arrangement, setConversationOpen],
  );
}
