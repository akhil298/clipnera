'use client';

import { Dialog, Kbd } from '@/components/ui';

import { useShell } from './ShellContext';

const SHORTCUTS: ReadonlyArray<{ keys: string[]; what: string }> = [
  { keys: ['⌘', 'K'], what: 'Go to a page, project or setting (Ctrl K on Windows)' },
  { keys: ['/'], what: 'The same, when you aren’t typing in a field' },
  { keys: ['?'], what: 'Show these shortcuts' },
  { keys: ['esc'], what: 'Close a menu, dialog or sheet' },
];

/** The app-wide keys, opened from the account menu, ⌘K or "?". */
export function ShortcutsDialog() {
  const { shortcutsOpen, setShortcutsOpen } = useShell();
  return (
    <Dialog open={shortcutsOpen} onOpenChange={setShortcutsOpen} title="Keyboard shortcuts" size="sm">
      <dl className="flex flex-col gap-3">
        {SHORTCUTS.map((shortcut) => (
          <div key={shortcut.what} className="flex items-center justify-between gap-4">
            <dt className="text-cn-body text-cn-fg-secondary">{shortcut.what}</dt>
            <dd className="shrink-0">
              <Kbd keys={shortcut.keys} />
            </dd>
          </div>
        ))}
      </dl>
    </Dialog>
  );
}
