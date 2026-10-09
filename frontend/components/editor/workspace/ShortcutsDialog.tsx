'use client';

import { Dialog } from '@/components/ui/Dialog';
import { Kbd } from '@/components/ui/Kbd';

/** The whole editor's keyboard map (02-editor §2.4). Zones bind their own keys; the frame binds Layout and the global ones. */
const SHORTCUTS: ReadonlyArray<{ group: string; rows: ReadonlyArray<[string, string[][]]> }> = [
  {
    group: 'Prompt',
    rows: [
      ['Focus the prompt', [['⌘', 'K'], ['/']]],
      ['Send · new line', [['↵'], ['⇧', '↵']]],
      ['Stop the running edit', [['⌘', '.']]],
      ['Pick option 1–4 on a question', [['1'], ['4']]],
    ],
  },
  {
    group: 'Playback',
    rows: [
      ['Play or pause', [['Space'], ['K']]],
      ['Back or forward 2 s', [['J'], ['L']]],
      ['One frame (preview focused)', [['←'], ['→']]],
      ['Mute · captions · full screen', [['M'], ['C'], ['F']]],
      ['Hold to see before · side by side', [['B'], ['⇧', 'B']]],
    ],
  },
  {
    group: 'Editing',
    rows: [
      ['Undo · redo', [['⌘', 'Z'], ['⇧', '⌘', 'Z']]],
      ['Cut selected words or delete the item', [['⌫']]],
      ['Split at the playhead', [['S']]],
      ['Trim start or end to playhead (timeline focused)', [['['], [']']]],
      ['Nudge one frame (timeline focused)', [[','], ['.']]],
      ['Zoom the timeline', [['⌘', '+'], ['⌘', '−']]],
    ],
  },
  {
    group: 'Layout',
    rows: [
      ['Hide or show the conversation', [['⌘', 'B']]],
      ['Hide or show the tool panel', [['⌘', '\\']]],
      ['Open a tool', [['⌥', '1'], ['⌥', '7']]],
    ],
  },
  {
    group: 'Moving around',
    rows: [
      ['Version history', [['⌘', '⇧', 'H']]],
      ['Export', [['⌘', 'E']]],
      ['Close the top overlay, then clear the selection', [['Esc']]],
      ['Show shortcuts', [['?']]],
    ],
  },
];

export function ShortcutsDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange} title="Keyboard shortcuts" description="Single keys work when no text field has focus." size="md">
      <div className="flex flex-col gap-4">
        {SHORTCUTS.map((section) => (
          <section key={section.group}>
            <h3 className="mb-1.5 text-cn-caption font-semibold text-cn-fg-muted">{section.group}</h3>
            <dl className="flex flex-col gap-1.5">
              {section.rows.map(([label, keys]) => (
                <div key={label} className="flex items-center gap-3 text-cn-label">
                  <dt className="flex-1 text-cn-fg-secondary">{label}</dt>
                  <dd className="flex gap-1">
                    {keys.map((combo) => (
                      <Kbd key={combo.join('')} keys={combo} />
                    ))}
                  </dd>
                </div>
              ))}
            </dl>
          </section>
        ))}
      </div>
    </Dialog>
  );
}
