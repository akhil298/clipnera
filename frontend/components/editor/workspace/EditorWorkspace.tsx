'use client';

import { useEditor } from './context';
import { EditorTopBar } from './EditorTopBar';
import { StatusStrips } from './StatusStrips';
import { useEditorKeys } from './useEditorKeys';
import { WorkspaceLayout } from './WorkspaceLayout';
import { ConversationZone } from './zones/ConversationZone';
import { LeftPanelZone } from './zones/LeftPanelZone';
import { PreviewZone } from './zones/PreviewZone';
import { TimelineZone } from './zones/TimelineZone';

/** The editor's four zones wired to their slot components. Zone units replace the slots, never this file. */
export function EditorWorkspace() {
  const { layout, features, focusPrompt } = useEditor();
  useEditorKeys();
  return (
    <WorkspaceLayout
      layout={layout}
      storageKey="editor"
      topBar={<EditorTopBar />}
      strips={<StatusStrips />}
      renderPanel={(placement) => <LeftPanelZone tool={layout.tool} placement={placement} onClose={() => layout.setPanelOpen(false)} />}
      renderPreview={(placement) => <PreviewZone placement={placement} />}
      renderTimeline={(placement) => <TimelineZone placement={placement} />}
      renderConversation={features.conversation ? (placement) => <ConversationZone placement={placement} /> : undefined}
      onAsk={focusPrompt}
    />
  );
}
