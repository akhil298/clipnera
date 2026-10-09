'use client';

import { useEffect } from 'react';

import { useEditor } from './context';
import { EDITOR_TOOLS } from './tools';

const isField = (target: EventTarget | null) =>
  target instanceof HTMLElement && (target.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName));

/**
 * The frame's global keys (02-editor §2.4, 07 §5.4): ⌘B conversation, ⌘\ panel, ⌥1–⌥7 tools, ⌘E
 * export, ⌘K and / prompt, ⌘⇧H history, ? shortcuts, Esc clears the selection. Zones bind their own.
 */
export function useEditorKeys(): void {
  const { layout, features, selection, history, shortcuts, openExport, focusPrompt } = useEditor();

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.defaultPrevented) return;
      const mod = event.metaKey || event.ctrlKey;
      const key = event.key.toLowerCase();
      const run = (action: () => void) => {
        event.preventDefault();
        action();
      };

      if (mod && !event.altKey) {
        if (key === 'b' && !event.shiftKey && features.conversation) return run(layout.toggleConversation);
        if (key === '\\') return run(layout.togglePanel);
        if (key === 'e' && !event.shiftKey) return run(openExport);
        if (key === 'k' && !event.shiftKey && features.conversation) return run(focusPrompt);
        if (key === 'h' && event.shiftKey) return run(() => history.setOpen(true));
        return;
      }
      if (event.altKey && !mod) {
        const tool = EDITOR_TOOLS[Number(event.code.replace('Digit', '')) - 1];
        if (event.code.startsWith('Digit') && tool) run(() => layout.openTool(tool.id));
        return;
      }
      if (isField(event.target)) return;
      if (event.key === '/' && features.conversation) return run(focusPrompt);
      if (event.key === '?') return run(() => shortcuts.setOpen(true));
      // An open overlay takes Escape first (it holds focus); only then does Escape clear the selection.
      const inOverlay = event.target instanceof Element && event.target.closest('[role="dialog"],[role="alertdialog"],[role="menu"]');
      if (event.key === 'Escape' && !inOverlay) selection.clear();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [features.conversation, focusPrompt, history, layout, openExport, selection, shortcuts]);
}
