'use client';

import { useCallback, useMemo, useState } from 'react';

import { useExport } from '@/components/export';
import { Drawer } from '@/components/ui/Drawer';
import type { EditorProject } from '@/lib/api/editor/types';
import { type DocState, useDoc } from '@/lib/editor/store';
import { useFlag } from '@/lib/flags/useFlag';

import { EditorProvider, type EditorContextValue, type EditorSession, useEditorSession, usePromptFocus } from './context';
import { EditorFrameSkeleton } from './EditorFrameSkeleton';
import { EditorWorkspace } from './EditorWorkspace';
import { ShortcutsDialog } from './ShortcutsDialog';
import { useArrangement } from './useArrangement';
import { useWorkspaceLayout } from './useWorkspaceLayout';
import { HistoryZone } from './zones/HistoryZone';

export interface EditorRootProps {
  project: EditorProject;
  /** Dev only: drive the run store from `lib/editor/dev` (`?sim=1`). */
  simulate: boolean;
}

/** One loaded editor project: its session, layout and overlays, provided through `useEditor()`. */
export function EditorRoot({ project, simulate }: EditorRootProps) {
  const session = useEditorSession(project, simulate);
  return session ? <EditorSessionView project={project} session={session} simulate={simulate} /> : <EditorFrameSkeleton />;
}

const selectServer = (s: DocState) => s.server;

function EditorSessionView({ project, session, simulate }: EditorRootProps & { session: EditorSession }) {
  const layout = useWorkspaceLayout(useArrangement(), 'editor');
  const { promptRef, focusPrompt } = usePromptFocus(layout);
  const conversationFlag = useFlag('prompt_streaming_v2');
  const timelineFlag = useFlag('new_ui_editor_timeline');
  const [historyOpen, setHistoryOpen] = useState(false);
  const [shortcutsOpen, setShortcutsOpen] = useState(false);
  const { doc } = session;

  // Export always takes the acked server version (pending edits are flushed first, 02-editor §11).
  const server = useDoc(doc, selectServer);
  const target = useMemo(
    () => (server ? { kind: 'editor' as const, projectId: project.id, title: project.title, version: server.version, timeline: server.timeline } : null),
    [project.id, project.title, server],
  );
  const exporter = useExport(target);
  const { open: openDialog } = exporter;
  const openExport = useCallback(() => void doc.flush().finally(openDialog), [doc, openDialog]);

  const value = useMemo<EditorContextValue>(
    () => ({
      ...session,
      project,
      features: { conversation: conversationFlag || simulate, timeline: timelineFlag },
      layout,
      promptRef,
      focusPrompt,
      openExport,
      history: { open: historyOpen, setOpen: setHistoryOpen },
      shortcuts: { open: shortcutsOpen, setOpen: setShortcutsOpen },
    }),
    [session, project, conversationFlag, simulate, timelineFlag, layout, promptRef, focusPrompt, openExport, historyOpen, shortcutsOpen],
  );

  return (
    <EditorProvider value={value}>
      <EditorWorkspace />
      {exporter.dialog}
      <ShortcutsDialog open={shortcutsOpen} onOpenChange={setShortcutsOpen} />
      <Drawer
        open={historyOpen}
        onOpenChange={setHistoryOpen}
        title="Version history"
        description={project.title}
        side={layout.arrangement === 'phone' ? 'bottom' : 'right'}
      >
        <HistoryZone />
      </Drawer>
    </EditorProvider>
  );
}
