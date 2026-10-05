'use client';

import { useEffect } from 'react';

import { PROMPT_FOCUS_EVENT } from './events';
import { useShell } from './ShellContext';

/** True while the user is typing somewhere, so single-key shortcuts stay out of the way. */
function isTyping(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  return target.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName) || target.getAttribute('role') === 'combobox';
}

/** ⌘K / Ctrl+K anywhere; "/" and "?" when no field has focus. */
export function useShellShortcuts() {
  const { commandOpen, setCommandOpen, setShortcutsOpen } = useShell();

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.defaultPrevented || event.altKey) return;
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault();
        if (commandOpen) return setCommandOpen(false);
        if (window.dispatchEvent(new CustomEvent(PROMPT_FOCUS_EVENT, { cancelable: true }))) setCommandOpen(true);
        return;
      }
      if (event.metaKey || event.ctrlKey || isTyping(event.target) || document.querySelector('[aria-modal="true"]')) return;
      if (event.key === '/') {
        event.preventDefault();
        setCommandOpen(true);
      } else if (event.key === '?') {
        event.preventDefault();
        setShortcutsOpen(true);
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [commandOpen, setCommandOpen, setShortcutsOpen]);
}
