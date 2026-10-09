'use client';

import { useEditor } from '../workspace/context';

import { EditorComposer, type EditorComposerProps } from './EditorComposer';

/** EditorComposer wired to `useEditor()`: the editor's stores, simulator, connection and prompt ref. */
export function ConnectedEditorComposer(props: Pick<EditorComposerProps, 'onAddFiles' | 'className'>) {
  const { project, runs, selection, doc, sim, connection, promptRef } = useEditor();
  return <EditorComposer {...props} projectId={project.id} runs={runs} selection={selection} doc={doc} sim={sim} connection={connection} promptRef={promptRef} />;
}
