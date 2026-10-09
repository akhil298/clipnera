'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';

import { usePersistentState } from '@/lib/design/usePersistentState';

import type { EditorToolId } from './tools';
import type { Arrangement } from './useArrangement';

export type PhoneTab = 'chat' | 'timeline' | 'media';

/** Which zones are open. Sizes live in `ResizablePanels`; this is visibility only. */
export interface WorkspaceLayout {
  arrangement: Arrangement;
  /** The last tool picked (remembered); shown when the panel is open. */
  tool: EditorToolId;
  panelOpen: boolean;
  /** Opens a tool's panel, or closes it when that tool is already open (rail toggle). */
  toggleTool: (tool: EditorToolId) => void;
  /** ⌥1–⌥7: always opens. On phones it switches to the Media tab. */
  openTool: (tool: EditorToolId) => void;
  setPanelOpen: (open: boolean) => void;
  /** ⌘\ */
  togglePanel: () => void;
  /** Side zone at ≥ 1024 (remembered), the Chat drawer at 768–1023, the Chat tab on phones. */
  conversationOpen: boolean;
  setConversationOpen: (open: boolean) => void;
  /** ⌘B */
  toggleConversation: () => void;
  phoneTab: PhoneTab;
  setPhoneTab: (tab: PhoneTab) => void;
}

/** Layout state for one workspace. `storageKey` separates the editor from clip mode. */
export function useWorkspaceLayout(arrangement: Arrangement, storageKey: string): WorkspaceLayout {
  const [tool, setTool] = usePersistentState<EditorToolId>(`cn-${storageKey}:tool`, 'transcript');
  const [sideChat, setSideChat] = usePersistentState(`cn-${storageKey}:conversation`, true);
  const [drawerChat, setDrawerChat] = useState(false);
  const [panelOpen, setPanelOpen] = useState(arrangement === 'wide');
  const [phoneTab, setPhoneTab] = useState<PhoneTab>('chat');

  // Each width starts from its own default (07 §5.4): the panel is open only at ≥ 1440.
  useEffect(() => setPanelOpen(arrangement === 'wide'), [arrangement]);

  const conversationOpen = arrangement === 'phone' ? phoneTab === 'chat' : arrangement === 'md' ? drawerChat : sideChat;
  const setConversationOpen = useCallback(
    (open: boolean) => {
      if (arrangement === 'phone') setPhoneTab(open ? 'chat' : 'timeline');
      else if (arrangement === 'md') setDrawerChat(open);
      else setSideChat(open);
    },
    [arrangement, setSideChat],
  );

  const openTool = useCallback(
    (next: EditorToolId) => {
      setTool(next);
      setPanelOpen(true);
      if (arrangement === 'phone') setPhoneTab('media');
    },
    [arrangement, setTool],
  );

  const toggleTool = useCallback(
    (next: EditorToolId) => {
      if (panelOpen && tool === next && arrangement !== 'phone') setPanelOpen(false);
      else openTool(next);
    },
    [arrangement, openTool, panelOpen, tool],
  );

  return useMemo(
    () => ({
      arrangement,
      tool,
      panelOpen,
      toggleTool,
      openTool,
      setPanelOpen,
      togglePanel: () => (arrangement === 'phone' ? setPhoneTab(phoneTab === 'media' ? 'timeline' : 'media') : setPanelOpen(!panelOpen)),
      conversationOpen,
      setConversationOpen,
      toggleConversation: () => setConversationOpen(!conversationOpen),
      phoneTab,
      setPhoneTab,
    }),
    [arrangement, tool, panelOpen, toggleTool, openTool, conversationOpen, setConversationOpen, phoneTab],
  );
}
