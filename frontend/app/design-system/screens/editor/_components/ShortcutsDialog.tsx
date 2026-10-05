'use client';

import { Dialog } from '@/components/ui/Dialog';
import { Kbd } from '@/components/ui/Kbd';

/** The studio's keyboard map, kept, plus the Editor's additions (marked new). */
export const SHORTCUTS: ReadonlyArray<{ group: string; rows: ReadonlyArray<[string, string[][], boolean?]> }> = [
  {
    group: 'Prompt',
    rows: [
      ['Focus the prompt bar', [['⌘', 'K']], true],
      ['Focus the prompt bar (no field focused)', [['/']], true],
      ['Send · new line', [['↵'], ['⇧', '↵']], true],
      ['Stop the running edit', [['⌘', '.']], true],
      ['Pick option 1–4 on a question', [['1'], ['4']], true],
    ],
  },
  {
    group: 'Playback',
    rows: [
      ['Play or pause', [['Space'], ['K']]],
      ['Back or forward 2 s', [['J'], ['L']]],
      ['Mute · captions · full screen', [['M'], ['C'], ['F']], true],
      ['Hold to see before', [['B']], true],
    ],
  },
  {
    group: 'Editing',
    rows: [
      ['Undo the last edit (AI or hand)', [['⌘', 'Z']]],
      ['Redo', [['⇧', '⌘', 'Z']]],
      ['Cut selected words', [['⌫']]],
      ['Highlight selected words', [['H']]],
      ['Trim start or end to playhead (timeline focused)', [['['], [']']], true],
      ['Nudge one frame (timeline focused)', [[','], ['.']], true],
      ['Zoom timeline', [['⌘', '+'], ['⌘', '−']], true],
    ],
  },
  {
    group: 'Moving around',
    rows: [
      ['Previous or next clip', [['['], [']']]],
      ['Version history', [['⌘', '⇧', 'H']], true],
      ['Export', [['⌘', 'E']]],
      ['Back to clips', [['Esc']]],
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
              {section.rows.map(([label, keys, added]) => (
                <div key={label} className="flex items-center gap-3 text-cn-label">
                  <dt className="flex-1 text-cn-fg-secondary">
                    {label}
                    {added && <span className="ml-1.5 text-cn-caption text-cn-accent-text">new</span>}
                  </dt>
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
